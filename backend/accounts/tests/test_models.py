from django.test import TestCase

from accounts.models import Client


class ClientModelTests(TestCase):
    def test_password_is_hashed(self):
        client = Client(email="a@example.com")
        client.set_password("s3cret-pass")
        self.assertNotIn("s3cret-pass", client.password)
        self.assertTrue(client.check_password("s3cret-pass"))
        self.assertFalse(client.check_password("wrong"))

    def test_state_never_exposes_secrets(self):
        client = Client.objects.create(email="a@example.com", password="hash", profile={"full_name": "Ann"})
        state = client.to_state()
        self.assertEqual(state["name"], "Ann")
        self.assertFalse(state["connected"])
        self.assertNotIn("password", state)
