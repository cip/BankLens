from permissions import assert_private
import contextlib
import io
import json
import logging
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from banklens_pdf.inspect import inspect_directory, inspect_pdf, main, write_report


SECRET = "PRIVATE_SENTINEL_DO_NOT_OUTPUT"


class Page:
    def __init__(self, text=None, broken=False):
        self.text = text
        self.broken = broken

    def extract_text(self):
        print(SECRET)
        logging.getLogger("pypdf").error(SECRET)
        if self.broken:
            raise ValueError(SECRET)
        return self.text


class Reader:
    is_encrypted = False
    pages = [Page(SECRET), Page(""), Page(broken=True)]


class InspectTests(unittest.TestCase):
    def test_content_names_and_parser_logs_are_absent(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            (directory / (SECRET + ".pdf")).write_bytes(b"dummy")
            stdout, stderr = io.StringIO(), io.StringIO()
            with patch("banklens_pdf.inspect.PdfReader", return_value=Reader()), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                result = main(["inspect", folder])
            self.assertEqual(result, 1)  # page extraction failure is actionable
            self.assertNotIn(SECRET, stdout.getvalue() + stderr.getvalue())
            report = json.loads(stdout.getvalue())
            self.assertEqual(report["summary"]["pages_with_text"], 1)
            self.assertEqual(report["summary"]["pages_without_extractable_text"], 1)
            self.assertEqual(report["summary"]["pages_with_extraction_failure"], 1)
            self.assertFalse(report["anonymization_performed"])

    def test_unreadable_exception_is_not_returned(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.pdf"
            source.write_bytes(b"synthetic")
            with patch("banklens_pdf.inspect.PdfReader", side_effect=ValueError(SECRET)) as reader:
                result = inspect_pdf(source, "document-001")
                reader.assert_called_once()
        self.assertEqual(result, {"document_id": "document-001", "status": "unreadable"})

    def test_encrypted_file_is_skipped_without_accessing_pages(self):
        class Locked:
            is_encrypted = True

            @property
            def pages(self):
                raise AssertionError("Encrypted pages must not be accessed")

        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source.pdf"
            source.write_bytes(b"synthetic")
            with patch("banklens_pdf.inspect.PdfReader", return_value=Locked()) as reader:
                self.assertEqual(inspect_pdf(source, "document-001")["status"], "encrypted_skipped")
                reader.assert_called_once()

    def test_reports_cannot_overwrite_or_enter_input_directory(self):
        with tempfile.TemporaryDirectory() as folder:
            source = Path(folder) / "source"
            source.mkdir()
            with self.assertRaises(ValueError):
                write_report(source / "report.json", source, {})
            target = Path(folder) / "report.json"
            write_report(target, source, {"safe": True})
            assert_private(self, target)
            with self.assertRaises(ValueError):
                write_report(target, source, {})
            self.assertEqual(json.loads(target.read_text()), {"safe": True})

    def test_symlinks_and_nested_files_are_ignored(self):
        with tempfile.TemporaryDirectory() as folder:
            directory = Path(folder)
            original = directory / "original.PDF"
            original.write_bytes(b"dummy")
            (directory / "._original.PDF").write_bytes(b'\x00\x05\x16\x07' + bytes(32))
            (directory / "link.pdf").symlink_to(original)
            nested = directory / "nested"
            nested.mkdir()
            (nested / "hidden.pdf").write_bytes(b"dummy")
            with patch("banklens_pdf.inspect.PdfReader", return_value=Reader()):
                report = inspect_directory(directory)
            self.assertEqual(report["document_count"], 1)
            self.assertEqual(original.read_bytes(), b"dummy")


if __name__ == "__main__":
    unittest.main()
