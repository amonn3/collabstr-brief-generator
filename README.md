# Collabstr AI Brief Generator

A brand fills in a short form about its campaign and gets a creator brief it can edit in place and copy to send to creators.

**Live demo:** _TBD_ · **Loom:** _TBD_

## Lite PRD

**Problem.** Brands on Collabstr often hire creators with a vague one-liner. Creators then guess, deliver off-brief content, and both sides lose time on revisions. Writing a good brief is tedious, especially for small brands doing it for the first time.

**User.** A small or mid-size brand about to send an offer to one or more creators.

**Goal.** Go from "I want creators to promote X" to a send-ready brief in under a minute.

**What it does**
- Five inputs: brand name, what the brand does, what's being promoted (optional), platform, goal, plus optional notes.
- Generates a structured brief: overview, objective, audience, key messages, deliverables, do's and don'ts, hashtags, timeline and usage rights.
- **No made-up facts.** Anything the brand didn't give (dates, codes, handles, usage terms) shows up as a highlighted `[TBD: …]`. A counter shows how many details are still missing.
- Every section can be edited in place, and **Copy brief** copies clean plain text, ready to paste into a Collabstr offer or a DM.

**Success metrics (if shipped):** share of offers sent with a brief, the copy rate of generated briefs, and the revision requests per collab.

**Out of scope / next steps**
- Regenerate a single section, or adjust the tone.
- Save briefs to the brand's account and attach them to an offer directly.
- Pre-fill the brand info from the brand's Collabstr profile or website.

## Tech

- Django 5.2 + jQuery, with no database: briefs live in the browser until they're copied.
- Claude (`claude-opus-5-5`) through the Anthropic SDK with **structured outputs**: a Pydantic schema guarantees the response has every section in the right shape. The call runs at low effort to keep the wait short, and server-side refusal fallback is enabled.
- Styling follows Collabstr's design system: the Inter font, a black primary CTA, and pink as an accent only.

## Run locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env   # set ANTHROPIC_API_KEY
.venv/bin/python manage.py runserver
.venv/bin/python manage.py test briefs
```

Production: `gunicorn config.wsgi` with `DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS` and `ANTHROPIC_API_KEY` set, after `collectstatic`.
