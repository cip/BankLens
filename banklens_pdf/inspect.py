"""Read-only PDF inventory with an explicit allowlist for report fields.

Text extraction runs inside this local process only. Never return strings from
the input, exception messages, filenames, metadata values, or raw parser logs.
This command does NOT anonymize a PDF or certify that a file is safe to share.
"""

from __future__ import annotations

import argparse
import contextlib
import json
import logging
import os
from pathlib import Path
import sys
import warnings

from pypdf import PdfReader


@contextlib.contextmanager
def quiet_parser():
    """Discard library diagnostics, which can include document content."""
    previous_logging_level = logging.root.manager.disable
    with open(os.devnull, "w") as sink, warnings.catch_warnings():
        warnings.simplefilter("ignore")
        logging.disable(logging.CRITICAL)
        try:
            with contextlib.redirect_stdout(sink), contextlib.redirect_stderr(sink):
                yield
        finally:
            logging.disable(previous_logging_level)


def inspect_pdf(path: Path, document_id: str) -> dict:
    base = {"document_id": document_id}
    try:
        with quiet_parser(), path.open("rb") as source:
            reader = PdfReader(source, strict=False)
            if reader.is_encrypted:
                return {**base, "status": "encrypted_skipped"}
            pages = []
            for index, page in enumerate(reader.pages, start=1):
                try:
                    # Keep source text in local memory only; do not persist it.
                    has_text = bool((page.extract_text() or "").strip())
                    state = "text_present" if has_text else "no_extractable_text"
                except Exception:
                    state = "extraction_failed"
                pages.append({"page": index, "text_status": state})
            return {
                **base,
                "status": "inspected",
                "page_count": len(pages),
                "pages": pages,
            }
    except Exception:
        # Never interpolate the exception: parsers may echo source material.
        return {**base, "status": "unreadable"}


def inspect_directory(directory: Path) -> dict:
    if not directory.is_dir():
        raise ValueError("invalid_input_directory")
    # Do not follow file symlinks or recurse into unrelated folders.
    paths = sorted(
        (p for p in directory.iterdir()
         if p.suffix.lower() == ".pdf" and not p.is_symlink() and p.is_file()),
        key=lambda p: p.name,
    )
    documents = [
        inspect_pdf(path, f"document-{index:03d}")
        for index, path in enumerate(paths, start=1)
    ]
    statuses = [p["text_status"] for d in documents for p in d.get("pages", [])]
    return {
        "schema_version": 1,
        "operation": "inspect_only",
        "anonymization_performed": False,
        "document_count": len(documents),
        "summary": {
            "inspected_documents": sum(d["status"] == "inspected" for d in documents),
            "encrypted_skipped": sum(d["status"] == "encrypted_skipped" for d in documents),
            "unreadable_documents": sum(d["status"] == "unreadable" for d in documents),
            "page_count": len(statuses),
            "pages_with_text": statuses.count("text_present"),
            "pages_without_extractable_text": statuses.count("no_extractable_text"),
            "pages_with_extraction_failure": statuses.count("extraction_failed"),
        },
        "documents": documents,
    }


def write_report(report_path: Path, input_directory: Path, report: dict) -> None:
    target = report_path.resolve()
    if target.is_relative_to(input_directory.resolve()):
        raise ValueError("report_must_be_outside_input_directory")
    if target.exists():
        raise ValueError("report_already_exists")
    if target.suffix.lower() != ".json":
        raise ValueError("report_requires_json_extension")
    payload = json.dumps(report, indent=2, ensure_ascii=True) + "\n"
    target.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation prevents overwriting any existing file. Remove a
    # partially written report if serialization/write fails.
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as output:
            output.write(payload)
    except BaseException:
        target.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local PDF inventory; no document text in output.")
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Read-only technical inventory of a PDF directory")
    inspect.add_argument("directory", type=Path)
    inspect.add_argument("--report", type=Path, help="New JSON file outside the input directory")
    preview = commands.add_parser("preview", help="Local browser preview and private redaction plan")
    preview.add_argument("directory", type=Path)
    preview.add_argument("--state-dir", type=Path, default=Path("private/review"))
    preview.add_argument("--port", type=int, default=0)
    preview.add_argument("--session-token", help=argparse.SUPPRESS)
    diagnostic=commands.add_parser("diagnose",help="Read-only aggregate recognition diagnostics; no document text")
    diagnostic.add_argument("directory",type=Path)
    diagnostic.add_argument("--state-dir",type=Path,default=Path("private/review"))
    diagnostic.add_argument("--document",type=int,default=1)
    diagnostic.add_argument("--page",type=int,default=1)
    args = parser.parse_args(argv)
    try:
        if args.command=="diagnose":
            from .diagnostics import diagnose
            print(json.dumps(diagnose(args.directory,args.state_dir,args.document,args.page),indent=2))
            return 0
        if args.command == "preview":
            from .preview import serve
            return serve(args.directory, args.state_dir, args.port, args.session_token)
        report = inspect_directory(args.directory)
        if args.report:
            write_report(args.report, args.directory, report)
        print(json.dumps(report, indent=2, ensure_ascii=True))
        if not report["document_count"]:
            return 2
        if report["summary"]["encrypted_skipped"] or report["summary"]["unreadable_documents"]:
            return 1
        if report["summary"]["pages_with_extraction_failure"]:
            return 1
        return 0
    except Exception:
        print("Pruefung fehlgeschlagen. Eingabeordner und neuen JSON-Ausgabepfad pruefen.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
