from django.test import SimpleTestCase

from automation.dom import DomError, is_http_url, normalize_dom


class DomTests(SimpleTestCase):
    def test_keeps_expected_shape(self):
        dom = normalize_dom({
            "title": " Job ",
            "text": "Build things",
            "fields": [{"selector": "#a", "type": "select", "label": "Country", "required": True,
                        "options": [{"value": "us", "label": "USA"}, {"value": "ca"}, "junk", {}]}],
            "buttons": [{"selector": "#go", "text": "Apply", "type": "submit"}, {"text": "no selector"}],
        })
        self.assertEqual(dom["title"], "Job")
        self.assertEqual(dom["fields"][0]["options"], [{"value": "us", "label": "USA"}, {"value": "ca", "label": "ca"}])
        self.assertTrue(dom["fields"][0]["required"])
        self.assertEqual(len(dom["buttons"]), 1)

    def test_drops_password_hidden_and_malformed_fields(self):
        dom = normalize_dom({"fields": [
            {"selector": "#p", "type": "password"},
            {"selector": "#h", "type": "hidden"},
            {"type": "text"},
            "junk",
        ]})
        self.assertEqual(dom["fields"], [])

    def test_applies_limits(self):
        dom = normalize_dom({"text": "x" * 50000, "fields": [{"selector": "#a", "type": "text"}] * 500})
        self.assertEqual(len(dom["text"]), 20000)
        self.assertEqual(len(dom["fields"]), 200)

    def test_tolerates_wrong_types_and_rejects_non_objects(self):
        self.assertEqual(normalize_dom({"fields": "nope", "buttons": 1, "text": 5})["fields"], [])
        with self.assertRaises(DomError):
            normalize_dom([])

    def test_url_check(self):
        self.assertTrue(is_http_url("https://example.com/job"))
        for bad in ("javascript:alert(1)", "file:///etc/passwd", "chrome://settings", "https://", None,
                    "https://x/" + "a" * 3000):
            self.assertFalse(is_http_url(bad))
