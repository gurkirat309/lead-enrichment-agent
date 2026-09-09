"""Phase 2 - Context pre-processing & token optimization.

Converts raw HTML into lean markdown/text (stripping CSS, scripts, SVGs and
navigation boilerplate) so we never feed raw HTML trees to the LLM, and harvests
public emails via regex as ground truth alongside the model's extraction.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

import trafilatura
from bs4 import BeautifulSoup

from .config import Settings, settings as default_settings
from .fetch import FetchedSite

# --- Email harvesting -------------------------------------------------------

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")

# Substrings that indicate a false-positive "email" (asset names, placeholders).
_EMAIL_JUNK = (
    ".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".ico", "@2x", "@3x",
    "example.com", "domain.com", "email.com", "yourdomain", "sentry.io",
    "wixpress.com", ".webflow.io",
)


# Escaped delimiters that leak from embedded JSON/HTML and glue onto emails
# (e.g. Next.js payloads render '>info@x.com' as '>info@x.com').
_ESCAPE_ARTIFACTS = ("\\u003e", "\\u003c", "\\u0026", "&gt;", "&lt;", "&amp;", "&#62;", "&#60;")


def extract_emails(html: str) -> List[str]:
    """Return deduped, plausible public emails from raw HTML (incl. mailto: links)."""
    for art in _ESCAPE_ARTIFACTS:
        html = html.replace(art, " ")

    found: List[str] = []
    # mailto: links are the most reliable source.
    for m in re.findall(r'mailto:([^"\'?>\s]+)', html, flags=re.IGNORECASE):
        found.append(m)
    found.extend(EMAIL_RE.findall(html))

    seen = set()
    out: List[str] = []
    for raw in found:
        email = raw.strip().strip(".").lower()
        if not EMAIL_RE.fullmatch(email):
            continue
        if any(junk in email for junk in _EMAIL_JUNK):
            continue
        if email in seen:
            continue
        seen.add(email)
        out.append(email)
    return out


# --- HTML -> clean text -----------------------------------------------------

_STRIP_TAGS = ["script", "style", "noscript", "svg", "nav", "header", "footer", "form", "iframe"]
_WS_RE = re.compile(r"[ \t\r\f\v]+")
_NL_RE = re.compile(r"\n{3,}")


def _collapse(text: str) -> str:
    text = _WS_RE.sub(" ", text)
    text = _NL_RE.sub("\n\n", text)
    return text.strip()


def clean_html(html: str) -> str:
    """Extract the main readable content of a page as markdown/plain text."""
    if not html:
        return ""
    # Primary: trafilatura pulls main content and drops boilerplate.
    try:
        md = trafilatura.extract(
            html,
            output_format="markdown",
            include_comments=False,
            include_tables=True,
            favor_recall=True,
        )
        if md and len(md.strip()) > 200:
            return _collapse(md)
    except Exception:  # noqa: BLE001
        pass

    # Fallback: strip boilerplate tags and take visible text.
    try:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(_STRIP_TAGS):
            tag.decompose()
        root = soup.body or soup
        return _collapse(root.get_text("\n", strip=True))
    except Exception:  # noqa: BLE001
        return ""


# --- Site-level context assembly -------------------------------------------

@dataclass
class CleanedContent:
    domain: str
    markdown: str = ""            # token-budgeted context handed to the LLM
    emails: List[str] = field(default_factory=list)
    pages_used: List[str] = field(default_factory=list)


def build_context(site: FetchedSite, cfg: Settings = default_settings) -> CleanedContent:
    """Clean every fetched page and assemble a single token-budgeted context."""
    result = CleanedContent(domain=site.domain)

    all_emails: List[str] = []
    chunks: List[str] = []
    budget = cfg.max_total_context_chars

    for page in site.ok_pages:
        all_emails.extend(extract_emails(page.html))

        if budget <= 0:
            continue
        cleaned = clean_html(page.html)
        if not cleaned:
            continue
        cleaned = cleaned[: cfg.max_chars_per_page]
        cleaned = cleaned[:budget]
        budget -= len(cleaned)

        chunks.append(f"## Source page: {page.url}\n\n{cleaned}")
        result.pages_used.append(page.url)

    # Dedup emails, preserve order.
    seen = set()
    for e in all_emails:
        if e not in seen:
            seen.add(e)
            result.emails.append(e)

    result.markdown = "\n\n---\n\n".join(chunks)
    return result
