"""Bonus - Agentic navigation via a custom multi-step tool-calling loop.

Instead of deterministic subpage selection, this gives an LLM a `visit_page`
tool and lets it decide, step by step, which discovered links to open in a
headless browser until it calls `finish`. Produces the same FetchedSite shape as
fetch.py so the rest of the pipeline is unchanged.

Enabled via `--agentic`; the deterministic path in fetch.py remains the default.
"""

from __future__ import annotations

import json
import re
from typing import List
from urllib.parse import urljoin, urlparse

from groq import Groq
from playwright.async_api import async_playwright

from .clean import clean_html
from .config import Settings, settings as default_settings
from .fetch import USER_AGENT, FetchedPage, FetchedSite, _fetch_one, _same_host, normalize_base_url

SYSTEM_PROMPT = """You are a web-navigation agent enriching a company lead.
You are given a company's homepage text and a list of candidate internal links.
Your goal is to visit the few pages most likely to contain: what the company
does, who it's for (ICP), public contact emails, and leadership/team members.

Use the visit_page tool to open a promising link (about, team, company, contact,
pricing, careers pages are usually best). After visiting the pages you need, call
finish. Be economical - visit only high-value pages, not everything."""

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "visit_page",
            "description": "Open one candidate URL in the browser and read its cleaned text.",
            "parameters": {
                "type": "object",
                "properties": {"url": {"type": "string", "description": "The URL to open."}},
                "required": ["url"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "finish",
            "description": "Stop navigating; enough pages have been gathered.",
            "parameters": {
                "type": "object",
                "properties": {"reason": {"type": "string"}},
                "required": [],
            },
        },
    },
]


def _candidate_links(html: str, base_url: str, base_netloc: str, limit: int = 40) -> List[str]:
    hrefs = re.findall(r'href=["\']([^"\']+)["\']', html or "", flags=re.IGNORECASE)
    seen, out = set(), []
    for h in hrefs:
        url = urljoin(base_url, h).split("#")[0].rstrip("/")
        if url in seen or not _same_host(url, base_netloc):
            continue
        if not urlparse(url).path or urlparse(url).path == "/":
            continue  # skip the homepage itself
        seen.add(url)
        out.append(url)
        if len(out) >= limit:
            break
    return out


async def agentic_fetch_site(domain: str, cfg: Settings = default_settings) -> FetchedSite:
    """Fetch homepage, then let the LLM drive subpage navigation. Never raises."""
    base_url = normalize_base_url(domain)
    base_netloc = urlparse(base_url).netloc
    site = FetchedSite(domain=domain, base_url=base_url)

    try:
        cfg.require_groq()
        client = Groq(api_key=cfg.groq_api_key)

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            context = await browser.new_context(user_agent=USER_AGENT)
            page = await context.new_page()

            home = await _fetch_one(page, base_url, cfg.page_timeout_ms)
            site.pages.append(home)

            candidates = _candidate_links(home.html, base_url, base_netloc)
            home_text = clean_html(home.html)[:3000]

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": (
                        f"Company domain: {domain}\n\n"
                        f"Homepage text (truncated):\n{home_text}\n\n"
                        f"Candidate internal links:\n" + "\n".join(candidates)
                    ),
                },
            ]

            visited = set()
            max_steps = cfg.max_subpages
            for _ in range(max_steps + 2):  # a little headroom for finish/thinking turns
                resp = client.chat.completions.create(
                    model=cfg.llm_model,
                    messages=messages,
                    tools=TOOLS,
                    tool_choice="auto",
                    temperature=0.1,
                )
                msg = resp.choices[0].message
                if not msg.tool_calls:
                    break

                assistant_msg = {"role": "assistant", "content": msg.content or None,
                                 "tool_calls": [
                                     {"id": tc.id, "type": "function",
                                      "function": {"name": tc.function.name,
                                                   "arguments": tc.function.arguments}}
                                     for tc in msg.tool_calls
                                 ]}
                messages.append(assistant_msg)

                stop = False
                for tc in msg.tool_calls:
                    if tc.function.name == "finish":
                        stop = True
                        messages.append({"role": "tool", "tool_call_id": tc.id, "content": "ok"})
                        continue

                    try:
                        args = json.loads(tc.function.arguments or "{}")
                    except Exception:  # noqa: BLE001
                        args = {}
                    url = (args.get("url") or "").split("#")[0].rstrip("/")

                    if not url or not _same_host(url, base_netloc) or url in visited:
                        messages.append({"role": "tool", "tool_call_id": tc.id,
                                         "content": "skipped (invalid, off-site, or already visited)"})
                        continue
                    if len(visited) >= max_steps:
                        messages.append({"role": "tool", "tool_call_id": tc.id,
                                         "content": "page budget reached; call finish"})
                        continue

                    visited.add(url)
                    fetched = await _fetch_one(page, url, cfg.page_timeout_ms)
                    site.pages.append(fetched)
                    snippet = clean_html(fetched.html)[:800] if fetched.status == "ok" else f"error: {fetched.error}"
                    messages.append({"role": "tool", "tool_call_id": tc.id,
                                     "content": f"Visited {url}\n{snippet}"})

                if stop or len(visited) >= max_steps:
                    break

            await context.close()
            await browser.close()
    except Exception as exc:  # noqa: BLE001 - navigation must never crash the run
        if not site.pages:
            site.pages.append(FetchedPage(url=base_url, status="error", error=str(exc)))

    return site
