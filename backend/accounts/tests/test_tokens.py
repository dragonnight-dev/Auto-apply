from django.test import SimpleTestCase, override_settings

from accounts.tokens import issue_token, read_token


class TokenTests(SimpleTestCase):
    def test_round_trip(self):
        self.assertEqual(read_token(issue_token("client", 7), "client"), 7)

    def test_rejects_other_role(self):
        self.assertIsNone(read_token(issue_token("client", 7), "boss"))

    def test_rejects_tampering_and_non_strings(self):
        self.assertIsNone(read_token(issue_token("client", 7) + "x", "client"))
        self.assertIsNone(read_token(None, "client"))

    @override_settings(TOKEN_MAX_AGE_SECONDS=-1)
    def test_rejects_expired(self):
        self.assertIsNone(read_token(issue_token("client", 7), "client"))
