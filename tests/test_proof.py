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
from reportlab.pdfgen import canvas

from banklens_pdf.preview import Review, make_server
from banklens_pdf.proof import ProofError, ProofService, index_bookings, page_bands, render_redacted, write_redacted_pdf


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
        self.assertEqual(target.stat().st_mode&0o777,0o600)

    def test_asynchronous_service_export_and_selection_validation(self):
        service=ProofService(self.review,self.root/"exports")
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
        self.assertEqual(len(PdfReader(service.download(state["files"][0]["key"])).pages),1)

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
