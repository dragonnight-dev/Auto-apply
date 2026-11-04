from django.db import models
from django.utils import timezone

from accounts.models import Client


class ApplySession(models.Model):
    """One job URL being pushed to all enabled clients."""

    class State(models.TextChoices):
        SYNCING = "syncing"
        PLANNING = "planning"
        READY = "ready"
        FILLING = "filling"
        DONE = "done"
        FAILED = "failed"

    url = models.URLField(max_length=2048)
    source_client = models.ForeignKey(Client, null=True, on_delete=models.SET_NULL, related_name="+")
    state = models.CharField(max_length=16, choices=State.choices, default=State.SYNCING)
    dom = models.JSONField(default=dict, blank=True)
    error = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class FillPlan(models.Model):
    """The auto-fill data generated for one client on one session's page."""

    class Status(models.TextChoices):
        READY = "ready"
        SENT = "sent"
        DONE = "done"
        FAILED = "failed"

    session = models.ForeignKey(ApplySession, on_delete=models.CASCADE, related_name="plans")
    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="plans")
    actions = models.JSONField(default=list, blank=True)
    skipped = models.JSONField(default=list, blank=True)
    resume_file = models.CharField(max_length=512, blank=True)
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.READY)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["session", "client"], name="one_plan_per_client")]


class ApplyHistory(models.Model):
    """What happened when a plan ran. "filled" means the fields were set, not that a job was applied to."""

    class Status(models.TextChoices):
        FILLED = "filled"
        PARTIAL = "partial"
        FAILED = "failed"

    client = models.ForeignKey(Client, on_delete=models.CASCADE, related_name="history")
    apply_url = models.URLField(max_length=2048)
    time = models.DateTimeField(default=timezone.now)
    status = models.CharField(max_length=16, choices=Status.choices)
    results = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-time", "-id"]
