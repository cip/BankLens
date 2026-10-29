"""Folder opening uses artificial PDFs only; old session URLs stay isolated."""
import http.client
import errno
import json
import os
import subprocess
import sys
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from pypdf import PdfReader, PdfWriter

from banklens_pdf.preview import DirectoryError, Review, ReviewSession, make_server, open_directory
from test_proof import artificial_pdf


class SourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory()
        self.root=Path(self.temporary.name).resolve()
        self.source=self.root/"first"
        self.source.mkdir()
        self.original=artificial_pdf()
        (self.source/"input.pdf").write_bytes(self.original)
        self.second=self.root/"second folder ä"
        self.second.mkdir()
        (self.second/"input.PDF").write_bytes(self.original+b"\n% different fixture")
        (self.second/"notes.txt").write_text("Not a PDF")
        (self.second/"nested").mkdir()
        (self.second/"nested"/"nested.pdf").write_bytes(self.original)
        (self.second/"linked.pdf").symlink_to(self.source/"input.pdf")
        self.state=self.root/"private"

    def tearDown(self):
        self.assertEqual((self.source/"input.pdf").read_bytes(),self.original)
        self.assertEqual((self.second/"input.PDF").read_bytes(),self.original+b"\n% different fixture")
        self.temporary.cleanup()

    def test_quoted_absolute_folder_loads_only_direct_non_symlink_pdfs(self):
        opened=open_directory(" '"+str(self.second)+"' ",self.state)
        self.assertEqual(opened.directory,self.second)
        self.assertEqual(len(opened.documents),1)
        self.assertEqual(opened.documents[0]["page_count"],3)
        self.assertEqual(list(opened.paths.values()),[self.second/"input.PDF"])
        self.assertFalse(self.state.exists())

    def test_macos_appledouble_sidecar_is_not_treated_as_a_pdf(self):
        sidecar = self.source/'._input.pdf'
        sidecar.write_bytes(b'\x00\x05\x16\x07' + bytes(32))
        opened = open_directory(str(self.source), self.state)
        self.assertEqual(list(opened.paths.values()), [self.source/'input.pdf'])
        self.assertEqual(sidecar.read_bytes(), b'\x00\x05\x16\x07' + bytes(32))
        only_sidecars = self.root/'only-sidecars'
        only_sidecars.mkdir()
        (only_sidecars/'._input.pdf').write_bytes(sidecar.read_bytes())
        with self.assertRaises(DirectoryError) as caught:
            open_directory(str(only_sidecars), self.state)
        self.assertEqual(str(caught.exception), 'no_pdfs')
        valid_named_sidecar = self.root/'real-pdf-with-prefix'
        valid_named_sidecar.mkdir()
        (valid_named_sidecar/'._valid.pdf').write_bytes(self.original)
        self.assertEqual(len(open_directory(str(valid_named_sidecar), self.state).documents), 1)

    def test_open_folder_without_standard_output_handles(self):
        script = '''
import os, sys
from pathlib import Path
from banklens_pdf.preview import open_directory
os.close(1)
os.close(2)
review = open_directory(sys.argv[1], Path(sys.argv[2]))
assert len(review.documents) == 1
assert review.documents[0]['page_count'] == 3
'''
        result=subprocess.run([sys.executable,'-c',script,str(self.source),str(self.state)],
                              stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        self.assertEqual(result.returncode,0)

    def test_open_folder_when_windowed_runtime_has_unavailable_stdout(self):
        dup=os.dup
        def windowed_dup(fd):
            if fd == 1:
                raise OSError(errno.EBADF, 'synthetic unavailable handle')
            return dup(fd)
        with patch('banklens_pdf.preview.os.dup',side_effect=windowed_dup):
            opened=open_directory(str(self.source),self.state)
        self.assertEqual(opened.documents[0]['page_count'],3)

    def test_session_uses_explicit_output_directory_and_rejects_source_overlap(self):
        output = self.state / "exports"
        for source in (self.source, self.second):
            review = Review(source, self.state)
            session = ReviewSession(review, "synthetic-token", output_directory=output)
            self.assertEqual(session.proofs().output_directory, output.resolve())
            with self.assertRaises(ValueError):
                ReviewSession(review, "synthetic-token", output_directory=source / "exports").proofs()

    def test_bad_paths_have_fixed_errors_and_no_private_strings(self):
        empty=self.root/"empty"
        empty.mkdir()
        broken=self.root/"broken"
        broken.mkdir()
        (broken/"PRIVATE_NAME.pdf").write_bytes(b"PRIVATE_PDF_SENTINEL")
        cases=[(None,"invalid_directory"),("","invalid_directory"),("relative/path","absolute_directory_required"),
               (str(self.root/"PRIVATE_MISSING"),"directory_not_found"),(str(self.source/"input.pdf"),"not_a_directory"),
               (str(empty),"no_pdfs"),(str(broken),"pdf_invalid"),(str(self.root),"directory_contains_state")]
        for path,expected in cases:
            with self.subTest(expected=expected),self.assertRaises(DirectoryError) as caught:
                open_directory(path,self.state)
            self.assertEqual(str(caught.exception),expected)

    def test_password_protected_pdf_has_fixed_diagnostic(self):
        encrypted = self.root / 'encrypted'
        encrypted.mkdir()
        writer = PdfWriter()
        writer.append(PdfReader(self.source / 'input.pdf'))
        writer.encrypt('synthetic-password')
        with (encrypted / 'PRIVATE_NAME.pdf').open('wb') as stream:
            writer.write(stream)
        with self.assertRaises(DirectoryError) as caught:
            open_directory(str(encrypted), self.state)
        self.assertEqual(str(caught.exception), 'pdf_password')
        self.assertEqual(caught.exception.filename, 'PRIVATE_NAME.pdf')

    def test_invalid_saved_selection_has_fixed_diagnostic(self):
        review = Review(self.source, self.state)
        self.state.mkdir()
        review.selection_path.write_text('{"schema_version":1,"reference":"PRIVATE_SENTINEL"}')
        with self.assertRaises(DirectoryError) as caught:
            open_directory(str(self.source), self.state)
        self.assertEqual(str(caught.exception), 'saved_state_unreadable')

    def test_empty_start_opens_a_separate_folder_session(self):
        server,url=make_server(None,state_directory=self.state)
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        prefix="/"+url.split("/",3)[3]
        origin=f"http://127.0.0.1:{server.server_port}"
        def request(route,payload=None,origin_value=None):
            connection=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=10)
            connection.request("GET" if payload is None else "POST",route,None if payload is None else json.dumps(payload),
                {"Content-Type":"application/json","Origin":origin_value or origin,"X-BankLens-Request":"1"})
            response=connection.getresponse()
            result=response.status,response.read()
            connection.close()
            return result
        try:
            self.assertEqual(request(prefix)[0],200)
            self.assertEqual(json.loads(request(prefix+"api/source")[1])["document_count"],0)
            self.assertEqual(json.loads(request(prefix+"api/proof/status")[1])["index"]["phase"],"empty")
            payload={"directory":str(self.source)}
            self.assertEqual(request(prefix+"api/source/load",payload,"https://evil.invalid")[0],403)
            broken=self.root/'broken-synthetic'
            broken.mkdir()
            (broken/'synthetic-invalid.pdf').write_bytes(b'synthetic invalid PDF')
            code,data=request(prefix+'api/source/load',{'directory':str(broken)})
            self.assertEqual(code,400)
            self.assertEqual(json.loads(data),{'error':'pdf_invalid','filename':'synthetic-invalid.pdf'})
            self.assertNotIn(str(broken).encode(),data)
            code,data=request(prefix+"api/source/load",payload)
            self.assertEqual(code,200)
            opened=json.loads(data)
            self.assertNotEqual(opened["session_path"],prefix)
            self.assertEqual(json.loads(request(opened["session_path"]+"api/source")[1])["document_count"],1)
            self.assertEqual(json.loads(request(prefix+"api/source")[1])["document_count"],0)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()

    def test_folder_sessions_are_independent_and_keep_access_checks(self):
        review=Review(self.source,self.state)
        restored_token="restored-folder-session-0123456789abcdef"
        restored_review=Review(self.second,self.state)
        server,url=make_server(review,restored_reviews={restored_token:restored_review})
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        origin=f"http://127.0.0.1:{server.server_port}"
        prefix="/"+url.split("/",3)[3]
        def request(route,payload=None,extra=None):
            connection=http.client.HTTPConnection("127.0.0.1",server.server_port,timeout=10)
            connection.request("GET" if payload is None else "POST",route,None if payload is None else json.dumps(payload),
                {"Content-Type":"application/json","Origin":origin,"X-BankLens-Request":"1",**(extra or {})})
            response=connection.getresponse()
            result=response.status,dict(response.getheaders()),response.read()
            connection.close()
            return result
        try:
            restored=json.loads(request("/"+restored_token+"/api/source")[2])
            self.assertEqual(restored["directory"],str(self.second))
            status,headers,data=request(prefix+"api/source")
            self.assertEqual(status,200)
            self.assertEqual(headers["Cache-Control"],"no-store")
            self.assertEqual(json.loads(data)["directory"],str(self.source))
            payload={"directory":str(self.second)}
            self.assertEqual(request(prefix+"api/source/load",payload,{"Origin":"https://evil.invalid"})[0],403)
            self.assertEqual(request(prefix+"api/source/load",payload,{"Host":"evil.invalid"})[0],403)
            self.assertEqual(request("/api/source/load",payload)[0],403)
            self.assertEqual(request(prefix+"api/source/load",payload,{"X-BankLens-Request":""})[0],403)
            status,_,data=request(prefix+"api/source/load",payload)
            self.assertEqual(status,200)
            loaded=json.loads(data)
            self.assertEqual(loaded["document_count"],1)
            second_prefix=loaded["session_path"]
            self.assertNotEqual(second_prefix,prefix)
            self.assertEqual(request(second_prefix+"proof.html")[0],200)
            first=json.loads(request(prefix+"api/workspace")[2])
            second=json.loads(request(second_prefix+"api/workspace")[2])
            self.assertNotEqual(first["documents"][0]["source_sha256"],second["documents"][0]["source_sha256"])
            self.assertEqual(request(second_prefix+"api/workspace",first)[0],400)
            self.assertEqual(request(prefix+"api/workspace",first)[0],200)
            self.assertEqual(json.loads(request(prefix+"api/source")[2])["directory"],str(self.source))
            self.assertEqual(json.loads(request(second_prefix+"api/source")[2])["directory"],str(self.second))
            self.assertEqual(json.loads(request(second_prefix+"api/proof/status")[2])["index"]["phase"],"idle")
            status,_,data=request(prefix+"api/source/load",{"directory":str(self.root/"PRIVATE_MISSING")})
            self.assertEqual(status,400)
            self.assertEqual(json.loads(data),{"error":"directory_not_found"})
            self.assertEqual(request(prefix+"api/source/load",[])[0],400)
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


if __name__=="__main__":
    unittest.main()
