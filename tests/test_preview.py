import contextlib
import http.client
import io
import json
from pathlib import Path
import tempfile
import threading
import unittest

from reportlab.pdfgen import canvas

from banklens_pdf.preview import Review, make_server


SECRET = "SYNTHETIC_PRIVATE_SENTINEL"


class PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # All contents are artificial. Original statements are never test inputs.
        stream = io.BytesIO()
        pdf = canvas.Canvas(stream, pagesize=(595, 842))
        pdf.setTitle(SECRET)
        pdf.drawString(40, 780, SECRET)
        pdf.showPage()
        pdf.setPageSize((842, 595))
        pdf.drawString(40, 540, "Second synthetic page")
        pdf.showPage()
        pdf.save()
        cls.pdf_bytes = stream.getvalue()

    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.source = self.root / "source"
        self.source.mkdir()
        self.original = self.source / (SECRET + ".pdf")
        self.original.write_bytes(self.pdf_bytes)
        self.review = Review(self.source, self.root / "private")

    def tearDown(self):
        self.assertEqual(self.original.read_bytes(), self.pdf_bytes)
        self.temporary.cleanup()

    def plan(self):
        plan = self.review.empty_plan()
        plan["documents"][0]["regions"] = [{"page": 1, "box": [.1, .1, .3, .1],
                                             "label": "Name", "replacement": "MUSTERPERSON"}]
        return plan

    def test_render_uses_memory_and_leaves_no_image_on_disk(self):
        image = self.review.render("document-001", 1)
        self.assertTrue(image.startswith(b"\x89PNG\r\n\x1a\n"))
        self.assertNotIn(SECRET.encode(), image)
        self.assertEqual(list(self.root.rglob("*.png")), [])
        self.assertEqual(self.review.public_documents(), [{"document_id": "document-001", "page_count": 2}])

    def test_plan_round_trip_strips_unexpected_fields(self):
        plan = self.plan()
        plan["source_path"] = SECRET
        plan["documents"][0]["metadata"] = SECRET
        self.assertEqual(self.review.save(plan), 1)
        loaded = self.review.load()
        self.assertNotIn(SECRET, json.dumps(loaded))
        self.assertEqual(loaded["documents"][0]["regions"], plan["documents"][0]["regions"])
        self.assertFalse(loaded["anonymization_performed"])
        self.assertEqual(self.review.plan_path.stat().st_mode & 0o777, 0o600)

    def test_plan_rejects_bad_coordinates_pages_and_source_bindings(self):
        for bad in ([0, 0, float("nan"), .1], [0, 0, -1, .1], [.9, 0, .2, .1], [True, 0, .2, .1]):
            with self.subTest(box=bad):
                plan = self.plan()
                plan["documents"][0]["regions"][0]["box"] = bad
                with self.assertRaises(ValueError):
                    self.review.validate_plan(plan)
        plan = self.plan()
        plan["documents"][0]["regions"][0]["page"] = 3
        with self.assertRaises(ValueError):
            self.review.save(plan)
        plan = self.plan()
        plan["documents"][0]["source_sha256"] = "wrong-document"
        with self.assertRaises(ValueError):
            self.review.save(plan)
        with self.assertRaises(ValueError):
            Review(self.source, self.source / "output")

    def test_old_plan_is_not_applied_to_other_documents(self):
        plan = self.plan()
        plan["documents"][0]["source_sha256"] = "different-source"
        self.review.state_directory.mkdir()
        self.review.plan_path.write_text(json.dumps(plan))
        with self.assertRaises(ValueError):
            self.review.load()

    def test_invalid_page_never_returns_document_derived_errors(self):
        with self.assertRaises(ValueError):
            self.review.render("document-001", 0)
        with self.assertRaises(ValueError):
            self.review.render("document-001", 3)

    def test_text_layer_and_workspace_profile_store_no_extracted_values(self):
        layout=self.review.text_layout("document-001",1)
        self.assertTrue(layout["selection_available"])
        self.assertEqual("".join(t["text"] for t in layout["tokens"]),SECRET)
        for token in layout["tokens"]:
            x,y,w,h=token["box"]
            self.assertTrue(0<=x<x+w<=1 and 0<=y<y+h<=1)
        workspace=self.review.empty_workspace()
        workspace["documents"][0]["annotations"]=[{"id":"test-example","field":"owner.name","page":1,
            "token_ids":[t["id"] for t in layout["tokens"]],"kind":"example","row_id":None}]
        self.assertTrue(self.review.save_workspace(workspace)["profile_updated"])
        self.assertEqual(self.review.load_workspace(),self.review.validate_workspace(workspace))
        self.assertNotIn(SECRET,self.review.workspace_path.read_text())
        self.assertNotIn(SECRET,json.dumps(self.review.load_profile()))
        self.assertEqual(self.review.workspace_path.stat().st_mode & 0o777,0o600)
        self.assertEqual((self.review.state_directory/"profiles"/self.review.selected_profile.split(":")[1]/"1.json").stat().st_mode & 0o777,0o600)
        self.assertEqual(self.review.load_profile()["engine"],"layout-examples-v2")

    def test_legacy_character_ids_and_owner_and_continuation_metadata_survive(self):
        workspace=self.review.empty_workspace()
        workspace["documents"][0]["annotations"]=[
            {"id":"owner","field":"owner.name","page":1,"token_ids":[3],"kind":"example","row_id":None,"entity_id":"holder-2"},
            {"id":"row-start","field":"transaction.row","page":1,"token_ids":[0],"kind":"suggestion","row_id":None,"family":"direct_debit","partial":True,"continued_on":2},
            {"id":"row-end","field":"transaction.row","page":2,"token_ids":[0],"kind":"suggestion","row_id":None,"family":"direct_debit","partial":False,"continuation_of":"row-start"},
        ]
        self.review.private_write(self.review.workspace_path,workspace)
        original_bytes=self.review.workspace_path.read_bytes()
        loaded=self.review.load_workspace()
        annotations=loaded["documents"][0]["annotations"]
        self.assertEqual(annotations[0]["token_ids"],[0])
        self.assertEqual(annotations[0]["entity_id"],"holder-2")
        self.assertEqual(annotations[1]["continued_on"],2)
        self.assertEqual(annotations[2]["continuation_of"],"row-start")
        self.assertEqual(self.review.workspace_path.read_bytes(),original_bytes)

    def test_loopback_routes_headers_and_cross_origin_protection(self):
        server, url = make_server(self.review)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        port = server.server_port
        prefix = "/" + url.split("/", 3)[3]
        origin = f"http://127.0.0.1:{port}"

        def request(method, route, payload=None, extra_headers=None):
            connection = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
            headers = {"Content-Type": "application/json", "Origin": origin,
                       "X-BankLens-Request": "1", **(extra_headers or {})}
            body = None if payload is None else json.dumps(payload)
            connection.request(method, route, body=body, headers=headers)
            response = connection.getresponse()
            result = response.status, dict(response.getheaders()), response.read()
            connection.close()
            return result

        stdout, stderr = io.StringIO(), io.StringIO()
        try:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                status, headers, data = request("GET", prefix + "api/documents")
                self.assertEqual(status, 200)
                self.assertEqual(headers["Cache-Control"], "no-store")
                self.assertIn("default-src 'none'", headers["Content-Security-Policy"])
                self.assertNotIn(SECRET.encode(), data)
                self.assertEqual(request("GET", "/api/documents")[0], 404)
                self.assertEqual(request("GET", prefix + "api/documents", extra_headers={"Host": "evil.invalid"})[0], 404)
                self.assertEqual(request("POST", prefix + "api/plan", self.plan(), {"Origin": "http://evil.invalid"})[0], 403)
                self.assertFalse(self.review.plan_path.exists())
                self.assertEqual(request("POST", prefix + "api/plan", self.plan())[0], 200)
                self.assertEqual(request("GET", prefix + "api/page/document-001/1.png")[0], 200)
                status, _, data = request("GET",prefix+"api/text/document-001/1.json")
                self.assertEqual(status,200)
                self.assertIn(SECRET.encode(),data) # Only the user's local browser gets this data.
                self.assertEqual(request("GET",prefix+"api/workspace")[0],200)
                state=self.review.empty_workspace()
                token_ids=[t["id"] for t in json.loads(data)["tokens"]]
                state["documents"][0]["annotations"]=[{"id":"http-example","field":"owner.name","page":1,
                    "token_ids":token_ids,"kind":"example","row_id":None}]
                status, _, data=request("POST",prefix+"api/learn",state)
                self.assertEqual(status,200)
                self.assertNotIn(SECRET.encode(),data)
                profile=json.loads(data)
                status,_,data=request("POST",prefix+"api/recognize",{"profile":profile,"document_id":"document-001","page":2,"existing":[]})
                self.assertEqual(status,200)
                self.assertEqual(json.loads(data)["suggestions"],[])
                self.assertEqual(request("POST",prefix+"api/workspace",state,{"Origin":"http://evil.invalid"})[0],403)
                self.assertEqual(request("POST",prefix+"api/workspace",state)[0],200)
                status, _, data = request("GET", prefix + "api/page/" + SECRET + "/1.png")
                self.assertEqual(status, 409)
                self.assertNotIn(SECRET.encode(), data)
                self.assertEqual(request("GET", prefix + "../preview.py")[0], 404)
            self.assertNotIn(SECRET, stdout.getvalue() + stderr.getvalue())
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
