import tempfile
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings

from accounts.models import Client
from accounts.tokens import read_token

from .helpers import make_pdf


def resume_file(data=None):
    return SimpleUploadedFile("resume.pdf", data or make_pdf(), content_type="application/pdf")


class ClientAuthTests(TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)
        settings_override = override_settings(RESUME_DIR=self.dir)
        settings_override.enable()
        self.addCleanup(settings_override.disable)
        patcher = patch("accounts.views.build_profile", return_value={"full_name": "Ann Lee"})
        self.build_profile = patcher.start()
        self.addCleanup(patcher.stop)

    def signup(self, **overrides):
        data = {"email": "Ann@Example.com", "password": "long-enough", "phone": "555", "resume": resume_file()}
        data.update(overrides)
        return self.client.post("/api/clients/signup", {k: v for k, v in data.items() if v is not None})

    def test_signup_stores_profile_resume_and_hash(self):
        response = self.signup()
        self.assertEqual(response.status_code, 201)
        client = Client.objects.get(email="ann@example.com")
        self.assertEqual(read_token(response.json()["token"], "client"), client.id)
        self.assertEqual(client.profile, {"full_name": "Ann Lee"})
        self.assertEqual(client.info["phone"], "555")
        self.assertIn("Python developer", client.resume_text)
        self.assertNotEqual(client.password, "long-enough")
        self.assertTrue((self.dir / "ann@example.com.pdf").exists())

    def test_signup_rejects_bad_input(self):
        cases = [
            {"email": "not-an-email"},
            {"email": "../evil@example.com"},
            {"password": "short"},
            {"resume": None},
            {"resume": resume_file(b"not a pdf")},
        ]
        for overrides in cases:
            with self.subTest(overrides=overrides):
                self.assertEqual(self.signup(**overrides).status_code, 400)
        self.assertEqual(Client.objects.count(), 0)
        self.assertEqual(list(self.dir.iterdir()), [])

    def test_duplicate_signup_does_not_replace_the_resume(self):
        self.signup()
        before = (self.dir / "ann@example.com.pdf").read_bytes()
        response = self.signup(resume=resume_file(make_pdf("Attacker")))
        self.assertEqual(response.status_code, 409)
        self.assertEqual((self.dir / "ann@example.com.pdf").read_bytes(), before)

    def test_signin(self):
        self.signup()
        ok = self.client.post("/api/clients/signin", {"email": "ann@example.com", "password": "long-enough"},
                              content_type="application/json")
        self.assertEqual(ok.status_code, 200)
        self.assertIsNotNone(read_token(ok.json()["token"], "client"))
        for body in ({"email": "ann@example.com", "password": "wrong-password"}, {"email": "x@example.com"}, {}):
            bad = self.client.post("/api/clients/signin", body, content_type="application/json")
            self.assertEqual(bad.status_code, 401)


class BossAuthTests(TestCase):
    def signup(self, **overrides):
        body = {"username": "boss", "password": "long-enough", "boss_key": "the-key", **overrides}
        return self.client.post("/api/boss/signup", body, content_type="application/json")

    @override_settings(BOSS_KEY="the-key")
    def test_signup_and_signin_with_boss_key(self):
        response = self.signup()
        self.assertEqual(response.status_code, 201)
        self.assertIsNotNone(read_token(response.json()["token"], "boss"))
        signin = self.client.post("/api/boss/signin", {"username": "boss", "password": "long-enough"},
                                  content_type="application/json")
        self.assertEqual(signin.status_code, 200)

    @override_settings(BOSS_KEY="the-key")
    def test_wrong_key_is_rejected(self):
        self.assertEqual(self.signup(boss_key="wrong").status_code, 403)

    @override_settings(BOSS_KEY="")
    def test_signup_is_closed_when_no_key_is_configured(self):
        self.assertEqual(self.signup(boss_key="").status_code, 403)

    @override_settings(BOSS_KEY="the-key")
    def test_duplicate_and_weak_are_rejected(self):
        self.signup()
        self.assertEqual(self.signup().status_code, 409)
        self.assertEqual(self.signup(username="other", password="short").status_code, 400)

    def test_client_token_does_not_grant_boss_signin(self):
        response = self.client.post("/api/boss/signin", {"username": "nobody", "password": "x"},
                                    content_type="application/json")
        self.assertEqual(response.status_code, 401)
