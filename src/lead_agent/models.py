"""Pydantic schemas: the structured contract for the whole pipeline.

These models are used both for LLM structured-output extraction (via Instructor)
and for serializing the final enriched record to JSON/CSV.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class TeamMember(BaseModel):
    """A leadership / key team member discovered on the site (or via search)."""

    name: str = Field(..., description="Full name of the person.")
    role: Optional[str] = Field(
        None, description="Job title or role, e.g. 'CEO', 'Head of Engineering'."
    )
    linkedin_url: Optional[str] = Field(
        None,
        description="LinkedIn profile URL if discoverable from page content or search.",
    )


class CompanyIntel(BaseModel):
    """The structured intelligence the LLM is asked to extract for one company."""

    overview: Optional[str] = Field(
        None, description="Concise 2-sentence summary of what the company does."
    )
    target_audience: Optional[str] = Field(
        None,
        description=(
            "Who the product is built for / ideal customer profile (ICP), "
            "e.g. 'Developers building backend applications'."
        ),
    )
    contact_emails: List[str] = Field(
        default_factory=list,
        description="Generic/public emails found on the site (contact@, sales@, support@).",
    )
    team_members: List[TeamMember] = Field(
        default_factory=list,
        description="Key leadership / team members with names, roles, and LinkedIn URLs.",
    )
    confidence_score: float = Field(
        0.0,
        ge=0.0,
        le=1.0,
        description="Estimated 0.0-1.0 score for the quality/completeness of the data.",
    )


class DomainResult(BaseModel):
    """Top-level per-domain record written to the output file.

    Always produced even when scraping/extraction fails, so a single bad site
    never crashes the run and the failure is captured explicitly.
    """

    domain: str
    status: str = Field("ok", description="'ok' or 'error'.")
    error: Optional[str] = Field(None, description="Error message when status='error'.")

    intel: Optional[CompanyIntel] = None

    # Diagnostics / provenance
    pages_crawled: List[str] = Field(default_factory=list)
    usage_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
