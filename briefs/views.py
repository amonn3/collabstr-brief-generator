import hashlib
import json
import logging
import re
import time

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from datetime import timedelta

from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .llm import BriefGenerationError, generate_brief
from .models import BriefRun

logger = logging.getLogger(__name__)
TBD_RE = re.compile(r"\[TBD:[^\]]*\]")

PLATFORMS = ["Instagram", "TikTok", "UGC"]
GOALS = ["Awareness", "Conversions", "Content Assets"]
TONES = ["Professional", "Friendly", "Playful"]
CHOICES = {"platform": PLATFORMS, "goal": GOALS, "tone": TONES}

LIMITS = {"brand_name": 80, "promoting": 300}
REQUIRED = ["brand_name", "platform", "goal", "tone"]


@require_GET
def index(request):
    choice_groups = [("platform", "Platform", PLATFORMS), ("goal", "Goal", GOALS), ("tone", "Tone", TONES)]
    return render(request, "briefs/index.html", {"choice_groups": choice_groups})


def _clean(payload: dict) -> tuple[dict, dict]:
    data, errors = {}, {}
    for field in REQUIRED + ["promoting"]:
        value = str(payload.get(field, "")).strip()
        limit = LIMITS.get(field)
        if field in REQUIRED and not value:
            errors[field] = "Required."
        elif limit and len(value) > limit:
            errors[field] = f"Keep it under {limit} characters."
        data[field] = value
    for field, options in CHOICES.items():
        if data[field] and data[field] not in options:
            errors[field] = "Pick an option from the list."
    return data, errors


@require_POST
def generate(request):
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        return JsonResponse({"error": "Invalid request."}, status=400)

    data, errors = _clean(payload)
    if errors:
        return JsonResponse({"error": "Check the highlighted fields.", "fields": errors}, status=400)

    client_hash = _client_hash(request)
    limited = _rate_limited(client_hash)
    if limited:
        return JsonResponse({"error": limited}, status=429)

    run = BriefRun(**data, model=settings.ANTHROPIC_MODEL, client_hash=client_hash)
    started = time.monotonic()
    try:
        brief = generate_brief(data)
    except BriefGenerationError as exc:
        run.status, run.error = BriefRun.Status.ERROR, str(exc)[:200]
        _save_run(run, started)
        return JsonResponse({"error": str(exc)}, status=502)

    output = brief.model_dump()
    run.status, run.output = BriefRun.Status.SUCCESS, output
    run.tbd_count = len(TBD_RE.findall(json.dumps(output)))
    _save_run(run, started)
    return JsonResponse({"id": str(run.id), "brief": output})


def _client_hash(request) -> str:
    ip = (request.META.get("HTTP_X_FORWARDED_FOR") or request.META.get("REMOTE_ADDR") or "").split(",")[0].strip()
    return hashlib.sha256(f"{settings.SECRET_KEY}:{ip}".encode()).hexdigest()[:16]


def _rate_limited(client_hash: str) -> str | None:
    """Each generation costs real money, so cap it per visitor and per day. Returns a message when blocked."""
    now = timezone.now()
    recent = BriefRun.objects.filter(client_hash=client_hash, created_at__gte=now - timedelta(hours=1)).count()
    if recent >= settings.BRIEF_LIMIT_PER_HOUR:
        return "You've generated a lot of briefs this hour. Try again later."
    today = BriefRun.objects.filter(created_at__gte=now - timedelta(days=1)).count()
    if today >= settings.BRIEF_LIMIT_PER_DAY:
        return "The demo has hit its daily limit. Try again tomorrow."
    return None


def _save_run(run: BriefRun, started: float) -> None:
    """Analytics must never break the product: log and move on if the write fails."""
    run.latency_ms = int((time.monotonic() - started) * 1000)
    try:
        run.save()
    except Exception:
        logger.exception("Could not record brief run")


@require_POST
def track_copy(request, run_id):
    run = get_object_or_404(BriefRun, pk=run_id, status=BriefRun.Status.SUCCESS)
    try:
        payload = json.loads(request.body or b"{}")
    except json.JSONDecodeError:
        payload = {}
    run.copy_count += 1
    if run.copied_at is None:  # first copy defines the metric; later copies only bump the count
        run.copied_at = timezone.now()
        run.edited_before_copy = bool(payload.get("edited"))
        remaining = payload.get("tbd_remaining")
        run.tbd_remaining_at_copy = remaining if isinstance(remaining, int) and remaining >= 0 else None
    run.save()
    return JsonResponse({"ok": True})
