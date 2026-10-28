"""Profiles tested only with generated statements and artificial layout tokens."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from reportlab.pdfgen import canvas

from banklens_pdf.preview import Review, make_server
from banklens_pdf.proof import proof_profile_context
from banklens_pdf.fields import recognize_page
from banklens_pdf.profiles import BUNDLED
from test_multiline import layout_fixture


class ProfileTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.source = self.root/'input'
        self.source.mkdir()
        stream = io.BytesIO()
        pdf = canvas.Canvas(stream)
        pdf.drawString(40, 780, 'SYNTHETIC_OWNER_SENTINEL')
        pdf.showPage()
        pdf.save()
        self.original = self.source/'synthetic.pdf'
        self.original_bytes = stream.getvalue()
        self.original.write_bytes(self.original_bytes)
        self.review = Review(self.source, self.root/'state')

    def tearDown(self):
        self.assertEqual(self.original.read_bytes(), self.original_bytes)
        self.temp.cleanup()

    def workspace(self, name='Synthetic bank'):
        workspace = self.review.empty_workspace()
        workspace['profile_name'] = name
        layout = self.review.text_layout('document-001',1)
        workspace['documents'][0]['annotations'] = [{'id':'owner','field':'owner.name','page':1,
            'kind':'example','token_ids':[t['id'] for t in layout['tokens']], 'row_id':None}]
        return workspace

    def test_bundled_default_is_structural_and_recognizes_synthetic_blocks(self):
        self.assertEqual(self.review.selected_profile,'bundled:bank-austria:1')
        profile = self.review.load_profile()
        self.assertEqual(profile['profile_name'],'Bank Austria')
        self.assertTrue(profile['header_rules'])
        # Inspect every string: only fixed field/engine/scope enums, no learned values.
        allowed = set(__import__('banklens_pdf.fields',fromlist=['FIELDS']).FIELDS)
        allowed.update(('Bank Austria','layout-examples-v2','booking-blocks-4','date','amount',
                        'iban','currency','text','first','following','card','direct_debit','transfer','generic'))
        def check(value):
            if isinstance(value,str):
                self.assertTrue(value in allowed or value in ('holder-1','holder-2'))
            elif isinstance(value,dict):
                for item in value.values(): check(item)
            elif isinstance(value,list):
                for item in value: check(item)
        check(profile)
        layout,_ = layout_fixture()
        outcome = recognize_page(profile,layout,'document-001')
        self.assertEqual(len(outcome['rows']),4)
        self.assertTrue(outcome['carry'])
        self.assertFalse(self.review.state_directory.exists())

    def test_revisions_copies_restart_and_old_session_identity(self):
        bundled_bytes=(BUNDLED/'bank-austria.json').read_bytes()
        self.review.save_workspace(self.workspace())
        first=self.review.selected_profile
        first_path=self.root/'state/profiles'/first.split(':')[1]/'1.json'
        first_bytes=first_path.read_bytes()
        old=Review(self.source,self.root/'state')
        self.review.save_workspace(self.workspace())
        second=self.review.selected_profile
        self.assertEqual(first.split(':')[1],second.split(':')[1])
        self.assertEqual(second.split(':')[2],'2')
        self.assertEqual(first_path.read_bytes(),first_bytes)
        self.assertEqual(old.selected_profile,first)
        self.assertEqual(old.profiles.metadata(first)['revision'],1)
        self.review.save_workspace(self.workspace('Another synthetic bank'))
        third=self.review.selected_profile
        self.assertNotEqual(third.split(':')[1],first.split(':')[1])
        restored=Review(self.source,self.root/'state')
        self.assertEqual(restored.selected_profile,third)
        self.assertEqual({p['reference'] for p in restored.profiles.catalog()['profiles']},
                         {'examples','bundled:bank-austria:1',first,second,third})
        self.assertEqual((BUNDLED/'bank-austria.json').read_bytes(),bundled_bytes)
        for path in (self.root/'state/profiles').rglob('*.json'):
            self.assertNotIn('SYNTHETIC_OWNER_SENTINEL',path.read_text())
            self.assertEqual(path.stat().st_mode & 0o777,0o600)

    def test_legacy_profile_is_preserved_and_explicit_choice_beats_examples(self):
        legacy=self.review.learn(self.workspace('Legacy synthetic'))
        self.review.private_write(self.review.profile_path,legacy)
        original=self.review.profile_path.read_bytes()
        restored=Review(self.source,self.root/'state')
        self.assertEqual(restored.selected_profile,'legacy')
        self.review.private_write(self.review.workspace_path,self.workspace())
        restored.persist_profile_selection('bundled:bank-austria:1')
        profile,_=proof_profile_context(restored)
        self.assertEqual(profile['profile_name'],'Bank Austria')
        restored.save_workspace(self.workspace('Local copy'))
        self.assertEqual(self.review.profile_path.read_bytes(),original)

    def test_invalid_revisions_paths_and_symlinks_are_not_loaded(self):
        for reference in ('../field-profile.json','local:../../x:1','bundled:bank-austria:2','local:'+'a'*32+':0'):
            with self.subTest(reference=reference),self.assertRaises((ValueError,OSError)):
                self.review.profiles.load(reference)
        self.review.save_workspace(self.workspace())
        ref=self.review.selected_profile
        path=self.root/'state/profiles'/ref.split(':')[1]/'1.json'
        envelope=json.loads(path.read_text())
        envelope['catalog_schema_version']=2
        path.write_text(json.dumps(envelope))
        with self.assertRaises(ValueError): self.review.profiles.load(ref)
        self.assertEqual(self.review.profiles.catalog()['invalid_profiles'],1)
        path.unlink()
        path.symlink_to(self.original)
        with self.assertRaises(ValueError): self.review.profiles.load(ref)

    def test_synthetic_http_profile_switch_is_isolated_and_origin_protected(self):
        # Exercise the real HTTP handler in memory: this environment forbids socket bind.
        def bind(server): server.server_name='localhost'; server.server_port=8765
        with patch('http.server.HTTPServer.server_bind',bind),patch('socketserver.TCPServer.server_activate'):
            server,url=make_server(self.review)
        prefix='/'+url.split('/',3)[3]
        class Socket:
            def __init__(self,data): self.input=io.BytesIO(data); self.output=io.BytesIO()
            def makefile(self,*args): return self.input
            def settimeout(self,*args): pass
            def sendall(self,data): self.output.write(data)
        def request(route,payload=None,origin='http://127.0.0.1:8765'):
            body=json.dumps(payload).encode() if payload is not None else b''
            method='POST' if payload is not None else 'GET'
            wire=(f'{method} {route} HTTP/1.1\r\nHost: 127.0.0.1:8765\r\nOrigin: {origin}\r\nX-BankLens-Request: 1\r\nContent-Type: application/json\r\nContent-Length: {len(body)}\r\nConnection: close\r\n\r\n').encode()+body
            sock=Socket(wire)
            server.RequestHandlerClass(sock,('127.0.0.1',1234),server)
            header,data=sock.output.getvalue().split(b'\r\n\r\n',1)
            return int(header.split()[1]),json.loads(data) if b'application/json' in header else data
        try:
            self.assertEqual(request(prefix+'profiles.js')[0],200)
            self.assertIn(b'api/profile/select',request(prefix+'profiles.js')[1])
            self.assertEqual(request(prefix+'api/profiles')[0],200)
            payload={'reference':'examples'}
            self.assertEqual(request(prefix+'api/profile/select',payload,'https://evil.invalid')[0],403)
            self.assertEqual(request('/missing/api/profile/select',payload)[0],403)
            code,result=request(prefix+'api/profile/select',payload)
            self.assertEqual(code,200)
            new_prefix=result['session_path']
            self.assertNotEqual(prefix,new_prefix)
            self.assertEqual(request(new_prefix+'api/profiles')[1]['selected_profile'],'examples')
            self.assertEqual(request(prefix+'api/profiles')[1]['selected_profile'],'bundled:bank-austria:1')
            profile=self.review.learn(self.workspace())
            code,recognized=request(new_prefix+'api/recognize',{'profile':profile,'document_id':'document-001','page':1})
            self.assertEqual(code,200)
            self.assertTrue(recognized['suggestions'])
            self.assertTrue(all(a['profile_sha256']==recognized['profile_sha256'] for a in recognized['suggestions']))
            workspace=self.workspace()
            workspace['documents'][0]['annotations']=recognized['suggestions']
            self.assertEqual(self.review.validate_workspace(workspace)['documents'][0]['annotations'][0]['profile_sha256'],recognized['profile_sha256'])
            self.assertNotEqual(recognized['profile_sha256'],request(prefix+'api/config')[1]['profile_sha256'])
            self.assertEqual(request(new_prefix+'api/profile/select',{'reference':'../x'})[0],400)
            self.assertEqual(request(prefix+'api/profiles')[1]['selected_profile'],'bundled:bank-austria:1')
        finally:
            server.server_close()


if __name__=='__main__': unittest.main()
