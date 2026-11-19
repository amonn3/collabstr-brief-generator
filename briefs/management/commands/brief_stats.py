from statistics import median

from django.core.management.base import BaseCommand

from briefs.models import BriefRun


class Command(BaseCommand):
    help = "Print the brief generator's funnel: runs, success rate, copy rate (primary metric), latency."

    def handle(self, *args, **options):
        runs = list(BriefRun.objects.all())
        ok = [r for r in runs if r.status == BriefRun.Status.SUCCESS]
        copied = [r for r in ok if r.copied_at]

        def pct(n, d):
            return f"{100 * n / d:.0f}%" if d else "n/a"

        self.stdout.write(f"Runs:              {len(runs)}")
        self.stdout.write(f"Success rate:      {pct(len(ok), len(runs))}")
        self.stdout.write(f"Copy rate:         {pct(len(copied), len(ok))}   <- primary metric")
        self.stdout.write(f"Edited before copy:{pct(sum(1 for r in copied if r.edited_before_copy), len(copied)):>5}")
        if ok:
            self.stdout.write(f"Median latency:    {median(r.latency_ms for r in ok) / 1000:.1f}s")
            self.stdout.write(f"Median [TBD]s:     {median(r.tbd_count or 0 for r in ok)} generated")
        if copied:
            self.stdout.write(f"Median [TBD]s left at copy: {median(r.tbd_remaining_at_copy or 0 for r in copied)}")
        for goal in ("Awareness", "Conversions", "Content Assets"):
            g_ok = [r for r in ok if r.goal == goal]
            if g_ok:
                self.stdout.write(f"  {goal:<15} copy rate {pct(sum(1 for r in g_ok if r.copied_at), len(g_ok))} (n={len(g_ok)})")
