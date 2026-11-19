import uuid

from django.db import models


class BriefRun(models.Model):
    """One generation attempt. Enough to compute the primary metric (copy rate) and spot quality/latency issues."""

    class Status(models.TextChoices):
        SUCCESS = "success"
        ERROR = "error"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # Inputs
    brand_name = models.CharField(max_length=80)
    platform = models.CharField(max_length=20)
    goal = models.CharField(max_length=20)
    tone = models.CharField(max_length=20)
    promoting = models.CharField(max_length=300, blank=True)
    client_hash = models.CharField(max_length=16, blank=True, db_index=True)  # salted IP hash, for rate limiting only

    # Generation outcome
    status = models.CharField(max_length=10, choices=Status.choices)
    error = models.CharField(max_length=200, blank=True)
    model = models.CharField(max_length=60)
    latency_ms = models.PositiveIntegerField()
    output = models.JSONField(null=True, blank=True)
    tbd_count = models.PositiveIntegerField(null=True)

    # What the brand did next: the primary metric is "share of successful runs that get copied".
    copied_at = models.DateTimeField(null=True, blank=True)
    copy_count = models.PositiveIntegerField(default=0)
    edited_before_copy = models.BooleanField(null=True)
    tbd_remaining_at_copy = models.PositiveIntegerField(null=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.brand_name} / {self.platform} / {self.status}"
