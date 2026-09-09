"""Phase 3 - LLM extraction with strict structured outputs.

Uses Groq via Instructor to coerce the model into the CompanyIntel Pydantic
schema (tool/function calling under the hood), merges regex-harvested emails as
ground truth, computes a blended confidence score, and reports token usage/cost.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import instructor
from groq import Groq

from .clean import CleanedContent
from .config import Settings, settings as default_settings
from .models import CompanyIntel

SYSTEM_PROMPT = """You are a precise B2B company-intelligence extraction engine.
Extract structured facts ONLY from the website content provided by the user.

Rules:
- overview: a concise summary of what the company does, ideally two sentences.
- target_audience: the ideal customer profile / who the product is built for
  (e.g. "Developers building backend applications").
- contact_emails: only generic/public emails that literally appear in the content
  (contact@, sales@, support@, info@, etc.). Never invent an address.
- team_members: key leadership / notable team members mentioned in the content,
  with name, role/title, and a LinkedIn URL ONLY if it appears in the content.
  Never fabricate names, titles, or LinkedIn URLs.
- confidence_score: your own 0.0-1.0 estimate of how complete/reliable this data is.
- If a field is not supported by the content, leave it null or empty. Do not guess."""

# Groq pricing (USD per 1M tokens) for openai/gpt-oss-120b (approx, for the
# diagnostic estimate only).
_PRICE_IN_PER_M = 0.15
_PRICE_OUT_PER_M = 0.75


@dataclass
class Extraction:
    intel: CompanyIntel
    usage_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None


def _heuristic_confidence(intel: CompanyIntel) -> float:
    """Completeness-based score from which fields the extraction actually filled."""
    score = 0.0
    if intel.overview and len(intel.overview.strip()) > 20:
        score += 0.30
    if intel.target_audience and len(intel.target_audience.strip()) > 5:
        score += 0.25
    if intel.contact_emails:
        score += 0.20
    if intel.team_members:
        score += 0.15
        # Reward leadership entries that carry a LinkedIn URL.
        if any(m.linkedin_url for m in intel.team_members):
            score += 0.10
    return round(min(score, 1.0), 2)


def extract_intel(ctx: CleanedContent, cfg: Settings = default_settings) -> Extraction:
    """Run structured LLM extraction over the cleaned site context."""
    # Nothing to work with: skip the LLM call, return an empty low-confidence record.
    if not ctx.markdown and not ctx.emails:
        return Extraction(intel=CompanyIntel(confidence_score=0.0))

    cfg.require_groq()
    client = instructor.from_groq(Groq(api_key=cfg.groq_api_key))

    user_prompt = (
        f"Company domain: {ctx.domain}\n\n"
        f"Public emails already found on the site (ground truth, include these): "
        f"{ctx.emails or 'none found'}\n\n"
        f"Website content (cleaned markdown from multiple pages):\n\n{ctx.markdown}"
    )

    intel, completion = client.chat.completions.create_with_completion(
        model=cfg.llm_model,
        response_model=CompanyIntel,
        max_retries=2,
        temperature=0.1,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
    )

    # Merge regex ground-truth emails (union, preserve order, case-insensitive).
    seen = set()
    merged = []
    for e in [*intel.contact_emails, *ctx.emails]:
        key = e.lower().strip()
        if key and key not in seen:
            seen.add(key)
            merged.append(key)
    intel.contact_emails = merged

    # Blend the model's self-estimate with a completeness heuristic.
    llm_estimate = intel.confidence_score or 0.0
    heuristic = _heuristic_confidence(intel)
    intel.confidence_score = round(0.5 * llm_estimate + 0.5 * heuristic, 2)

    # Usage / cost diagnostics.
    usage = getattr(completion, "usage", None)
    tokens = getattr(usage, "total_tokens", None) if usage else None
    cost = None
    if usage is not None:
        prompt_toks = getattr(usage, "prompt_tokens", 0) or 0
        completion_toks = getattr(usage, "completion_tokens", 0) or 0
        cost = round(
            prompt_toks / 1_000_000 * _PRICE_IN_PER_M
            + completion_toks / 1_000_000 * _PRICE_OUT_PER_M,
            6,
        )

    return Extraction(intel=intel, usage_tokens=tokens, estimated_cost_usd=cost)
