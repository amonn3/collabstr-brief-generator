# Collabstr AI Brief Generator

A brand picks a platform, goal and tone, and gets a creator brief, content angles and creator selection criteria. It can edit the result in place and copy it into an offer.

**Live:** _TBD_ · **Loom:** _TBD_

---

## Lite PRD

**Problem.** Brands often know they want creator content but not how to brief it. A vague brief gives off-target content and costly revision rounds, and it hits small brands briefing for the first time hardest.

**Intended outcome.** A brand goes from four inputs to a brief it would actually send, in under a minute, with the gaps it still needs to fill made obvious.

**Primary success metric: copy rate.** This is the share of successfully generated briefs that get copied. Copying is the hand-off to the next step (an offer or a DM), so it is the best signal that the output was usable and not just interesting. Every generation and copy is logged, and `python manage.py brief_stats` reports the metric.
- Supporting signals: edited-before-copy, the number of `[TBD]`s left at copy, latency and error rate.

**Scope**
- In: the four inputs from the spec, plus one optional "What are you promoting?" field; brief + content angles + creator criteria; editing in place; Copy brief; loading, success, error and empty states; measurement.
- Out: accounts, saved briefs, sending the brief to a creator inside Collabstr, regenerating a single section.

**Assumptions**
- The brand is about to message creators, so plain text it can paste beats a PDF or a share link.
- Brands won't always know the specifics (dates, codes, usage terms) when they start, so the brief should show those gaps instead of guessing.
- Creators are legally responsible for the claims in sponsored posts, so the brief must not put unproven brand claims in their mouth.

## Technical approach

```
jQuery page ── POST /api/briefs/ ──► Django view ──► Claude (structured output) ──► Brief schema
   ▲                                    │  validate · rate-limit · log BriefRun
   └──────── JSON {id, brief} ◄─────────┘
Copy brief ── POST /api/briefs/<id>/copied/ ──► log copy (edited?, [TBD]s left)
```

- **Frontend:** one Django template plus jQuery. It renders the result into a single `contenteditable` document, highlights `[TBD: …]` gaps and counts them live.
- **Backend:** Django 5.2. The view validates the inputs against the exact options in the spec, calls the LLM and records a `BriefRun` row. Postgres (Neon) in production, SQLite locally.
- **LLM:** Claude (`claude-opus-5-5`) through the Anthropic SDK with **structured outputs**. A Pydantic schema (brief fields, 3 content angles with a hook, creator criteria) guarantees a complete, parseable response, so there is no JSON scraping and no half-rendered UI.
- **Prompt decisions:**
  - It defines what UGC, Content Assets and Tone mean for a brief.
  - Missing facts must become `[TBD: …]`, never be invented.
  - Claims that need proof (health, fuel, safety, "best", the physically implausible) are turned into a request for proof plus a matching "don't", instead of a key message.
- **Tradeoff: low effort.** Generation runs at low effort. Measured latency was about 15s per brief, which is good enough for a one-shot task with a clear loading state.

**Reliability & safety**
- Typed SDK errors (rate limit, connection, API) and model refusals each map to a clear message. A truncated output is treated as an error and never rendered.
- Server-side refusal fallback is enabled. Inputs are length-limited and restricted to the allowed options.
- Generations are rate-limited per visitor (salted IP hash, 15 per hour) and capped at 300 per day across the whole demo. Every call spends real money.
- Logging is best-effort: if the analytics write fails, the brief is still returned.
- CSRF is on. In production the app runs with HTTPS-only cookies, and secrets come from env vars.

**Implemented vs. production**
- Implemented: the end-to-end flow, validation, error states, run and copy logging, rate limiting, 13 tests (the LLM is mocked).
- For production I'd add:
  - streaming, so text shows up in about 2s instead of 15s;
  - an eval set of real briefs to tune the prompt against;
  - attaching the brief to an actual Collabstr offer;
  - auth and per-account quotas instead of per-IP limits;
  - error monitoring.

## Design rationale

- **The chosen interaction is editing in place plus Copy brief.** The brief is only useful once the brand fills the gaps and sends it, so the result is a single editable document. The `[TBD]` counter ("3 details to fill in before sending") turns into "Ready to send" as the brand edits. Copy produces clean plain text that pastes anywhere.
- **Pills instead of selects.** Each input has three options, so they're all visible and one click picks one. The Tone pill directly changes the voice of the hooks.
- **Two-column layout.** The inputs stay visible next to the result, so tweaking and regenerating is quick. It stacks to one column on mobile.
- **Design system:** the Inter font, a **black primary CTA**, and pink (`#FB669D`) used only as an accent (the `[TBD]` highlights and the loading spinner), as in Collabstr's design system. Colors are tokens, with a dark mode that follows the OS and can be toggled.

## Validation & iteration

- **What I tested:**
  - unit tests for validation, the rate limit, run and copy logging, and the stats command;
  - the end-to-end flow in a real browser against the live model, including the clipboard contents;
  - adversarial input: a "flying car that runs on water", to check the brief refuses to state those claims as fact.
- **What I'd measure next:**
  - copy rate by goal and by platform;
  - how many `[TBD]`s are left at copy;
  - which sections brands edit most, a sign of where the model is weakest.
- **Next steps:**
  - regenerate a single section;
  - pre-fill brand context from the brand's Collabstr profile;
  - send the brief straight into a Collabstr offer, which would let us measure creator outcomes (fewer revision requests).

## Use of AI tools

Built with Claude Code as a pair programmer: scaffolding, the prompt and schema, the front end, the tests and the deploy. I reviewed and checked the output myself:
- I tried the flow in the browser. That caught a jQuery SRI hash that silently broke all JS, and cross-section text selection that didn't work.
- I read generated briefs critically. That led to the claim-safety rule in the prompt.
- I aligned the inputs and outputs with the spec.

## Run locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env              # set ANTHROPIC_API_KEY (platform.claude.com → API Keys)
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
.venv/bin/python manage.py test briefs
.venv/bin/python manage.py brief_stats   # funnel + copy rate
```

Production settings come from env vars: `DATABASE_URL`, `ANTHROPIC_API_KEY`, `DJANGO_SECRET_KEY`, `DJANGO_DEBUG=0`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`.
