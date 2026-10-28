"""Browser preconnections must not stall the local preview server."""
import http.client
from pathlib import Path
import socket
import threading
import unittest

from banklens_pdf.preview import make_server


class EmptyReview:
    selected_profile="examples"
    class profiles:
        @staticmethod
        def metadata(reference): return {"sha256":"0"*64}
    profile_path=Path("/nonexistent-banklens-test-profile")


class ServerTests(unittest.TestCase):
    def check_preconnection(self,incomplete_headers=False):
        server,url=make_server(EmptyReview())
        accepted=threading.Event()
        original_get_request=server.get_request
        def get_request():
            request=original_get_request()
            accepted.set()
            return request
        server.get_request=get_request
        thread=threading.Thread(target=server.serve_forever,daemon=True)
        thread.start()
        idle=socket.create_connection(server.server_address,timeout=2)
        connection=None
        try:
            self.assertTrue(accepted.wait(2))
            if incomplete_headers:
                prefix='/' + url.split('/',3)[3]
                idle.sendall(f'GET {prefix} HTTP/1.1\r\nHost: 127.0.0.1:{server.server_port}\r\n'.encode())
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=1)
            connection.request('GET','/'+url.split('/',3)[3]+'api/config')
            response=connection.getresponse()
            self.assertEqual(response.status,200)
            response.read()
        finally:
            idle.close()
            if connection:
                connection.close()
            server.shutdown()
            thread.join(timeout=3)
            server.server_close()

    def test_idle_browser_connection_does_not_block_other_requests(self):
        self.check_preconnection()

    def test_incomplete_request_does_not_block_other_requests(self):
        self.check_preconnection(incomplete_headers=True)


if __name__=='__main__':
    unittest.main()
