"""Synthetic-only tests of search, multi-page grouping and burned-in masking."""
import io
import http.client
import json
import math
from pathlib import Path
import tempfile
import threading
import time
import unittest

from pypdf import PdfReader
from PIL import Image
import pypdfium2 as pdfium
from reportlab.pdfgen import canvas

from banklens_pdf.preview import Review, make_server, quiet_renderer
from banklens_pdf.proof import ProofError, ProofService, index_bookings, page_bands, proof_profile_context, render_redacted, write_redacted_pdf, write_combined_pdf
from banklens_pdf.fields import bounds


def artificial_pdf():
    stream=io.BytesIO()
    pdf=canvas.Canvas(stream,pagesize=(600,420))
    pdf.setAuthor("PRIVATE_SOURCE_AUTHOR")
    pdf.setTitle("PRIVATE_SOURCE_TITLE")
    for number in (1,2,3):
        pdf.setFont("Helvetica-Bold",14)
        pdf.drawString(40,385,"ARTIFICIAL BANK")
        pdf.setFont("Helvetica",8)
        pdf.drawString(40,360,"Visible owner: SAMPLE PERSON")
        pdf.drawString(40,320,"Buchungsnr./Buchungstext")
        pdf.drawString(450,320,"Wert")
        pdf.drawString(520,320,"Betrag")
        pdf.setFont("Courier",10)
        if number==1:
            pdf.drawString(40,290,"04.10 POS")
            pdf.drawString(100,275,"KEEPCLINIC CONSULTATION")
            pdf.drawString(450,275,"04.10")
            pdf.drawRightString(580,275,"42,50-")
            pdf.drawString(40,245,"05.10 POS")
            pdf.drawString(100,230,"HIDDEN_OTHER_BOOKING")
            pdf.drawString(450,230,"05.10")
            pdf.drawRightString(580,230,"99,00-")
            pdf.drawString(40,195,"06.10 SEPA Lastschrift")
            pdf.drawString(100,180,"CONTINUED_TARGET")
            pdf.drawString(150,145,"Fortsetzung folgt auf Blatt 2")
        elif number==2:
            pdf.drawString(100,290,"CONTINUED_REFERENCE_END")
            pdf.drawString(450,290,"06.10")
            pdf.drawRightString(580,290,"123,45-")
            pdf.drawString(40,245,"07.10 POS")
            pdf.drawString(100,230,"HIDDEN_LAST_BOOKING")
            pdf.drawString(450,230,"07.10")
            pdf.drawRightString(580,230,"17,00-")
            pdf.setFont("Helvetica",7)
            pdf.drawString(40,190,"alter Kontostand")
            pdf.drawString(390,190,"neuer Kontostand")
            pdf.setFont("Courier",10)
            pdf.drawRightString(580,165,"8888,88")
        else:
            pdf.drawString(40,290,"08.10 POS")
            pdf.drawString(100,275,"HIDDEN_ENTIRE_PAGE")
            pdf.drawString(450,275,"08.10")
            pdf.drawRightString(580,275,"55,00-")
        pdf.showPage()
    pdf.save()
    return stream.getvalue()


def redaction_pdf():
    """Artificial one-page header with recognizable personal field roles."""
    stream=io.BytesIO()
    pdf=canvas.Canvas(stream,pagesize=(600,600))
    pdf.setFont("Helvetica-Bold",14)
    pdf.drawString(40,580,"ARTIFICIAL BANK")
    pdf.setFont("Helvetica",9)
    values=[
        ("Kontoinhaber 1:","SAMPLE_OWNER_ONE",555),
        ("Kontoinhaber 2:","SAMPLE_OWNER_TWO",540),
        ("Adresse:","SAMPLE_ADDRESS",525),
        ("Kontonummer:","0000123456",510),
        ("IBAN:","DE00123456789012345678",495),
        ("Waehrung:","EUR",480),
        ("Auszugsdatum:","01.09.2026",465),
        ("Auszugszeitraum:","SAMPLE_PERIOD",450),
        ("Anfangssaldo:","123,45",435),
        ("Endsaldo:","678,90",420),
    ]
    for label,value,y in values:
        pdf.drawString(40,y,label)
        pdf.drawString(180,y,value)
    pdf.setFont("Helvetica",8)
    pdf.drawString(40,380,"Buchungsnr./Buchungstext")
    pdf.drawString(450,380,"Wert")
    pdf.drawString(520,380,"Betrag")
    pdf.setFont("Courier",10)
    pdf.drawString(40,340,"01.10 POS")
    pdf.drawString(100,340,"KEEP_SYNTHETIC_BOOKING")
    pdf.drawString(450,340,"01.10")
    pdf.drawRightString(580,340,"42,50-")
    pdf.drawString(40,315,"02.10 POS")
    pdf.drawString(100,315,"HIDDEN_SYNTHETIC_BOOKING")
    pdf.drawString(450,315,"02.10")
    pdf.drawRightString(580,315,"99,00-")
    pdf.setFont("Helvetica",7)
    pdf.drawString(40,270,"alter Kontostand")
    pdf.drawString(390,270,"neuer Kontostand")
    pdf.setFont("Courier",10)
    pdf.drawRightString(580,250,"8888,88")
    pdf.showPage()
    pdf.save()
    return stream.getvalue()


class ProofTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source_bytes=artificial_pdf()

    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.root=Path(self.temporary.name)
        self.source=self.root/"source"
        self.source.mkdir()
        self.original=self.source/"PRIVATE_FILENAME.pdf"
        self.original.write_bytes(self.source_bytes)
        self.review=Review(self.source,self.root/"private")

    def tearDown(self):
        self.assertEqual(self.original.read_bytes(),self.source_bytes)
        self.temporary.cleanup()

    def test_selected_header_fields_match_in_preview_and_export(self):
        source=self.root/"header-source"
        source.mkdir()
        original=source/"synthetic-header.pdf"
        synthetic_bytes=redaction_pdf()
        original.write_bytes(synthetic_bytes)
        review=Review(source,self.root/"header-state")
        layout=review.text_layout("document-001",1)
        examples=[
            ("owner.name","SAMPLE_OWNER_ONE","holder-1"),
            ("owner.name","SAMPLE_OWNER_TWO","holder-2"),
            ("owner.address.line1","SAMPLE_ADDRESS",None),
            ("account.number","0000123456",None),
            ("account.iban","DE00123456789012345678",None),
            ("account.currency","EUR",None),
            ("statement.date","01.09.2026",None),
            ("statement.period","SAMPLE_PERIOD",None),
            ("statement.opening_balance","123,45",None),
            ("statement.closing_balance","678,90",None),
        ]
        workspace=review.empty_workspace()
        annotations=workspace["documents"][0]["annotations"]
        for index,(field,value,entity_id) in enumerate(examples):
            tokens=[token for token in layout["tokens"] if token["text"]==value]
            self.assertTrue(tokens,value)
            annotation={"id":f"header-example-{index}","field":field,"page":1,
                        "token_ids":[token["id"] for token in tokens],"kind":"example",
                        "row_id":None,"entity_id":entity_id}
            if entity_id is None:
                annotation.pop("entity_id")
            annotations.append(annotation)
        review.save_workspace(workspace)
        profile,workspace=proof_profile_context(review)
        piece_tokens=[token for token in layout["tokens"]
                      if token["text"]=="KEEP_SYNTHETIC_BOOKING"]
        self.assertTrue(piece_tokens)
        row_tokens=[token for token in layout["tokens"] if token["line"]==piece_tokens[0]["line"]]
        piece={"document_id":"document-001","page":1,
               "token_ids":[token["id"] for token in row_tokens],"box":bounds(row_tokens)}
        service=ProofService(review,self.root/"header-exports")
        service.profile,service.workspace=profile,workspace
        metadata={field["id"]:field for field in service.state()["redaction_fields"]}
        self.assertTrue(metadata["owner-1"]["available"])
        self.assertTrue(metadata["owner-2"]["available"])
        self.assertTrue(metadata["owner-1"]["default"])
        self.assertTrue(metadata["owner-2"]["default"])
        self.assertTrue(metadata["owner-1"]["first_page"])
        self.assertFalse(metadata["owner-1"]["following_pages"])
        self.assertTrue(metadata["account-iban"]["default"])
        self.assertFalse(metadata["account-currency"]["default"])
        self.assertNotIn("SAMPLE_OWNER_ONE",json.dumps(service.state()))
        service.records={"synthetic-booking":{"id":"synthetic-booking","complete":True,"pieces":[piece]}}
        service.status["phase"]="ready"

        def assert_field_pixels(image,hidden):
            for value,is_hidden in hidden.items():
                token=next(token for token in layout["tokens"] if token["text"]==value)
                x,y,w,h=token["box"]
                crop=image.crop((math.floor(x*image.width),math.floor(y*image.width),
                                 math.ceil((x+w)*image.width),math.ceil((y+h)*image.width)))
                try:
                    extrema=crop.getextrema()
                    if is_hidden:
                        self.assertEqual(extrema,((0,0),(0,0),(0,0)),value)
                    else:
                        self.assertTrue(any(high>0 for _,high in extrema),value)
                finally:
                    crop.close()

        png=service.preview(["synthetic-booking"],"document-001",1)
        with Image.open(io.BytesIO(png)) as image:
            assert_field_pixels(image,{"SAMPLE_OWNER_ONE":True,"SAMPLE_OWNER_TWO":True,
                "SAMPLE_ADDRESS":True,"0000123456":True,"DE00123456789012345678":True,
                "123,45":True,"678,90":True,"EUR":False,"01.09.2026":False,"SAMPLE_PERIOD":False})

        chosen=["owner-1","account-iban"]
        preview=service.preview(["synthetic-booking"],"document-001",1,redaction_fields=chosen)
        with Image.open(io.BytesIO(preview)) as image:
            assert_field_pixels(image,{"SAMPLE_OWNER_ONE":True,"SAMPLE_OWNER_TWO":False,
                "SAMPLE_ADDRESS":False,"0000123456":False,"DE00123456789012345678":True})
        service.start_export(["synthetic-booking"],redaction_fields=chosen)
        deadline=time.monotonic()+10
        while service.state()["export"]["phase"]=="exporting" and time.monotonic()<deadline:
            time.sleep(.02)
        exported=service.state()["export"]
        self.assertEqual(exported["phase"],"ready")
        with quiet_renderer(),pdfium.PdfDocument(service.download(exported["files"][0]["key"]).read_bytes()) as document:
            page=document[0]
            bitmap=page.render(scale=1,may_draw_forms=False)
            try:
                with bitmap.to_pil() as image:
                    assert_field_pixels(image,{"SAMPLE_OWNER_ONE":True,"SAMPLE_OWNER_TWO":False,
                        "SAMPLE_ADDRESS":False,"0000123456":False,"DE00123456789012345678":True})
            finally:
                bitmap.close()
                page.close()
        with self.assertRaises(ProofError):
            service.preview(["synthetic-booking"],"document-001",1,redaction_fields=["owner-3"])
        self.assertEqual(original.read_bytes(),synthetic_bytes)

    def test_index_groups_fragments_and_searches_all_fields(self):
        records=index_bookings(self.review)
        self.assertEqual(len(records),5)
        continued=next(r for r in records if "CONTINUED_TARGET" in r["text"])
        self.assertEqual([p["page"] for p in continued["pieces"]],[1,2])
        self.assertEqual(continued["amount"],"123,45-")
        self.assertTrue(continued["complete"])
        self.assertIn("CONTINUED_REFERENCE_END",continued["text"])
        service=ProofService(self.review,self.root/"exports")
        service.records={r["id"]:r for r in records}
        service.status["phase"]="ready"
        self.assertEqual(service.search("continued_target 123,45")["total"],1)
        self.assertEqual(service.search("06.10 CONTINUED_REFERENCE_END")["total"],1)
        self.assertEqual(service.search("-123,45")["total"],1)
        self.assertEqual(service.search("continued_target 99,00")["total"],0)
        self.assertNotIn("PRIVATE_FILENAME",json.dumps(service.search("")))
        with self.assertRaises(ProofError):
            service.search('"unfinished')

    def test_mask_starts_black_and_never_keeps_other_rows_or_balance(self):
        records=index_bookings(self.review)
        wanted=next(r for r in records if "CONTINUED_TARGET" in r["text"])
        for piece in wanted["pieces"]:
            layout=self.review.text_layout(piece["document_id"],piece["page"])
            header,bands=page_bands(layout,[piece])
            image,_=render_redacted(self.review,piece["document_id"],piece["page"],[piece],dpi=72)
            try:
                self.assertEqual(image.mode,"RGB")
                self.assertEqual(image.info,{})
                # Every pixel outside approved rectangles is opaque black.
                allowed=[(math.ceil(left*image.width),math.ceil(top*image.height),math.floor(right*image.width),math.floor(bottom*image.height)) for left,top,right,bottom in [[0,0,1,header]]+bands]
                for y in range(image.height):
                    for x in range(image.width):
                        if not any(left<=x<right and top<=y<bottom for left,top,right,bottom in allowed):
                            self.assertEqual(image.getpixel((x,y)),(0,0,0))
                # Independently locate non-selected row and balance sentinels.
                for token in layout["tokens"]:
                    if token["text"].startswith("HIDDEN") or token["text"]=="8888,88":
                        x,y,w,h=token["box"]
                        self.assertEqual(image.crop((math.floor(x*image.width),math.floor(y*image.height),math.ceil((x+w)*image.width),math.ceil((y+h)*image.height))).getextrema(),((0,0),(0,0),(0,0)))
                self.assertEqual(image.getpixel((300,20)),(255,255,255))
            finally:
                image.close()

    def test_export_contains_only_selected_pages_and_no_original_objects(self):
        records=index_bookings(self.review)
        wanted=next(r for r in records if "CONTINUED_TARGET" in r["text"])
        target=self.root/"copy.pdf"
        write_redacted_pdf(self.review,"document-001",wanted["pieces"],target)
        result=PdfReader(target)
        self.assertEqual(len(result.pages),2)
        self.assertFalse(result.get_fields())
        self.assertNotIn("/EmbeddedFiles",str(result.trailer["/Root"].get("/Names",{})))
        metadata=str(result.metadata)
        self.assertNotIn("PRIVATE_SOURCE",metadata)
        for page in result.pages:
            self.assertNotIn("HIDDEN",page.extract_text())
            self.assertNotIn("CONTINUED",page.extract_text()) # selected text is pixels too
            self.assertTrue(page.images)
            self.assertIn(self.original.name,page.extract_text())
            self.assertNotIn(str(self.source),page.extract_text())
        self.assertEqual(target.stat().st_mode&0o777,0o600)

    def test_combined_pdf_deduplicates_pages_and_preserves_source_order(self):
        second=self.source/"Zweiter Auszug Ärzte.pdf"
        second.write_bytes(self.source_bytes)
        review=Review(self.source,self.root/"private")
        records=index_bookings(review)
        selected=[r for r in reversed(records) if "CONTINUED_TARGET" in r["text"] or r["document_id"]=="document-001" and "KEEPCLINIC" in r["text"]]
        pieces=[piece for record in selected for piece in record["pieces"]]
        target=self.root/"combined.pdf"
        write_combined_pdf(review,pieces,target)
        result=PdfReader(target)
        self.assertEqual(len(result.pages),4)
        expected=[(self.original.name,1),(self.original.name,2),(second.name,1),(second.name,2)]
        for page,(filename,number) in zip(result.pages,expected):
            footer=page.extract_text()
            self.assertIn(filename,footer)
            self.assertIn(f"Originalseite {number}",footer)
            self.assertNotIn("HIDDEN",footer)
            self.assertNotIn("CONTINUED",footer)
            self.assertTrue(page.images)
        self.assertNotIn("PRIVATE_SOURCE",str(result.metadata))
        neutral=self.root/"neutral.pdf"
        write_combined_pdf(review,pieces,neutral,source_reference="neutral")
        text="".join(page.extract_text() for page in PdfReader(neutral).pages)
        self.assertIn("document-001",text)
        self.assertIn("document-002",text)
        self.assertNotIn(self.original.name,text)
        self.assertNotIn(second.name,text)

    def test_long_unicode_reference_wraps_in_its_own_margin(self):
        filename="Ärzte_"+"langer Dateiname_"*10+"Österreich.pdf"
        self.original.rename(self.source/filename)
        try:
            review=Review(self.source,self.root/"private")
            wanted=next(r for r in index_bookings(review) if "KEEPCLINIC" in r["text"])
            target=self.root/"long-name.pdf"
            write_combined_pdf(review,wanted["pieces"],target)
            page=PdfReader(target).pages[0]
            self.assertIn("".join(filename.split()),"".join(page.extract_text().split()))
            self.assertGreater(float(page.mediabox.height),420+25)
        finally:
            (self.source/filename).rename(self.original)

    def test_asynchronous_service_export_and_selection_validation(self):
        service=ProofService(self.review,self.root/"exports")
        with self.assertRaises(ProofError) as error:
            service.selected_redaction_fields(["owner-1"])
        self.assertEqual(str(error.exception),"field_not_configured")
        service.start_index()
        deadline=time.monotonic()+10
        while service.state()["index"]["phase"]=="indexing" and time.monotonic()<deadline:
            time.sleep(.02)
        self.assertEqual(service.state()["index"]["phase"],"ready")
        record=service.search("keepclinic")["results"][0]
        with self.assertRaises(ProofError):
            service.selection(["unknown"])
        with self.assertRaises(ProofError):
            service.selection([record["id"],record["id"]])
        png=service.preview([record["id"]],"document-001",1)
        self.assertTrue(png.startswith(b"\x89PNG"))
        service.start_export([record["id"]])
        deadline=time.monotonic()+10
        while service.state()["export"]["phase"]=="exporting" and time.monotonic()<deadline:
            time.sleep(.02)
        state=service.state()["export"]
        self.assertEqual(state["phase"],"ready")
        self.assertEqual([file["name"] for file in state["files"]],["zahlungsnachweise.pdf"])
        self.assertEqual(len(PdfReader(service.download(state["files"][0]["key"])).pages),1)
        for kwargs in ({"output_format":"wrong"},{"source_reference":"wrong"}):
            with self.assertRaises(ProofError):
                service.start_export([record["id"]],**kwargs)

    def test_changed_source_is_checked_even_when_layout_was_cached(self):
        self.review.text_layout("document-001",1)
        self.original.write_bytes(self.source_bytes+b"\n% changed")
        try:
            with self.assertRaises(ValueError):
                self.review.text_layout("document-001",1)
        finally:
            self.original.write_bytes(self.source_bytes)

    def test_http_proof_routes_keep_origin_and_session_protection(self):
        server,url=make_server(self.review)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        port=server.server_port
        prefix="/"+url.split("/",3)[3]
        origin=f"http://127.0.0.1:{port}"
        def request(route,payload=None,headers=None):
            connection=http.client.HTTPConnection("127.0.0.1",port,timeout=10)
            connection.request("GET" if payload is None else "POST",route,
                body=None if payload is None else json.dumps(payload),
                headers={"Content-Type":"application/json","Origin":origin,"X-BankLens-Request":"1",**(headers or {})})
            response=connection.getresponse()
            result=response.status,dict(response.getheaders()),response.read()
            connection.close()
            return result
        try:
            self.assertEqual(request(prefix+"proof.html")[0],200)
            self.assertEqual(request(prefix+"api/proof/index",{}, {"Origin":"https://evil.invalid"})[0],403)
            self.assertEqual(request("/api/proof/status")[0],404)
            self.assertEqual(request(prefix+"api/proof/search",{"query":"test"})[0],400)
            self.assertEqual(request(prefix+"api/proof/index",{})[0],200)
            deadline=time.monotonic()+10
            while time.monotonic()<deadline:
                status=json.loads(request(prefix+"api/proof/status")[2])
                if status["index"]["phase"]!="indexing":
                    break
                time.sleep(.02)
            self.assertEqual(status["index"]["phase"],"ready")
            code,headers,data=request(prefix+"api/proof/search",{"query":"continued_target 123,45"})
            self.assertEqual(code,200)
            self.assertEqual(headers["Cache-Control"],"no-store")
            result=json.loads(data)["results"][0]
            self.assertEqual(result["pages"],[1,2])
            self.assertNotIn("PRIVATE_FILENAME",data.decode())
            code,headers,data=request(prefix+"api/proof/preview",{"selected_ids":[result["id"]],"document_id":"document-001","page":1})
            self.assertEqual(code,200)
            self.assertEqual(headers["Content-Type"],"image/png")
            self.assertTrue(data.startswith(b"\x89PNG"))
            self.assertEqual(request(prefix+"api/proof/preview",{"selected_ids":[result["id"]],"document_id":"document-001","page":3})[0],400)
            self.assertEqual(request(prefix+"api/proof/download/../../../README.md")[0],409)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


if __name__=="__main__":
    unittest.main()
