import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from banklens_pdf import desktop


class DesktopTests(unittest.TestCase):
    def test_self_test_uses_a_synthetic_pdf_and_bundled_profile(self):
        desktop.self_test()

    def test_state_requires_absolute_local_app_data(self):
        with patch.dict(os.environ, {'LOCALAPPDATA': 'relative'}):
            with self.assertRaises(RuntimeError):
                desktop.state_directory()
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'LOCALAPPDATA': root}):
            self.assertEqual(desktop.state_directory(), Path(root) / 'BankLens' / 'state')

    def test_window_lifecycle_closes_server(self):
        class Server:
            def __init__(self):
                self.stopped = False
                self.closed = False
            def serve_forever(self):
                pass
            def shutdown(self):
                self.stopped = True
            def server_close(self):
                self.closed = True
        class Window:
            def create_file_dialog(self, kind):
                self.kind = kind
                return ('C:/synthetic',)
        class Webview:
            FOLDER_DIALOG = 20  # pywebview 5.4 public API
            settings = {}
            window = Window()
            def create_window(self, title, url, **kwargs):
                self.url = url
                self.window_options = kwargs
                return self.window
            def start(self, **kwargs):
                self.options = kwargs
        server, view = Server(), Webview()
        captured = {}
        def make_server(review, **kwargs):
            captured.update(kwargs)
            return server, 'http://127.0.0.1:1234/token/'
        with tempfile.TemporaryDirectory() as root, patch.dict(os.environ, {'LOCALAPPDATA': root}), patch.object(desktop, 'make_server', make_server):
            desktop.run(view)
        self.assertTrue(server.stopped and server.closed)
        self.assertEqual(captured['directory_picker'](), 'C:/synthetic')
        self.assertEqual(view.window.kind, view.FOLDER_DIALOG)
        with patch.object(view.window, 'create_file_dialog', return_value=None):
            self.assertIsNone(captured['directory_picker']())
        self.assertEqual(captured['output_directory'], captured['state_directory'] / 'exports')
        self.assertEqual(view.options['gui'], 'edgechromium')
        self.assertTrue(view.window_options['text_select'])
        self.assertFalse(view.settings['ALLOW_FILE_URLS'])


if __name__ == '__main__':
    unittest.main()
