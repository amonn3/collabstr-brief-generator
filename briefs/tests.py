import json
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.test import TestCase

from .llm import Brief, BriefGenerationError, ContentAngle
from .models import BriefRun

VALID = {
    "brand_name": "Glow Botanics",
    "platform": "TikTok",
    "goal": "Conversions",
    "tone": "Friendly",
    "promoting": "",
}

SAMPLE = Brief(
    title="Glow Morning Routine",
    overview="o", objective="o", target_audience="a",
    key_messages=["k"], deliverables=["1 TikTok"], dos=["d"], donts=["n"],
    usage_rights="[TBD: usage terms]",
    content_angles=[ContentAngle(name="Morning routine", idea="i", hook="h")],
    creator_criteria=["Skincare niche"],
)


class GenerateViewTests(TestCase):
    def post(self, payload):
        return self.client.post("/api/briefs/", json.dumps(payload), content_type="application/json")

    def test_index_renders(self):
        self.assertContains(self.client.get("/"), "Generate brief")

    def test_missing_fields_are_reported(self):
        res = self.post({"brand_name": ""})
        self.assertEqual(res.status_code, 400)
        self.assertIn("brand_name", res.json()["fields"])
        self.assertIn("platform", res.json()["fields"])
        self.assertIn("tone", res.json()["fields"])

    def test_options_outside_the_spec_are_rejected(self):
        for field, bad in [("platform", "YouTube"), ("goal", "Drive sales"), ("tone", "Edgy")]:
            res = self.post({**VALID, field: bad})
            self.assertEqual(res.status_code, 400)
            self.assertIn(field, res.json()["fields"])

    def test_brand_name_length_limit(self):
        res = self.post({**VALID, "brand_name": "x" * 81})
        self.assertEqual(res.status_code, 400)

    @patch("briefs.views.generate_brief", return_value=SAMPLE)
    def test_success_returns_brief(self, mock_gen):
        res = self.post(VALID)
        self.assertEqual(res.status_code, 200)
        brief = res.json()["brief"]
        self.assertEqual(brief["title"], "Glow Morning Routine")
        self.assertEqual(brief["content_angles"][0]["name"], "Morning routine")
        self.assertEqual(brief["creator_criteria"], ["Skincare niche"])
        mock_gen.assert_called_once()
        run = BriefRun.objects.get(pk=res.json()["id"])
        self.assertEqual(run.status, "success")
        self.assertEqual((run.brand_name, run.goal, run.tone), ("Glow Botanics", "Conversions", "Friendly"))
        self.assertEqual(run.tbd_count, 1)

    @patch.dict("os.environ", {"ANTHROPIC_API_KEY": "", "ANTHROPIC_AUTH_TOKEN": ""})
    def test_missing_api_key_gives_clear_error(self):
        res = self.post(VALID)
        self.assertEqual(res.status_code, 502)
        self.assertIn("ANTHROPIC_API_KEY", res.json()["error"])

    @patch("briefs.views.generate_brief", side_effect=BriefGenerationError("Try again."))
    def test_llm_failure_is_502_with_message(self, _):
        res = self.post(VALID)
        self.assertEqual(res.status_code, 502)
        self.assertEqual(res.json()["error"], "Try again.")
        run = BriefRun.objects.get()
        self.assertEqual((run.status, run.error), ("error", "Try again."))

    @patch("briefs.views.generate_brief", return_value=SAMPLE)
    def test_rate_limit_per_visitor(self, _):
        with self.settings(BRIEF_LIMIT_PER_HOUR=2):
            self.assertEqual(self.post(VALID).status_code, 200)
            self.assertEqual(self.post(VALID).status_code, 200)
            res = self.post(VALID)
        self.assertEqual(res.status_code, 429)
        self.assertEqual(BriefRun.objects.count(), 2)

    def test_invalid_input_is_not_recorded(self):
        self.post({"brand_name": ""})
        self.assertEqual(BriefRun.objects.count(), 0)


class CopyTrackingTests(TestCase):
    def make_run(self, **kw):
        defaults = dict(brand_name="B", platform="TikTok", goal="Awareness", tone="Playful",
                        status="success", model="m", latency_ms=1000, tbd_count=5)
        return BriefRun.objects.create(**{**defaults, **kw})

    def copy(self, run, payload):
        return self.client.post(f"/api/briefs/{run.id}/copied/", json.dumps(payload), content_type="application/json")

    def test_first_copy_sets_metric_fields_later_copies_only_count(self):
        run = self.make_run()
        self.assertEqual(self.copy(run, {"edited": True, "tbd_remaining": 2}).status_code, 200)
        self.copy(run, {"edited": False, "tbd_remaining": 0})
        run.refresh_from_db()
        self.assertIsNotNone(run.copied_at)
        self.assertEqual((run.copy_count, run.edited_before_copy, run.tbd_remaining_at_copy), (2, True, 2))

    def test_bad_tbd_value_is_ignored(self):
        run = self.make_run()
        self.copy(run, {"tbd_remaining": "lots"})
        run.refresh_from_db()
        self.assertIsNone(run.tbd_remaining_at_copy)

    def test_cannot_copy_a_failed_run(self):
        run = self.make_run(status="error")
        self.assertEqual(self.copy(run, {}).status_code, 404)

    def test_stats_report_copy_rate(self):
        copied = self.make_run()
        self.copy(copied, {"edited": True, "tbd_remaining": 0})
        self.make_run()
        self.make_run(status="error")
        out = StringIO()
        call_command("brief_stats", stdout=out)
        self.assertIn("Copy rate:         50%", out.getvalue())
        self.assertIn("Success rate:      67%", out.getvalue())
