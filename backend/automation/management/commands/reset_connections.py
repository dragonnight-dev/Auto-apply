from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Client
from automation.models import ApplyHistory, ApplySession, FillPlan

ACTIVE = [ApplySession.State.SYNCING, ApplySession.State.PLANNING, ApplySession.State.FILLING]


class Command(BaseCommand):
    help = "Clear state left by the previous server process. Run once before the server starts."

    @transaction.atomic
    def handle(self, *args, **options):
        Client.objects.update(channel_name="", action=Client.Action.IDLE)
        for plan in FillPlan.objects.select_related("session").filter(status=FillPlan.Status.SENT):
            plan.status = FillPlan.Status.FAILED
            plan.save(update_fields=["status"])
            ApplyHistory.objects.create(client_id=plan.client_id, apply_url=plan.session.url,
                                        status=ApplyHistory.Status.FAILED,
                                        results={"error": "Server restarted before results arrived."})
        ApplySession.objects.filter(state__in=ACTIVE).update(state=ApplySession.State.FAILED,
                                                             error="Server restarted.")
