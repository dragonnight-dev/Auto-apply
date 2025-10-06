from django.test import SimpleTestCase

from accounts.profile import build_profile, rule_based_profile
from slm.client import SLMError


class FakeSLM:
    def __init__(self, result=None, error=False):
        self.result, self.error, self.calls = result, error, 0

    def call_tool(self, *_args):
        self.calls += 1
        if self.error:
            raise SLMError("down")
        return self.result


RESUME = "Ann Lee\nann@example.com +1 555 010 9999\nlinkedin.com/in/annlee\ngithub.com/annlee\nPython developer"


class ProfileTests(SimpleTestCase):
    def test_typed_info_overrides_extraction(self):
        slm = FakeSLM({"full_name": "Wrong", "skills": ["Python"]})
        profile = build_profile({"full_name": "Ann Lee"}, RESUME, slm)
        self.assertEqual(profile["full_name"], "Ann Lee")
        self.assertEqual(profile["skills"], ["Python"])

    def test_drops_unknown_and_mistyped_model_output(self):
        slm = FakeSLM({"full_name": 5, "password": "x", "skills": "Python", "years_experience": 500, "phone": " 1 "})
        self.assertEqual(build_profile({}, RESUME, slm), {"phone": "1"})

    def test_falls_back_to_rules_when_slm_is_down(self):
        profile = build_profile({}, RESUME, FakeSLM(error=True))
        self.assertEqual(profile["full_name"], "Ann Lee")
        self.assertEqual(profile["email"], "ann@example.com")
        self.assertEqual(profile["phone"], "+1 555 010 9999")
        self.assertEqual(profile["github"], "github.com/annlee")

    def test_empty_resume_skips_slm(self):
        slm = FakeSLM({})
        self.assertEqual(build_profile({"email": "a@example.com"}, "", slm), {"email": "a@example.com"})
        self.assertEqual(slm.calls, 0)

    def test_rules_do_not_take_a_contact_line_as_name(self):
        self.assertNotIn("full_name", rule_based_profile("ann@example.com\nAnn Lee"))
