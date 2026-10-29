"""Local search and image-only redacted copies. Never log document strings.

Search text stays in RAM. Output pages are fresh RGB images: everything starts
black, then the account header without selected field masks and selected
booking bands are copied in. No original PDF objects, metadata, text layers or
attachments are transferred.
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date
import hashlib
import io
import math
import os
from pathlib import Path
import re
import secrets
import shlex
import threading
import unicodedata
from urllib.parse import urlsplit
import zipfile

from PIL import Image, ImageDraw
import pypdfium2 as pdfium
import reportlab
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

from .fields import bounds, recognize_page, summary_boundary, table_context, text_lines
from .preview import quiet_renderer
from .private_files import create_private


class ProofError(ValueError):
    """Only fixed public codes are exposed to the browser."""


REDACTION_OPTIONS=(
    {"id":"owner-1","label":"Kontoinhaber 1","default":True},
    {"id":"owner-2","label":"Kontoinhaber 2","default":True},
    {"id":"owner-address","label":"Eigene Adresse","default":True},
    {"id":"account-number","label":"Kontonummer","default":True},
    {"id":"account-iban","label":"IBAN","default":True},
    {"id":"account-currency","label":"Kontowährung","default":False},
    {"id":"statement-date","label":"Auszugsdatum","default":False},
    {"id":"statement-period","label":"Auszugszeitraum","default":False},
    {"id":"opening-balance","label":"Anfangssaldo","default":True},
    {"id":"closing-balance","label":"Endsaldo","default":True},
)
REDACTION_IDS={option["id"] for option in REDACTION_OPTIONS}
HEADER_FIELD_OPTIONS={
    "owner.address.line1":"owner-address",
    "owner.address.line2":"owner-address",
    "owner.address.line3":"owner-address",
    "account.number":"account-number",
    "account.iban":"account-iban",
    "account.currency":"account-currency",
    "statement.date":"statement-date",
    "statement.period":"statement-period",
    "statement.opening_balance":"opening-balance",
    "statement.closing_balance":"closing-balance",
}


def proof_profile_context(review):
    """Return the same local profile and annotations used for fresh indexing."""
    workspace=review.load_workspace()
    profile=review.load_profile()
    return profile,workspace


def owner_option_for_y(profile,y,page_scope=None):
    rules=[r for r in profile.get("header_rules",[]) if r.get("field")=="owner.name"
           and (page_scope is None or r.get("page_scope")==page_scope)]
    if not rules:
        return None
    nearest=min(rules,key=lambda r:abs((r["box"][1]+r["box"][3]/2)-y))
    entity=nearest.get("entity_id")
    if entity in ("holder-1","holder-2"):
        return "owner-"+entity[-1]
    centers=sorted({round(r["box"][1]+r["box"][3]/2,4) for r in rules})
    rank=centers.index(round(nearest["box"][1]+nearest["box"][3]/2,4))+1
    return f"owner-{rank}" if rank<=2 else None


def redaction_option_for_rule(rule,profile):
    if rule.get("field")=="owner.name":
        return owner_option_for_y(profile,rule["box"][1]+rule["box"][3]/2,rule.get("page_scope"))
    return HEADER_FIELD_OPTIONS.get(rule.get("field"))


def redaction_option_for_annotation(annotation,layout,profile):
    field=annotation.get("field")
    if field=="owner.name":
        entity=annotation.get("entity_id")
        if entity in ("holder-1","holder-2"):
            return "owner-"+entity[-1]
        chosen=set(annotation.get("token_ids",[]))
        tokens=[t for t in layout["tokens"] if t["id"] in chosen and t.get("rotation",0)==0]
        if not tokens:
            return None
        box=bounds(tokens)
        scope="first" if layout["page"]==1 else "following"
        return owner_option_for_y(profile,box[1]+box[3]/2,scope)
    return HEADER_FIELD_OPTIONS.get(field)


def redaction_field_metadata(profile):
    scopes={option["id"]:set() for option in REDACTION_OPTIONS}
    for rule in profile.get("header_rules",[]):
        option=redaction_option_for_rule(rule,profile)
        if option in REDACTION_IDS and rule.get("page_scope") in ("first","following"):
            scopes[option].add(rule["page_scope"])
    return [{"id":option["id"],"label":option["label"],"available":bool(scopes[option["id"]]),
             "default":option["default"],"first_page":"first" in scopes[option["id"]],
             "following_pages":"following" in scopes[option["id"]]} for option in REDACTION_OPTIONS]


def default_redaction_fields(profile):
    return {option["id"] for option in redaction_field_metadata(profile) if option["available"] and option["default"]}


def redaction_boxes(review,document_id,number,profile,workspace,requested):
    if not requested:
        return []
    layout=review.text_layout(document_id,number)
    saved=next(d for d in workspace["documents"] if d["document_id"]==document_id)
    rejected=[a for a in saved["annotations"] if a["page"]==number and a["kind"]=="rejected"]
    outcome=recognize_page(profile,layout,document_id,rejected)
    context=table_context(layout)
    lookup={t["id"]:t for t in layout["tokens"]}
    boxes=[]
    for annotation in outcome["suggestions"]:
        option=redaction_option_for_annotation(annotation,layout,profile)
        if option not in requested:
            continue
        tokens=[lookup[i] for i in annotation["token_ids"] if i in lookup and lookup[i].get("rotation",0)==0]
        if not tokens:
            continue
        box=bounds(tokens)
        if context and box[1]+box[3]/2>=context["top"]:
            continue
        boxes.append(box)
    return boxes


FONT_LOCK=threading.Lock()


def footer_font():
    with FONT_LOCK:
        name="BankLensReference"
        if name not in pdfmetrics.getRegisteredFontNames():
            paths=[Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
                   Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
                   Path(reportlab.__file__).parent/"fonts"/"Vera.ttf"]
            path=next((path for path in paths if path.is_file()),None)
            if path is None:
                raise ProofError("reference_font_unavailable")
            pdfmetrics.registerFont(TTFont(name,str(path)))
        return name


def wrap_footer_line(text,font,width):
    lines=[""]
    for character in text:
        if lines[-1] and pdfmetrics.stringWidth(lines[-1]+character,font,7)>width-24:
            lines.append("")
        lines[-1]+=character
    return lines


def repository_link(value=None):
    value=os.environ.get("BANKLENS_REPOSITORY_URL","https://github.com/cip/BankLens") if value is None else value
    value=value.strip()
    if not value:
        return None
    parsed=urlsplit(value)
    path=parsed.path.rstrip("/")
    parts=path.split("/")
    if (parsed.scheme!="https" or parsed.netloc.lower()!="github.com" or
            parsed.username or parsed.password or parsed.query or parsed.fragment or
            len(parts)!=3 or not re.fullmatch(r"[A-Za-z0-9-]{1,39}",parts[1]) or
            not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}",parts[2]) or parts[2].endswith(".git")):
        raise ProofError("invalid_repository_url")
    return f"https://github.com/{parts[1]}/{parts[2]}"


def reference_lines(review,document_id,number,width,source_reference,repo_url=None):
    reference=review.paths[document_id].name if source_reference=="filename" else document_id
    # File basenames only; control characters cannot introduce fake footers.
    reference="".join(c if c.isprintable() else f"\\u{ord(c):04x}" for c in reference)
    text=f"Quelle: {reference} | Originalseite {number}"
    font=footer_font()
    lines=wrap_footer_line(text,font,width)
    linked_lines=[]
    if repo_url:
        repo_lines=wrap_footer_line(f"Geschwärzte Kopie erstellt mit BankLens · {repo_url}",font,width)
        linked_lines=list(range(len(lines),len(lines)+len(repo_lines)))
        lines.extend(repo_lines)
    return font,lines,linked_lines


def normalize(value):
    return " ".join(unicodedata.normalize("NFKC",value).casefold().replace("−","-").split())


def query_terms(query):
    if not isinstance(query,str) or len(query)>500:
        raise ProofError("invalid_query")
    try:
        return [normalize(term) for term in shlex.split(query) if normalize(term)]
    except ValueError:
        raise ProofError("unclosed_quote") from None


def filter_date(value):
    """Parse the ISO date supplied by the browser's date picker."""
    if value is None or value == "":
        return None
    if not isinstance(value,str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}",value):
        raise ProofError("invalid_date_filter")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ProofError("invalid_date_filter") from None


def booking_day(value,statement_date=None):
    """Parse a booking date, inferring a missing year from its statement date."""
    if not isinstance(value,str):
        return None
    raw=value.strip().rstrip(".").strip()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}",raw):
        try:
            return date.fromisoformat(raw)
        except ValueError:
            return None
    match=re.fullmatch(r"(\d{1,2})\s*[./]\s*(\d{1,2})(?:\s*[./]\s*(\d{2,4}))?",raw)
    if not match:
        return None
    day,month,year_text=match.groups()
    day,month=int(day),int(month)
    if year_text:
        year=int(year_text)
        if len(year_text)==2:
            year+=2000 if year<=68 else 1900
    elif isinstance(statement_date,date):
        year=statement_date.year
    else:
        return None
    try:
        result=date(year,month,day)
    except ValueError:
        return None
    if not year_text and isinstance(statement_date,date):
        delta=(result-statement_date).days
        if delta>183:
            try:
                result=date(year-1,month,day)
            except ValueError:
                return None
        elif delta < -183:
            try:
                result=date(year+1,month,day)
            except ValueError:
                return None
    return result


def booking_date_without_year(value):
    """Recognize a valid day/month value that has no year component."""
    if not isinstance(value,str):
        return False
    raw=value.strip().rstrip(".").strip()
    match=re.fullmatch(r"(\d{1,2})\s*[./]\s*(\d{1,2})",raw)
    if not match:
        return False
    day,month=map(int,match.groups())
    try:
        date(2000,month,day)
    except ValueError:
        return False
    return True


def statement_date_for_page(layout,annotations):
    """Read a profiled statement date or a clearly labeled header date."""
    for annotation in annotations:
        if annotation.get("field")=="statement.date":
            parsed=booking_day(words_text(layout,annotation["token_ids"]))
            if parsed:
                return parsed
    context=table_context(layout)
    header_limit=context["top"] if context else 1
    header_tokens=[token for token in layout["tokens"] if token.get("rotation",0)==0
                   and token["box"][1]<header_limit]
    date_pattern=re.compile(r"(?<!\d)(?:\d{4}-\d{2}-\d{2}|\d{1,2}\s*[./]\s*\d{1,2}(?:\s*[./]\s*\d{2,4})?\.?)")
    lines=text_lines(header_tokens)
    for index,line in enumerate(lines):
        line_text=" ".join(token["text"] for token in line)
        label=re.search(r"auszugs\s*datum",line_text,re.IGNORECASE)
        if not label:
            continue
        candidates=[line_text[label.end():]]
        if index+1<len(lines):
            next_line=lines[index+1]
            line_box,next_box=bounds(line),bounds(next_line)
            gap=next_box[1]-(line_box[1]+line_box[3])
            if 0<=gap<=max(line_box[3],next_box[3])*2.5:
                candidates.append(" ".join(token["text"] for token in next_line))
        for candidate_text in candidates:
            found=date_pattern.search(candidate_text)
            if found:
                parsed=booking_day(found.group())
                if parsed:
                    return parsed
    return None


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


def index_bookings(review,progress=lambda done,total,count:None,cancel=None,profile=None,workspace=None):
    """Fresh coarse recognition, using local examples but not stale predictions."""
    if profile is None or workspace is None:
        profile,workspace=proof_profile_context(review)
    total=sum(d["page_count"] for d in review.documents)
    records=[]
    done=0
    for descriptor in review.documents:
        document_id=descriptor["document_id"]
        document_record_start=len(records)
        document_statement_date=None
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
            page_statement_date=statement_date_for_page(layout,annotations)
            if document_statement_date is None and page_statement_date:
                document_statement_date=page_statement_date
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
        for record in records[document_record_start:]:
            record["booking_day"]=booking_day(record["booking_date"],document_statement_date)
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


def render_redacted(review,document_id,number,pieces,dpi=180,redaction_fields=None,profile=None,workspace=None):
    """Return sanitized pixels and page dimensions, never an original image."""
    if not review.source_is_current(document_id):
        raise ProofError("source_changed")
    if profile is None or workspace is None:
        profile,workspace=proof_profile_context(review)
    if redaction_fields is None:
        redaction_fields=default_redaction_fields(profile)
    else:
        redaction_fields=set(redaction_fields)
    layout=review.text_layout(document_id,number)
    header,bands=page_bands(layout,pieces)
    masks=redaction_boxes(review,document_id,number,profile,workspace,redaction_fields)
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
        draw=ImageDraw.Draw(result)
        for left,top,mask_width,mask_height in masks:
            rect=(max(0,math.floor(left*result.width)-2),max(0,math.floor(top*result.height)-2),
                  min(result.width,math.ceil((left+mask_width)*result.width)+2),
                  min(result.height,math.ceil((top+mask_height)*result.height)+2))
            if rect[2]>rect[0] and rect[3]>rect[1]:
                draw.rectangle(rect,fill=(0,0,0))
        # Rotated marginal stamps are not part of a booking or its evidence.
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


def write_combined_pdf(review,pieces,output,progress=lambda:None,source_reference="filename",dpi=180,repo_url=None,
                       redaction_fields=None,profile=None,workspace=None):
    if isinstance(output, Path):
        fd = create_private(output)
        try:
            with os.fdopen(fd, "wb") as stream:
                write_combined_pdf(review, pieces, stream, progress, source_reference, dpi, repo_url,
                                   redaction_fields, profile, workspace)
        except BaseException:
            output.unlink(missing_ok=True)
            raise
        return
    if source_reference not in ("filename","neutral"):
        raise ProofError("invalid_reference")
    repo_url=repository_link(repo_url)
    by_page=defaultdict(list)
    for piece in pieces:
        by_page[(piece["document_id"],piece["page"])].append(piece)
    if not by_page:
        raise ProofError("empty_selection")
    order={d["document_id"]:index for index,d in enumerate(review.documents)}
    pdf=canvas.Canvas(str(output) if isinstance(output,Path) else output,pageCompression=1)
    pdf.setTitle("BankLens Zahlungsnachweis - geschwaerzte Kopie")
    pdf.setAuthor("")
    pdf.setSubject("")
    pdf.setCreator("BankLens")
    for document_id,number in sorted(by_page,key=lambda key:(order[key[0]],key[1])):
        image,size=render_redacted(review,document_id,number,by_page[(document_id,number)],dpi=dpi,
                                   redaction_fields=redaction_fields,profile=profile,workspace=workspace)
        try:
            font,lines,linked_lines=reference_lines(review,document_id,number,size[0],source_reference,repo_url)
            footer_height=16+len(lines)*9
            pdf.setPageSize((size[0],size[1]+footer_height))
            # The reference gets its own margin, never covering original pixels.
            pdf.setFillColorRGB(0,0,0)
            pdf.rect(0,0,size[0],footer_height,fill=1,stroke=0)
            pdf.drawImage(ImageReader(image),0,footer_height,width=size[0],height=size[1])
            pdf.setFillColorRGB(.8,.8,.8)
            pdf.setFont(font,7)
            for index,line in enumerate(lines):
                baseline=footer_height-12-index*9
                pdf.drawString(12,baseline,line)
                if index in linked_lines:
                    link_width=min(size[0]-24,pdfmetrics.stringWidth(line,font,7))
                    pdf.linkURL(repo_url,(12,baseline-2,12+link_width,baseline+8),relative=0,thickness=0)
            pdf.showPage()
        finally:
            image.close()
        progress()
    pdf.save()
    if isinstance(output,Path):
        output.chmod(0o600)
    if any(not review.source_is_current(document_id) for document_id in {key[0] for key in by_page}):
        if isinstance(output,Path):
            output.unlink(missing_ok=True)
        raise ProofError("source_changed")


def write_redacted_pdf(review,document_id,pieces,output,progress=lambda:None,source_reference="filename",repo_url=None,
                       redaction_fields=None,profile=None,workspace=None):
    if any(piece["document_id"]!=document_id for piece in pieces):
        raise ProofError("invalid_selection")
    write_combined_pdf(review,pieces,output,progress,source_reference,repo_url=repo_url,
                       redaction_fields=redaction_fields,profile=profile,workspace=workspace)


class ProofService:
    def __init__(self,review,output_directory=Path("output/pdf"),repo_url=None):
        self.review=review
        self.repo_url=repository_link(repo_url)
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
        self.profile=None
        self.workspace=None
        self.redaction_fields=[]
        self._refresh_profile_context()

    def _refresh_profile_context(self):
        try:
            profile,workspace=proof_profile_context(self.review)
        except Exception:
            profile,workspace=None,None
        with self.lock:
            self.profile,self.workspace=profile,workspace
            self.profile_identity=self.review.profiles.metadata(self.review.selected_profile,profile) if profile else None
            self.redaction_fields=redaction_field_metadata(profile or {})

    def selected_redaction_fields(self,fields):
        available={option["id"] for option in self.redaction_fields if option["available"]}
        if fields is None:
            return {option["id"] for option in self.redaction_fields if option["available"] and option["default"]}
        if not isinstance(fields,list) or len(fields)>len(REDACTION_OPTIONS) or any(not isinstance(item,str) for item in fields) or len(set(fields))!=len(fields):
            raise ProofError("invalid_redaction_fields")
        if any(item not in REDACTION_IDS for item in fields):
            raise ProofError("invalid_redaction_fields")
        if any(item not in available for item in fields):
            raise ProofError("field_not_configured")
        return set(fields)

    def state(self):
        with self.lock:
            return {"index":dict(self.status),"export":dict(self.export_status),
                    "profile":self.profile_identity,
                    "redaction_fields":[dict(option) for option in self.redaction_fields]}

    def start_index(self):
        with self.lock:
            if self.status["phase"]=="indexing" or self.export_status["phase"]=="exporting":
                raise ProofError("busy")
            self.status={"phase":"indexing","pages_done":0,"pages_total":sum(d["page_count"] for d in self.review.documents),"booking_count":0}
            self.records={}
            self.cancel.clear()
        self._refresh_profile_context()
        profile,workspace=self.profile,self.workspace
        threading.Thread(target=self._index,args=(profile,workspace),daemon=True).start()
        return self.state()

    def _index(self,profile,workspace):
        def progress(done,total,count):
            with self.lock:
                self.status.update(pages_done=done,pages_total=total,booking_count=count)
        try:
            records=index_bookings(self.review,progress,self.cancel,profile=profile,workspace=workspace)
            with self.lock:
                self.records={r["id"]:r for r in records}
                self.status.update(phase="ready",booking_count=len(records))
        except Exception as error:
            code=str(error) if isinstance(error,ProofError) else "index_failed"
            with self.lock:
                self.status.update(phase="error",error=code)

    def search(self,query,booking_date_from=None,booking_date_to=None):
        terms=query_terms(query)
        date_from=filter_date(booking_date_from)
        date_to=filter_date(booking_date_to)
        if date_from and date_to and date_from>date_to:
            raise ProofError("invalid_date_range")
        with self.lock:
            if self.status["phase"]!="ready":
                raise ProofError("index_not_ready")
            matches=[]
            unmatched_booking_dates=0
            for record in self.records.values():
                if not all(term in record["search_text"] for term in terms):
                    continue
                if date_from or date_to:
                    day=record.get("booking_day") or booking_day(record["booking_date"])
                    if day is None:
                        unmatched_booking_dates+=booking_date_without_year(record["booking_date"])
                        continue
                    if (date_from and day<date_from) or (date_to and day>date_to):
                        continue
                matches.append(record)
            return {"total":len(matches),"results":[public_record(r) for r in matches[:500]],"limit":500,
                    "unmatched_booking_dates":unmatched_booking_dates}

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

    def preview(self,ids,document_id,number,source_reference="filename",redaction_fields=None):
        with self.lock:
            redact=self.selected_redaction_fields(redaction_fields)
            pieces=self.selection(ids)
            profile,workspace=self.profile,self.workspace
        selected=[p for p in pieces if p["document_id"]==document_id and p["page"]==number]
        if not selected:
            raise ProofError("page_not_selected")
        stream=io.BytesIO()
        write_combined_pdf(self.review,selected,stream,source_reference=source_reference,dpi=120,repo_url=self.repo_url,
                           redaction_fields=redact,profile=profile,workspace=workspace)
        with quiet_renderer(),pdfium.PdfDocument(stream.getvalue()) as document:
            page=document[0]
            try:
                bitmap=page.render(scale=120/72,may_draw_forms=False)
                try:
                    image=bitmap.to_pil()
                    try:
                        output=io.BytesIO()
                        image.save(output,format="PNG")
                        return output.getvalue()
                    finally:
                        image.close()
                finally:
                    bitmap.close()
            finally:
                page.close()

    def start_export(self,ids,output_format="combined",source_reference="filename",redaction_fields=None):
        if output_format not in ("combined","separate"):
            raise ProofError("invalid_export_format")
        if source_reference not in ("filename","neutral"):
            raise ProofError("invalid_reference")
        with self.lock:
            redact=self.selected_redaction_fields(redaction_fields)
            pieces=self.selection(ids)
            if self.status["phase"]=="indexing" or self.export_status["phase"]=="exporting":
                raise ProofError("busy")
            profile,workspace=self.profile,self.workspace
            job=secrets.token_hex(12)
            pages=len({(p["document_id"],p["page"]) for p in pieces})
            self.export_status={"phase":"exporting","pages_done":0,"pages_total":pages,"files":[]}
        threading.Thread(target=self._export,args=(job,pieces,output_format,source_reference,redact,profile,workspace),daemon=True).start()
        return self.state()

    def _export(self,job,pieces,output_format,source_reference,redaction_fields,profile,workspace):
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
            if output_format=="combined":
                target=folder/"zahlungsnachweise.pdf"
                write_combined_pdf(self.review,pieces,target,progress,source_reference,repo_url=self.repo_url,
                                   redaction_fields=redaction_fields,profile=profile,workspace=workspace)
                generated.append(target)
            else:
                for descriptor in self.review.documents:
                    document_id=descriptor["document_id"]
                    if document_id not in by_document:
                        continue
                    target=folder/f"nachweis-{document_id}.pdf"
                    write_redacted_pdf(self.review,document_id,by_document[document_id],target,progress,source_reference,self.repo_url,
                                       redaction_fields,profile,workspace)
                    generated.append(target)
                if len(generated)>1:
                    bundle=folder/"zahlungsnachweise.zip"
                    pdfs=list(generated)
                    fd = create_private(bundle)
                    try:
                        with os.fdopen(fd, "wb") as stream:
                            with zipfile.ZipFile(stream,"w",compression=zipfile.ZIP_DEFLATED) as archive:
                                for target in pdfs:
                                    archive.write(target,arcname=target.name)
                    except BaseException:
                        bundle.unlink(missing_ok=True)
                        raise
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
