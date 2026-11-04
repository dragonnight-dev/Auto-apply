from django.contrib.auth.hashers import check_password, make_password
from django.db import models


class Client(models.Model):
    """A job applicant whose browser runs the Chrome extension."""

    class Action(models.TextChoices):
        IDLE = "no-action"
        SYNCING = "syncing"
        FILLING = "filling"

    email = models.EmailField(unique=True)
    password = models.CharField(max_length=128)
    info = models.JSONField(default=dict, blank=True)
    profile = models.JSONField(default=dict, blank=True)
    resume_path = models.CharField(max_length=512, blank=True)
    resume_text = models.TextField(blank=True)
    enabled = models.BooleanField(default=True)
    channel_name = models.CharField(max_length=255, blank=True)
    current_url = models.URLField(max_length=2048, blank=True)
    action = models.CharField(max_length=16, choices=Action.choices, default=Action.IDLE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["id"]

    @property
    def connected(self) -> bool:
        return bool(self.channel_name)

    def set_password(self, raw: str) -> None:
        self.password = make_password(raw)

    def check_password(self, raw: str) -> bool:
        return check_password(raw, self.password)

    def to_state(self) -> dict:
        return {
            "id": self.id,
            "email": self.email,
            "name": self.profile.get("full_name", ""),
            "enabled": self.enabled,
            "connected": self.connected,
            "url": self.current_url,
            "action": self.action,
        }
