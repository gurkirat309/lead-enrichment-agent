"""Phase 5 (Bonus) - External founder LinkedIn lookup.

When a leader has no LinkedIn URL from on-page content, use a search engine
(Tavily or SerpAPI) to find their public LinkedIn profile URL. Entirely
optional: if no search key is configured, this is a no-op and never raises.
"""

from __future__ import annotations

import re
from typing import List, Optional
from urllib.parse import urlparse

import requests

from .config import Settings, settings as default_settings
from .models import CompanyIntel

LINKEDIN_IN_RE = re.compile(r"https?://([a-z]{2,3}\.)?linkedin\.com/in/[^\s\"'?#>)]+", re.IGNORECASE)

# Cap lookups so we never burn a large search budget on one domain.
MAX_LOOKUPS = 5


def _company_name(domain: str) -> str:
    host = urlparse(domain if "//" in domain else "//" + domain).netloc or domain
    host = host[4:] if host.startswith("www.") else host
    return host.split(".")[0]


def _first_linkedin_url(text: str) -> Optional[str]:
    m = LINKEDIN_IN_RE.search(text or "")
    return m.group(0).rstrip("/") if m else None


def _search_tavily(query: str, cfg: Settings) -> List[str]:
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=cfg.tavily_api_key)
        resp = client.search(query=query, max_results=5)
        return [r.get("url", "") for r in resp.get("results", [])]
    except Exception:  # noqa: BLE001
        return []


def _search_serpapi(query: str, cfg: Settings) -> List[str]:
    try:
        resp = requests.get(
            "https://serpapi.com/search.json",
            params={"engine": "google", "q": query, "api_key": cfg.serpapi_key, "num": 5},
            timeout=15,
        )
        data = resp.json()
        return [r.get("link", "") for r in data.get("organic_results", [])]
    except Exception:  # noqa: BLE001
        return []


def _find_linkedin(name: str, company: str, cfg: Settings) -> Optional[str]:
    query = f'{name} {company} LinkedIn'
    urls: List[str] = []
    if cfg.tavily_api_key:
        urls = _search_tavily(query, cfg)
    elif cfg.serpapi_key:
        urls = _search_serpapi(query, cfg)

    for url in urls:
        found = _first_linkedin_url(url)
        if found:
            return found
    return None


def enrich_linkedin(intel: CompanyIntel, domain: str, cfg: Settings = default_settings) -> None:
    """Mutate intel in place, filling missing LinkedIn URLs for team members."""
    if not (cfg.tavily_api_key or cfg.serpapi_key):
        return  # No search provider configured -> bonus disabled.

    company = _company_name(domain)
    lookups = 0
    for member in intel.team_members:
        if member.linkedin_url:
            continue
        if lookups >= MAX_LOOKUPS:
            break
        lookups += 1
        url = _find_linkedin(member.name, company, cfg)
        if url:
            member.linkedin_url = url
