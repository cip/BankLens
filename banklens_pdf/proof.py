"""Local search and image-only redacted copies. Never log document strings.

Search text stays in RAM. Output pages are fresh RGB images: everything starts
black, then only the account header and selected booking bands are copied in.
No original PDF objects, metadata, text layers or attachments are transferred.
"""
from __future__ import annotations

from collections import defaultdict
import hashlib
import io
import math
from pathlib import Path
import secrets
import shlex
import threading
import unicodedata
import zipfile

from PIL import Image, ImageDraw
import pypdfium2 as pdfium
from reportlab.lib.utils import ImageReader
from reportlab.pdfgen import canvas

from .fields import bounds, recognize_page, summary_boundary, table_context
from .preview import quiet_renderer


class ProofError(ValueError):
    """Only fixed public codes are exposed to the browser."""


def normalize(value):
    return " ".join(unicodedata.normalize("NFKC",value).casefold().replace("−","-").split())


def query_terms(query):
    if not isinstance(query,str) or len(query)>500:
        raise ProofError("invalid_query")
    try:
        return [normalize(term) for term in shlex.split(query) if normalize(term)]
    except ValueError:
        raise ProofError("unclosed_quote") from None


def words_text(layout,ids):
    wanted=set(ids)
    output=[]
    previous=None
    for token in layout["tokens"]:
        if token["id"] in wanted:
            if output:
                output.append(" " if token["line"]==previous else "\n")
            output.append(token["text"])
            previous=token["line"]
    return "".join(output)


def index_bookings(review,progress=lambda done,total,count:None,cancel=None):
    """Fresh coarse recognition, using local examples but not stale predictions."""
    workspace=review.load_workspace()
    profile=review.learn(workspace)
    if not any(a["kind"]=="example" for d in workspace["documents"] for a in d["annotations"]) and review.profile_path.is_file():
        profile=review.load_profile()
    total=sum(d["page_count"] for d in review.documents)
    records=[]
    done=0
    for descriptor in review.documents:
        document_id=descriptor["document_id"]
        previous=None
        fragments={}
        saved=next(d for d in workspace["documents"] if d["document_id"]==document_id)
        for number in range(1,descriptor["page_count"]+1):
            if cancel and cancel.is_set():
                raise ProofError("cancelled")
            layout=review.text_layout(document_id,number)
            rejected=[a for a in saved["annotations"] if a["page"]==number and a["kind"]=="rejected"]
            outcome=recognize_page(profile,layout,document_id,rejected,previous)
            previous=outcome["carry"]
            annotations=outcome["suggestions"]
            roots={a["id"]:a for a in annotations if a["field"]=="transaction.row"}
            for event in outcome["rows"]:
                row=roots.get(event["id"])
                if row is None:
                    continue
                predecessor=row.get("continuation_of")
                record=fragments.get(predecessor) if predecessor else None
                if record is None:
                    identity=hashlib.sha256(f"{document_id}:{row['id']}".encode()).hexdigest()[:24]
                    record={"id":identity,"document_id":document_id,"booking_date":"","value_date":"",
                            "amount":"","text_parts":[],"search_parts":[],"pieces":[],
                            "complete":False,"missing_start":bool(predecessor)}
                    records.append(record)
                children=[a for a in annotations if a.get("row_id")==row["id"]]
                def value(field):
                    child=next((a for a in children if a["field"]==field),None)
                    return words_text(layout,child["token_ids"]) if child else ""
                if not record["booking_date"]:
                    record["booking_date"]=value("transaction.booking_date")
                record["value_date"]=value("transaction.value_date") or record["value_date"]
                record["amount"]=value("transaction.amount") or record["amount"]
                body=value("transaction.full_text")
                if body:
                    record["text_parts"].append(body)
                record["search_parts"].append(words_text(layout,row["token_ids"]))
                selected=set(row["token_ids"])
                tokens=[t for t in layout["tokens"] if t["id"] in selected and t.get("rotation",0)==0]
                if not tokens:
                    continue
                context=table_context(layout)
                record["pieces"].append({"document_id":document_id,"page":number,"row_id":row["id"],
                    "token_ids":list(row["token_ids"]),"box":bounds(tokens),
                    "header_bottom":context["top"] if context else None,
                    "table_left":context["left"] if context else None,
                    "summary_top":summary_boundary(layout)})
                record["complete"]=not row.get("partial",False) and not record["missing_start"]
                fragments[row["id"]]=record
            done+=1
            progress(done,total,len(records))
    for record in records:
        record["text"]="\n".join(record.pop("text_parts"))
        record["search_text"]=normalize(" ".join(record.pop("search_parts"))+" "+record["booking_date"]+" "+record["value_date"]+" "+record["amount"])
        # Make both local trailing-minus and signed decimal amount queries work.
        amount=record["amount"].replace(" ","").replace("−","-")
        if amount.endswith("-"):
            record["search_text"]+=" "+normalize("-"+amount[:-1])
    return records


def public_record(record):
    return {key:record[key] for key in ("id","document_id","booking_date","value_date","amount","text","complete")}|{
        "pages":sorted({piece["page"] for piece in record["pieces"]})}


def page_bands(layout,pieces):
    context=table_context(layout)
    if context is None:
        raise ProofError("table_boundary_unknown")
    footer=summary_boundary(layout) or 1
    bands=[]
    all_selected=set(i for piece in pieces for i in piece["token_ids"])
    for piece in pieces:
        x,y,w,h=piece["box"]
        xpad=1/layout["width"]
        ypad=1/layout["height"]
        top=max(context["top"],y-ypad)
        bottom=min(footer,y+h+ypad)
        left=max(0,min(x,context["left"])-xpad)
        right=min(1,x+w+xpad)
        # Never let padding expose glyphs belonging to an adjacent booking.
        for token in layout["tokens"]:
            if token["id"] in all_selected or token.get("rotation",0)!=0:
                continue
            tx,ty,tw,th=token["box"]
            if tx+tw<=left or tx>=right:
                continue
            if ty+th<=y and ty+th>top:
                top=ty+th+.1/layout["height"]
            if ty>=y+h and ty<bottom:
                bottom=ty-.1/layout["height"]
        if bottom<=top:
            raise ProofError("invalid_mask")
        bands.append([left,top,right,bottom])
    return context["top"],bands


def render_redacted(review,document_id,number,pieces,dpi=180):
    """Return sanitized pixels and page dimensions, never an original image."""
    if not review.source_is_current(document_id):
        raise ProofError("source_changed")
    layout=review.text_layout(document_id,number)
    header,bands=page_bands(layout,pieces)
    with quiet_renderer(),pdfium.PdfDocument(str(review.paths[document_id])) as document:
        page=document[number-1]
        try:
            width,height=page.get_size()
            scale=min(dpi/72,4500/max(width,height))
            bitmap=page.render(scale=scale,may_draw_forms=False)
            try:
                original=bitmap.to_pil().convert("RGB")
            finally:
                bitmap.close()
        finally:
            page.close()
    try:
        result=Image.new("RGB",original.size,(0,0,0))
        rectangles=[[0,0,1,header]]+bands
        for left,top,right,bottom in rectangles:
            rect=(max(0,math.ceil(left*original.width)),max(0,math.ceil(top*original.height)),
                  min(original.width,math.floor(right*original.width)),min(original.height,math.floor(bottom*original.height)))
            if rect[2]>rect[0] and rect[3]>rect[1]:
                region=original.crop(rect)
                result.paste(region,rect[:2])
                region.close()
        # Rotated marginal stamps are not part of a booking or its evidence.
        draw=ImageDraw.Draw(result)
        for token in layout["tokens"]:
            if token.get("rotation",0)!=0 and token["box"][1]>=header:
                x,y,w,h=token["box"]
                draw.rectangle((math.floor(x*result.width)-1,math.floor(y*result.height)-1,
                                math.ceil((x+w)*result.width)+1,math.ceil((y+h)*result.height)+1),fill=(0,0,0))
        result.info.clear()
        if not review.source_is_current(document_id):
            result.close()
            raise ProofError("source_changed")
        return result,(width,height)
    finally:
        original.close()


def write_redacted_pdf(review,document_id,pieces,output,progress=lambda:None):
    by_page=defaultdict(list)
    for piece in pieces:
        by_page[piece["page"]].append(piece)
    if not by_page:
        raise ProofError("empty_selection")
    pdf=canvas.Canvas(str(output),pageCompression=1)
    pdf.setTitle("BankLens Zahlungsnachweis - geschwaerzte Kopie")
    pdf.setAuthor("")
    pdf.setSubject("")
    pdf.setCreator("BankLens")
    for number,page_pieces in sorted(by_page.items()):
        image,size=render_redacted(review,document_id,number,page_pieces)
        try:
            pdf.setPageSize(size)
            pdf.drawImage(ImageReader(image),0,0,width=size[0],height=size[1])
            pdf.setFillColorRGB(.8,.8,.8)
            pdf.setFont("Helvetica",6)
            pdf.drawString(10,6,f"Geschwaerzte Kopie | {document_id} | Originalseite {number}")
            pdf.showPage()
        finally:
            image.close()
        progress()
    pdf.save()
    output.chmod(0o600)
    if not review.source_is_current(document_id):
        output.unlink(missing_ok=True)
        raise ProofError("source_changed")


class ProofService:
    def __init__(self,review,output_directory=Path("output/pdf")):
        self.review=review
        self.output_directory=output_directory.resolve()
        source_directory=next(iter(review.paths.values())).parent.resolve()
        if self.output_directory.is_relative_to(source_directory):
            raise ProofError("output_in_source_directory")
        self.lock=threading.RLock()
        self.records={}
        self.cancel=threading.Event()
        self.status={"phase":"idle","pages_done":0,"pages_total":sum(d["page_count"] for d in review.documents),"booking_count":0}
        self.export_status={"phase":"idle","pages_done":0,"pages_total":0,"files":[]}
        self.downloads={}

    def state(self):
        with self.lock:
            return {"index":dict(self.status),"export":dict(self.export_status)}

    def start_index(self):
        with self.lock:
            if self.status["phase"]=="indexing" or self.export_status["phase"]=="exporting":
                raise ProofError("busy")
            self.status={"phase":"indexing","pages_done":0,"pages_total":sum(d["page_count"] for d in self.review.documents),"booking_count":0}
            self.records={}
            self.cancel.clear()
        threading.Thread(target=self._index,daemon=True).start()
        return self.state()

    def _index(self):
        def progress(done,total,count):
            with self.lock:
                self.status.update(pages_done=done,pages_total=total,booking_count=count)
        try:
            records=index_bookings(self.review,progress,self.cancel)
            with self.lock:
                self.records={r["id"]:r for r in records}
                self.status.update(phase="ready",booking_count=len(records))
        except Exception as error:
            code=str(error) if isinstance(error,ProofError) else "index_failed"
            with self.lock:
                self.status.update(phase="error",error=code)

    def search(self,query):
        terms=query_terms(query)
        with self.lock:
            if self.status["phase"]!="ready":
                raise ProofError("index_not_ready")
            matches=[record for record in self.records.values() if all(term in record["search_text"] for term in terms)]
            return {"total":len(matches),"results":[public_record(r) for r in matches[:500]],"limit":500}

    def selection(self,ids):
        if not isinstance(ids,list) or not ids or len(ids)>500 or any(not isinstance(i,str) for i in ids) or len(set(ids))!=len(ids):
            raise ProofError("invalid_selection")
        with self.lock:
            if self.status["phase"]!="ready" or any(i not in self.records for i in ids):
                raise ProofError("stale_selection")
            records=[self.records[i] for i in ids]
        if any(not r["complete"] for r in records):
            raise ProofError("incomplete_booking")
        pieces=[piece for record in records for piece in record["pieces"]]
        if len({(p["document_id"],p["page"]) for p in pieces})>200:
            raise ProofError("too_many_pages")
        return pieces

    def preview(self,ids,document_id,number):
        pieces=self.selection(ids)
        selected=[p for p in pieces if p["document_id"]==document_id and p["page"]==number]
        if not selected:
            raise ProofError("page_not_selected")
        image,_=render_redacted(self.review,document_id,number,selected,dpi=120)
        try:
            stream=io.BytesIO()
            image.save(stream,format="PNG")
            return stream.getvalue()
        finally:
            image.close()

    def start_export(self,ids):
        pieces=self.selection(ids)
        with self.lock:
            if self.status["phase"]=="indexing" or self.export_status["phase"]=="exporting":
                raise ProofError("busy")
            job=secrets.token_hex(12)
            pages=len({(p["document_id"],p["page"]) for p in pieces})
            self.export_status={"phase":"exporting","pages_done":0,"pages_total":pages,"files":[]}
        threading.Thread(target=self._export,args=(job,pieces),daemon=True).start()
        return self.state()

    def _export(self,job,pieces):
        folder=self.output_directory/job
        generated=[]
        try:
            folder.mkdir(mode=0o700,parents=True,exist_ok=False)
            by_document=defaultdict(list)
            for piece in pieces:
                by_document[piece["document_id"]].append(piece)
            def progress():
                with self.lock:
                    self.export_status["pages_done"]+=1
            for document_id,document_pieces in by_document.items():
                filename=f"nachweis-{document_id}.pdf"
                target=folder/filename
                generated.append(target)
                write_redacted_pdf(self.review,document_id,document_pieces,target,progress)
            if len(generated)>1:
                bundle=folder/"zahlungsnachweise.zip"
                with zipfile.ZipFile(bundle,"w",compression=zipfile.ZIP_DEFLATED) as archive:
                    for target in generated:
                        archive.write(target,arcname=target.name)
                bundle.chmod(0o600)
                generated.append(bundle)
            with self.lock:
                files=[]
                for target in generated:
                    key=job+"/"+target.name
                    self.downloads[key]=target
                    files.append({"name":target.name,"key":key,"bytes":target.stat().st_size})
                self.export_status.update(phase="ready",files=files)
        except Exception as error:
            for target in generated:
                target.unlink(missing_ok=True)
            code=str(error) if isinstance(error,ProofError) else "export_failed"
            with self.lock:
                self.export_status.update(phase="error",error=code,files=[])

    def download(self,key):
        with self.lock:
            target=self.downloads.get(key)
        if target is None or not target.is_file():
            raise ProofError("download_not_found")
        return target
