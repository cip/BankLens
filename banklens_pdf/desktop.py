"""Windows desktop entry point for the existing loopback application."""
import os
from pathlib import Path
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


def main():
    import webview
    run(webview)
