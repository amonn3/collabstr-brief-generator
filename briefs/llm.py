"""Brief generation with Claude.

One structured-output call: the model fills a fixed schema (brief, content
angles, creator criteria), and anything the brand did not tell us becomes a
visible "[TBD: ...]" placeholder instead of an invented fact.
"""

from __future__ import annotations

import os

import anthropic
from django.conf import settings
from pydantic import BaseModel, Field

SYSTEM_PROMPT = """You write creator campaign briefs for brands hiring influencers and UGC creators on Collabstr, a creator marketplace.

From a few inputs you produce three things: the campaign brief, suggested content angles, and criteria for choosing creators. A brand will edit your output and send it to creators, so it must be concrete, short and skimmable: plain sentences, short bullets, no marketing fluff.

What the inputs mean:
- Platform "UGC" means the creator films content the brand posts or runs as ads itself; it is not posted on the creator's own account, so the creator's audience size matters less than on-camera skill and production quality.
- Goal "Awareness" is reach and recall; "Conversions" is clicks, sign-ups or sales; "Content Assets" is footage the brand reuses in its own ads, site and social, so usage rights and raw files matter.
- Tone sets the voice of the content angles and hooks, and the style creators should aim for.

Ground every fact in what the brand told you. For a well-known brand you may use widely known public context, but never specific prices, offers, product specs or claims. When the brief needs a fact the brand did not give (a date, a price, a discount code, a link, a handle, a product claim, usage-rights terms), do not invent it: write a placeholder in the form [TBD: what the brand needs to fill in], for example "[TBD: posting date]" or "[TBD: discount code]". Creative direction (angles, hooks, do's and don'ts, creator criteria) is yours to suggest and needs no placeholder.

Creators are legally responsible for what they say in sponsored posts, so treat the brand's own claims with care. When the brand states something a creator should not repeat as fact without proof (health or medical effects, fuel or energy, safety, performance numbers, "best"/"#1", guaranteed results, or anything physically implausible), do not use it as fact in key messages, angles or hooks. Add a key message like "[TBD: proof or approved wording for the claim that ...]" and a don't telling creators not to state it until the brand provides that.

Turn the brand's input into direction a creator can act on in their own voice; don't paste the brand's sentences back. Write in the same language as the brand's input."""


class ContentAngle(BaseModel):
    name: str = Field(description="2-5 word name of the angle, e.g. 'Morning routine'")
    idea: str = Field(description="One sentence on what the content shows and why it fits the goal")
    hook: str = Field(description="An example opening line for the first 2 seconds, in the requested tone")


class Brief(BaseModel):
    title: str = Field(description="Short campaign name, max 8 words")
    overview: str = Field(description="2-3 sentences: who the brand is and what this collab is about")
    objective: str = Field(description="The single main goal of the content, one sentence, tied to the selected goal")
    target_audience: str = Field(description="Who the content should speak to, one or two sentences")
    key_messages: list[str] = Field(description="3-5 points the content must get across")
    deliverables: list[str] = Field(description="Exact content pieces expected, e.g. '1 TikTok video, 30-45s, vertical'")
    dos: list[str] = Field(description="3-5 creative do's")
    donts: list[str] = Field(description="3-5 creative don'ts")
    usage_rights: str = Field(description="How the brand may reuse the content; placeholder for the terms if unknown")
    content_angles: list[ContentAngle] = Field(description="3 distinct content angles")
    creator_criteria: list[str] = Field(description="4-6 concrete criteria for choosing creators for this campaign")


class BriefGenerationError(Exception):
    """A user-presentable failure."""


_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise BriefGenerationError("AI isn't configured yet: set ANTHROPIC_API_KEY in .env and restart the server.")
    if _client is None:
        _client = anthropic.Anthropic(timeout=90.0, max_retries=2)
    return _client


def _render_input(data: dict) -> str:
    lines = [
        f"Brand: {data['brand_name']}",
        f"Platform: {data['platform']}",
        f"Goal: {data['goal']}",
        f"Tone: {data['tone']}",
        f"What this campaign promotes: {data.get('promoting') or '(not specified - keep it about the brand overall)'}",
    ]
    return "Write the brief, content angles and creator criteria for this campaign.\n\n" + "\n".join(lines)


def generate_brief(data: dict) -> Brief:
    try:
        response = _get_client().beta.messages.parse(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=8000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": _render_input(data)}],
            output_format=Brief,
            # A brief is a short, well-specified task: low effort keeps the wait short.
            output_config={"effort": "low"},
            # If a safety classifier declines, let the API retry on a fallback model.
            betas=["server-side-fallback-2026-07-01"],
            fallbacks="default",
        )
    except anthropic.RateLimitError as exc:
        raise BriefGenerationError("We're getting a lot of requests. Try again in a minute.") from exc
    except anthropic.APIConnectionError as exc:
        raise BriefGenerationError("Couldn't reach the AI service. Try again.") from exc
    except anthropic.APIStatusError as exc:
        raise BriefGenerationError("The AI service returned an error. Try again.") from exc

    if response.stop_reason == "refusal":
        raise BriefGenerationError("This request couldn't be turned into a brief. Try rephrasing it.")
    if response.stop_reason == "max_tokens" or response.parsed_output is None:
        raise BriefGenerationError("The brief came back incomplete. Try again.")
    return response.parsed_output
