import tempfile
from pathlib import Path

from django.test import SimpleTestCase, override_settings

from accounts.resumes import extract_text
from automation.tailor import adds_no_numbers, tailor_resume
from slm.client import SLMError

SOURCE = "Ann Lee. Python developer at Acme from 2019 to 2024. Reduced latency by 40 percent."
GOOD = "Ann Lee & co. " + "Python developer at Acme from 2019 to 2024. Reduced latency by 40 percent. " * 4


class FakeSLM:
    def __init__(self, text=GOOD, error=False):
        self.text, self.error = text, error

    def complete(self, *_args):
        if self.error:
            raise SLMError("down")
        return self.text


class TailorTests(SimpleTestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        override = override_settings(RESUME_DIR=Path(tmp.name), TAILOR_RESUME=True)
        override.enable()
        self.addCleanup(override.disable)
        self.dir = Path(tmp.name)

    def run_tailor(self, slm, email="ann@example.com", source=SOURCE, job="Python role"):
        return tailor_resume(email, source, job, 3, slm)

    def test_writes_a_readable_pdf_for_the_session(self):
        path = self.run_tailor(FakeSLM())
        self.assertEqual(path, self.dir / "tailored" / "3" / "ann@example.com.pdf")
        self.assertIn("Reduced latency", extract_text(path.read_bytes()))

    def test_rejects_invented_numbers(self):
        self.assertFalse(adds_no_numbers("Reduced latency by 95 percent", SOURCE))
        self.assertTrue(adds_no_numbers("From 2019 to 2024", SOURCE))
        self.assertIsNone(self.run_tailor(FakeSLM(GOOD + " Led a team of 12.")))

    def test_rejects_short_output_and_outage(self):
        self.assertIsNone(self.run_tailor(FakeSLM("Too short")))
        self.assertIsNone(self.run_tailor(FakeSLM(error=True)))

    def test_skips_without_inputs_or_when_disabled(self):
        self.assertIsNone(self.run_tailor(FakeSLM(), source=""))
        self.assertIsNone(self.run_tailor(FakeSLM(), job=""))
        with override_settings(TAILOR_RESUME=False):
            self.assertIsNone(self.run_tailor(FakeSLM()))
