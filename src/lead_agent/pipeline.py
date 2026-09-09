"""Phase 4 - Orchestration & resilience.

Runs the full fetch -> clean -> extract (-> enrich) flow for a list of domains.
Each domain is isolated: any failure is captured in a DomainResult with
status='error' so a single bad site never crashes the whole run.
"""

from __future__ import annotations

from typing import List

from .clean import build_context
from .config import Settings, settings as default_settings
from .extract import extract_intel
from .fetch import fetch_site
from .models import DomainResult


async def process_domain(domain: str, cfg: Settings = default_settings) -> DomainResult:
    """Process a single domain end-to-end. Never raises; errors are captured."""
    try:
        # Phase 1: fetch homepage + subpages. Agentic (LLM-driven navigation) when
        # enabled, otherwise the deterministic sitemap+link discovery path.
        if cfg.agentic:
            from .nav_agent import agentic_fetch_site

            site = await agentic_fetch_site(domain, cfg)
        else:
            site = await fetch_site(domain, cfg)

        # Phase 2: clean + token-budget + harvest emails.
        ctx = build_context(site, cfg)

        pages_crawled = [p.url for p in site.ok_pages]

        if not ctx.markdown and not ctx.emails:
            # Nothing usable was retrieved from the site.
            failed = "; ".join(f"{p.url} ({p.error})" for p in site.pages if p.status == "error")
            return DomainResult(
                domain=domain,
                status="error",
                error=f"No usable content retrieved. {failed}".strip(),
                pages_crawled=pages_crawled,
            )

        # Phase 3: structured LLM extraction.
        extraction = extract_intel(ctx, cfg)

        # Phase 5 (bonus): fill missing founder LinkedIn URLs via web search.
        try:
            from .enrich import enrich_linkedin

            enrich_linkedin(extraction.intel, ctx.domain, cfg)
        except Exception:  # noqa: BLE001 - bonus enrichment must never break the run
            pass

        return DomainResult(
            domain=domain,
            status="ok",
            intel=extraction.intel,
            pages_crawled=pages_crawled,
            usage_tokens=extraction.usage_tokens,
            estimated_cost_usd=extraction.estimated_cost_usd,
        )
    except Exception as exc:  # noqa: BLE001 - resilience is a hard requirement
        return DomainResult(domain=domain, status="error", error=str(exc))


async def run(domains: List[str], cfg: Settings = default_settings) -> List[DomainResult]:
    """Process every domain, returning one DomainResult each."""
    results: List[DomainResult] = []
    for domain in domains:
        print(f"[*] Processing {domain} ...")
        result = await process_domain(domain, cfg)
        marker = "OK " if result.status == "ok" else "ERR"
        conf = result.intel.confidence_score if result.intel else "-"
        print(
            f"    {marker} pages={len(result.pages_crawled)} "
            f"confidence={conf} tokens={result.usage_tokens}"
        )
        results.append(result)
    return results
