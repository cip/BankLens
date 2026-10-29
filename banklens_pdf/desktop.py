"""Windows desktop entry point for the existing loopback application."""
import os
from pathlib import Path
import sys
import tempfile
import threading

from .preview import DirectoryError, make_server


def state_directory():
    local = os.environ.get("LOCALAPPDATA")
    if not local or not Path(local).is_absolute():
        raise RuntimeError("LOCALAPPDATA is unavailable")
    return Path(local) / "BankLens" / "state"


def run(webview):
    state = state_directory()
    state.mkdir(parents=True, exist_ok=True)
    window = None

    def pick_directory():
        try:
            selected = window.create_file_dialog(webview.FOLDER_DIALOG)
            return selected[0] if selected else None
        except Exception:
            raise DirectoryError("directory_picker_unavailable") from None

    server, url = make_server(None, state_directory=state, directory_picker=pick_directory,
                              output_directory=state / "exports")
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    try:
        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.settings["ALLOW_FILE_URLS"] = False
        window = webview.create_window("BankLens", url, width=1200, height=800, min_size=(800, 600))
        webview.start(gui="edgechromium", private_mode=True)
    finally:
        server.shutdown()
        server.server_close()
        worker.join()


def self_test():
    """Exercise the frozen application's PDF and profile resources with artificial data."""
    from reportlab.pdfgen import canvas
    from .preview import open_directory

    with tempfile.TemporaryDirectory() as root:
        root = Path(root)
        source = root / 'input'
        source.mkdir()
        pdf = canvas.Canvas(str(source / 'synthetic.pdf'))
        pdf.drawString(40, 750, 'Synthetic test')
        pdf.save()
        review = open_directory(str(source), root / 'state')
        if (len(review.documents) != 1 or review.documents[0]['page_count'] != 1
                or review.load_profile()['profile_name'] != 'Bank Austria'
                or not review.render('document-001', 1).startswith(b'\x89PNG\r\n\x1a\n')):
            raise RuntimeError('desktop_self_test_failed')


def main():
    if sys.argv[1:] == ['--self-test']:
        try:
            self_test()
        except Exception:
            raise SystemExit(1) from None
        return
    import webview
    run(webview)
