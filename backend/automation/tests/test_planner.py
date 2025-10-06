from django.test import SimpleTestCase, override_settings

from automation.dom import normalize_dom
from automation.planner import build_plan
from slm.client import SLMError

PROFILE = {"full_name": "Ann Marie Lee", "email": "ann@example.com", "phone": "555-0100",
           "linkedin": "linkedin.com/in/ann", "skills": ["Python"]}


class FakeSLM:
    def __init__(self, answers=None, text="I build Python services.", error=False):
        self.answers, self.text, self.error = answers or [], text, error
        self.tool_prompts, self.complete_prompts = [], []

    def call_tool(self, _system, user, *_args):
        self.tool_prompts.append(user)
        if self.error:
            raise SLMError("down")
        return {"answers": self.answers}

    def complete(self, _system, user):
        self.complete_prompts.append(user)
        if self.error:
            raise SLMError("down")
        return self.text


def page(*fields, text="Job description", buttons=()):
    return normalize_dom({"text": text, "fields": list(fields), "buttons": list(buttons)})


def field(selector, kind="text", label="", **extra):
    return {"selector": selector, "type": kind, "label": label, **extra}


def by_selector(items):
    return {item["selector"]: item for item in items}


class RuleTests(SimpleTestCase):
    def test_contact_fields_use_rules_not_slm(self):
        slm = FakeSLM()
        plan = build_plan(page(field("#f", label="First Name"), field("#l", "text", "Last name"),
                               field("#n", label="Full name"), field("#e", "email", "Email address"),
                               field("#p", "tel", "Phone"), field("#i", name="linkedin_url")), PROFILE, slm)
        values = {a["selector"]: a["value"] for a in plan["actions"]}
        self.assertEqual(values, {"#f": "Ann", "#l": "Lee", "#n": "Ann Marie Lee", "#e": "ann@example.com",
                                  "#p": "555-0100", "#i": "linkedin.com/in/ann"})
        self.assertEqual(slm.tool_prompts, [])

    def test_label_outranks_name_attribute(self):
        plan = build_plan(page(field("#p", label="Phone", name="contact_email")), PROFILE, FakeSLM())
        self.assertEqual(plan["actions"][0]["value"], "555-0100")


class SafetyTests(SimpleTestCase):
    def test_sensitive_and_attestation_fields_are_never_answered(self):
        slm = FakeSLM(answers=[{"field_id": 0, "value": "Yes"}])
        fields = [field("#g", "select", "Gender", options=[{"value": "f", "label": "Female"}]),
                  field("#v", "radio", "Are you a veteran?", options=[{"selector": "#v1", "label": "No"}]),
                  field("#d", label="Date of birth"),
                  field("#t", "checkbox", "I agree to the terms")]
        plan = build_plan(page(*fields), PROFILE, slm)
        self.assertEqual(plan["actions"], [])
        reasons = {s["selector"]: s["reason"] for s in plan["skipped"]}
        self.assertEqual(reasons, {"#g": "sensitive", "#v": "sensitive", "#d": "sensitive", "#t": "needs_person"})
        self.assertEqual(slm.tool_prompts, [])

    def test_word_containing_race_is_not_sensitive(self):
        slm = FakeSLM(answers=[{"field_id": 0, "value": "Yes"}])
        plan = build_plan(page(field("#a", label="Do you embrace remote work?")), PROFILE, slm)
        self.assertEqual(plan["actions"][0]["value"], "Yes")


class SlmAnswerTests(SimpleTestCase):
    def test_select_answer_must_be_a_listed_option(self):
        options = [{"value": "us", "label": "United States"}]
        slm = FakeSLM(answers=[{"field_id": 0, "value": "united states"}, {"field_id": 1, "value": "Mars"}])
        plan = build_plan(page(field("#a", "select", "Country", options=options),
                               field("#b", "select", "Country of work", options=options)), PROFILE, slm)
        self.assertEqual(by_selector(plan["actions"])["#a"]["value"], "us")
        self.assertEqual(by_selector(plan["skipped"])["#b"]["reason"], "no_answer")

    def test_radio_clicks_the_chosen_option(self):
        options = [{"selector": "#y", "label": "Yes"}, {"selector": "#n", "label": "No"}]
        plan = build_plan(page(field("#r", "radio", "Remote?", options=options)), PROFILE,
                          FakeSLM(answers=[{"field_id": 0, "value": "No"}]))
        self.assertEqual(plan["actions"][0]["op"], "check")
        self.assertEqual(plan["actions"][0]["selector"], "#n")

    def test_unknown_field_ids_and_bad_values_are_ignored(self):
        slm = FakeSLM(answers=[{"field_id": 99, "value": "x"}, {"field_id": "0", "value": "y"}, "junk",
                               {"field_id": 0, "value": "ten"}, {"field_id": 1, "value": "10/06/2025"}])
        plan = build_plan(page(field("#a", "number", "Years"), field("#b", "date", "Start")), PROFILE, slm)
        self.assertEqual(plan["actions"], [])
        self.assertEqual(len(plan["skipped"]), 2)

    def test_slm_outage_skips_fields_but_keeps_rule_results(self):
        plan = build_plan(page(field("#e", "email", "Email"), field("#q", label="Notice period"),
                               field("#w", "textarea", "Why us?")), PROFILE, FakeSLM(error=True))
        self.assertEqual([a["selector"] for a in plan["actions"]], ["#e"])
        self.assertEqual({s["reason"] for s in plan["skipped"]}, {"slm_unavailable"})

    def test_long_answers(self):
        slm = FakeSLM()
        plan = build_plan(page(field("#w", "textarea", "Why this role?"), text="Python role"), PROFILE, slm)
        self.assertEqual(plan["actions"][0]["value"], "I build Python services.")
        self.assertIn("Python role", slm.complete_prompts[0])
        self.assertIn("Why this role?", slm.complete_prompts[0])

    def test_model_can_decline_a_long_answer(self):
        plan = build_plan(page(field("#w", "textarea", "Clearance level?")), PROFILE, FakeSLM(text="UNKNOWN."))
        self.assertEqual(plan["actions"], [])
        self.assertEqual(plan["skipped"][0]["reason"], "no_answer")


class FileAndButtonTests(SimpleTestCase):
    def test_upload_targets_the_resume_input(self):
        plan = build_plan(page(field("#c", "file", "Cover letter"), field("#r", "file", "Resume/CV")), PROFILE,
                          FakeSLM())
        self.assertEqual([(a["op"], a["selector"]) for a in plan["actions"]], [("upload", "#r")])
        self.assertEqual(plan["skipped"][0]["reason"], "unsupported_file")

    def test_single_unlabelled_file_input_is_the_resume(self):
        plan = build_plan(page(field("#x", "file", "Attach")), PROFILE, FakeSLM())
        self.assertEqual(plan["actions"][0]["op"], "upload")

    def test_single_cover_letter_input_is_not_the_resume(self):
        plan = build_plan(page(field("#x", "file", "Cover letter")), PROFILE, FakeSLM())
        self.assertEqual(plan["actions"], [])

    def test_submit_is_not_clicked_by_default(self):
        plan = build_plan(page(buttons=[{"selector": "#s", "text": "Submit", "type": "submit"}]), PROFILE, FakeSLM())
        self.assertEqual(plan["actions"], [])

    @override_settings(AUTO_CLICK_SUBMIT=True)
    def test_submit_is_clicked_only_when_enabled(self):
        plan = build_plan(page(buttons=[{"selector": "#b", "text": "Back", "type": "button"},
                                        {"selector": "#s", "text": "Apply now", "type": "button"}]), PROFILE,
                          FakeSLM())
        self.assertEqual([(a["op"], a["selector"]) for a in plan["actions"]], [("click", "#s")])
