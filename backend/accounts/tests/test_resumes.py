import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from accounts.resumes import ResumeError, extract_text, resume_path, store_resume

from .helpers import make_pdf


class ResumeTests(SimpleTestCase):
    def test_stores_under_email_name(self):
        with tempfile.TemporaryDirectory() as tmp, override_settings(RESUME_DIR=Path(tmp) / "DB"):
            path = store_resume("ann@example.com", make_pdf())
            self.assertEqual(path, Path(tmp) / "DB" / "ann@example.com.pdf")
            self.assertTrue(path.exists())

    def test_rejects_path_traversal_emails(self):
        for email in ("../../etc/x@example.com", "a/b@example.com", "a\\b@example.com", "a@..", ""):
            with self.subTest(email=email), self.assertRaises(ResumeError):
                resume_path(email)

    def test_rejects_non_pdf_and_oversize(self):
        with self.assertRaises(ResumeError):
            store_resume("ann@example.com", b"MZ not a pdf")
        with override_settings(MAX_RESUME_BYTES=4), self.assertRaises(ResumeError):
            store_resume("ann@example.com", make_pdf())

    def test_extracts_text(self):
        self.assertIn("Python developer", extract_text(make_pdf()))

    def test_damaged_pdf_gives_empty_text(self):
        self.assertEqual(extract_text(b"%PDF-1.4 broken"), "")
