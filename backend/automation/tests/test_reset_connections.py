from django.core.management import call_command
from django.test import TestCase

from accounts.models import Client
from automation.models import ApplyHistory, ApplySession, FillPlan


class ResetConnectionsTests(TestCase):
    def test_clears_state_from_a_previous_process(self):
        client = Client.objects.create(email="a@example.com", password="x", channel_name="stale", action="filling")
        filling = ApplySession.objects.create(url="https://x.example/1", state="filling")
        done = ApplySession.objects.create(url="https://x.example/2", state="done")
        FillPlan.objects.create(session=filling, client=client, status="sent")

        call_command("reset_connections")

        client.refresh_from_db()
        filling.refresh_from_db()
        done.refresh_from_db()
        self.assertFalse(client.connected)
        self.assertEqual(client.action, "no-action")
        self.assertEqual(filling.state, "failed")
        self.assertEqual(done.state, "done")
        self.assertEqual(ApplyHistory.objects.get().status, "failed")
