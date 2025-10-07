from django.contrib.auth import get_user_model
from django.test import TestCase

from accounts.models import Client
from accounts.tokens import issue_token
from automation.models import ApplyHistory


class ManagementApiTests(TestCase):
    def setUp(self):
        boss = get_user_model().objects.create_user(username="boss", password="x", is_staff=True)
        self.auth = {"HTTP_AUTHORIZATION": f"Bearer {issue_token('boss', boss.id)}"}
        self.ann = Client.objects.create(email="a@example.com", password="x")
        self.bob = Client.objects.create(email="b@example.com", password="x")
        self.row = ApplyHistory.objects.create(client=self.ann, apply_url="https://x.example/1", status="filled")
        ApplyHistory.objects.create(client=self.ann, apply_url="https://x.example/2", status="failed")
        ApplyHistory.objects.create(client=self.bob, apply_url="https://x.example/3", status="partial")

    def test_every_endpoint_requires_a_boss_token(self):
        client_auth = {"HTTP_AUTHORIZATION": f"Bearer {issue_token('client', self.ann.id)}"}
        for headers in ({}, client_auth):
            self.assertEqual(self.client.get("/api/history", **headers).status_code, 401)
            self.assertEqual(self.client.get("/api/stats", **headers).status_code, 401)
            self.assertEqual(self.client.delete(f"/api/history/{self.row.id}", **headers).status_code, 401)
            self.assertEqual(self.client.patch(f"/api/clients/{self.ann.id}", {"enabled": False},
                                               content_type="application/json", **headers).status_code, 401)
        self.assertEqual(ApplyHistory.objects.count(), 3)

    def test_enable_and_disable_client(self):
        response = self.client.patch(f"/api/clients/{self.ann.id}", {"enabled": False},
                                     content_type="application/json", **self.auth)
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.json()["enabled"])
        self.ann.refresh_from_db()
        self.assertFalse(self.ann.enabled)

    def test_enable_validates_input_and_id(self):
        bad = self.client.patch(f"/api/clients/{self.ann.id}", {"enabled": "no"}, content_type="application/json",
                                **self.auth)
        self.assertEqual(bad.status_code, 400)
        missing = self.client.patch("/api/clients/9999", {"enabled": True}, content_type="application/json",
                                    **self.auth)
        self.assertEqual(missing.status_code, 404)

    def test_list_history_all_and_by_client(self):
        self.assertEqual(len(self.client.get("/api/history", **self.auth).json()["history"]), 3)
        rows = self.client.get(f"/api/history?client={self.bob.id}", **self.auth).json()["history"]
        self.assertEqual([r["url"] for r in rows], ["https://x.example/3"])
        self.assertEqual(self.client.get("/api/history?client=abc", **self.auth).status_code, 400)

    def test_delete_one_history_entry(self):
        self.assertEqual(self.client.delete(f"/api/history/{self.row.id}", **self.auth).status_code, 204)
        self.assertEqual(ApplyHistory.objects.count(), 2)
        self.assertEqual(self.client.delete(f"/api/history/{self.row.id}", **self.auth).status_code, 404)

    def test_clear_requires_a_client(self):
        self.assertEqual(self.client.delete("/api/history", **self.auth).status_code, 400)
        self.assertEqual(ApplyHistory.objects.count(), 3)
        self.assertEqual(self.client.delete(f"/api/history?client={self.ann.id}", **self.auth).status_code, 204)
        self.assertEqual(ApplyHistory.objects.count(), 1)

    def test_statistics_per_client(self):
        rows = {r["email"]: r for r in self.client.get("/api/stats", **self.auth).json()["clients"]}
        self.assertEqual(rows["a@example.com"]["total"], 2)
        self.assertEqual(rows["a@example.com"]["filled"], 1)
        self.assertEqual(rows["a@example.com"]["failed"], 1)
        self.assertEqual(rows["b@example.com"]["partial"], 1)
