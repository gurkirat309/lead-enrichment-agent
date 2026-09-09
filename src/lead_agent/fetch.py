"""Phase 1 - Automated browsing & content retrieval (Playwright).

Renders the homepage headlessly (handling JS-rendered content), discovers
relevant subpages via sitemap.xml + on-page link filtering, and returns the
raw HTML for each page. Every network operation is isolated so a single bad
page or site never raises out of this module.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional
from urllib.parse import urljoin, urlparse

from playwright.async_api import async_playwright

from .config import Settings, settings as default_settings

# A realistic desktop UA reduces trivial bot blocking.
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
)


@dataclass
class FetchedPage:
    url: str
    html: str = ""
    status: str = "ok"  # "ok" | "error"
    error: Optional[str] = None


@dataclass
class FetchedSite:
    domain: str
    base_url: str
    pages: List[FetchedPage] = field(default_factory=list)

    @property
    def ok_pages(self) -> List[FetchedPage]:
        return [p for p in self.pages if p.status == "ok" and p.html]


def normalize_base_url(domain: str) -> str:
    """Turn 'postman.com' or 'https://postman.com/x' into a clean 'https://host'."""
    domain = domain.strip()
    if not domain.startswith(("http://", "https://")):
        domain = "https://" + domain
    parsed = urlparse(domain)
    return f"{parsed.scheme}://{parsed.netloc}"


def _same_host(url: str, base_netloc: str) -> bool:
    netloc = urlparse(url).netloc.lower()
    base = base_netloc.lower()
    # Treat www / apex and shallow subdomains of the same registrable domain as same site.
    base_root = base[4:] if base.startswith("www.") else base
    return netloc == base or netloc == base_root or netloc.endswith("." + base_root)


def _select_candidates(
    links: List[str], base_netloc: str, hints: List[str], limit: int
) -> List[str]:
    """Pick same-host links whose path matches a hint, ordered by hint priority."""
    selected: List[str] = []
    seen = set()
    for hint in hints:  # preserve hint priority (about, team, contact, ...)
        pattern = re.compile(rf"(^|/){re.escape(hint)}(/|$)", re.IGNORECASE)
        for link in links:
            clean = link.split("#")[0].rstrip("/")
            if clean in seen:
                continue
            if not _same_host(clean, base_netloc):
                continue
            path = urlparse(clean).path
            if pattern.search(path):
                selected.append(clean)
                seen.add(clean)
                if len(selected) >= limit:
                    return selected
    return selected


async def _fetch_one(page, url: str, timeout_ms: int) -> FetchedPage:
    try:
        resp = await page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
        if resp is not None and resp.status >= 400:
            return FetchedPage(url=url, status="error", error=f"HTTP {resp.status}")
        # Give client-rendered content a brief moment to settle.
        try:
            await page.wait_for_timeout(800)
        except Exception:  # noqa: BLE001
            pass
        html = await page.content()
        return FetchedPage(url=url, html=html, status="ok")
    except Exception as exc:  # noqa: BLE001 - resilience is a hard requirement
        return FetchedPage(url=url, status="error", error=str(exc))


async def _discover_from_sitemap(page, base_url: str, hints: List[str], timeout_ms: int) -> List[str]:
    """Best-effort sitemap parse. Returns candidate URLs matching hints."""
    found: List[str] = []
    for path in ("/sitemap.xml", "/sitemap_index.xml"):
        try:
            resp = await page.goto(urljoin(base_url, path), wait_until="domcontentloaded", timeout=timeout_ms)
            if resp is None or resp.status >= 400:
                continue
            body = await page.content()
            locs = re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", body, flags=re.IGNORECASE)
            for loc in locs:
                low = loc.lower()
                if any(h in low for h in hints):
                    found.append(loc.split("#")[0].rstrip("/"))
        except Exception:  # noqa: BLE001
            continue
    return found


async def fetch_site(domain: str, cfg: Settings = default_settings) -> FetchedSite:
    """Fetch homepage + discovered subpages for one domain. Never raises."""
    base_url = normalize_base_url(domain)
    base_netloc = urlparse(base_url).netloc
    site = FetchedSite(domain=domain, base_url=base_url)

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=USER_AGENT)
            page = await context.new_page()

            # 1) Homepage
            home = await _fetch_one(page, base_url, cfg.page_timeout_ms)
            site.pages.append(home)

            # 2) Candidate subpages from on-page links + sitemap
            candidates: List[str] = []
            if home.status == "ok" and home.html:
                hrefs = re.findall(r'href=["\']([^"\']+)["\']', home.html, flags=re.IGNORECASE)
                links = [urljoin(base_url, h) for h in hrefs]
                candidates.extend(links)
            sitemap_hits = await _discover_from_sitemap(page, base_url, cfg.subpage_hints, cfg.page_timeout_ms)
            candidates.extend(sitemap_hits)

            targets = _select_candidates(candidates, base_netloc, cfg.subpage_hints, cfg.max_subpages)

            # 3) Fetch each selected subpage
            for url in targets:
                site.pages.append(await _fetch_one(page, url, cfg.page_timeout_ms))

            await context.close()
            await browser.close()
    except Exception as exc:  # noqa: BLE001 - never let the browser layer crash the run
        if not site.pages:
            site.pages.append(FetchedPage(url=base_url, status="error", error=str(exc)))

    return site
