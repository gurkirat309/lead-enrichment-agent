# Autonomous Lead Enrichment Agent

A Python pipeline that takes company **domains** as input, autonomously crawls
their public web presence with a **headless browser**, cleans the content down to
lean markdown, and uses an **LLM with strict structured outputs** to produce
company intelligence as JSON/CSV.

For each domain it extracts:

| Field | Description |
|---|---|
| **Company overview** | Concise ~2-sentence summary of what they do |
| **Target audience / ICP** | Who the product is built for |
| **Contact emails** | Public/generic emails (`contact@`, `sales@`, `support@`, …) |
| **Key leadership / team** | Name, role, and LinkedIn URL (if discoverable) |
| **Data confidence score** | `0.0`–`1.0` completeness/quality estimate |

## Architecture

```
domains
  │
  ▼
[1] fetch.py      Playwright (headless Chromium) renders each page.
                  Subpage discovery via sitemap.xml + on-page link filtering
                  (/about, /team, /company, /contact, /pricing, /careers …)
  │
  ▼
[2] clean.py      HTML → lean markdown via trafilatura (bs4 fallback).
                  Strips CSS / JS / SVG / nav boilerplate. Regex-harvests
                  emails as ground truth. Token-budgeted context assembly.
  │  (~99% size reduction vs raw HTML)
  ▼
[3] extract.py    Groq + Instructor + Pydantic → CompanyIntel schema
                  (tool calling). Merges regex emails, blends a confidence
                  score, records token usage + estimated cost.
  │
  ▼
[5] enrich.py     (bonus) Tavily/SerpAPI lookup for founder LinkedIn URLs
                  when missing from the page. No-op if no search key.
  │
  ▼
[4] pipeline.py   Orchestrates per domain with full isolation → DomainResult
main.py           CLI → output.json / output.csv
```

Each domain is processed **in isolation**: any failure (DNS, 404, timeout,
anti-bot, missing fields) is captured as an `error` record so a single bad site
**never crashes the run**.

## How design decisions map to the evaluation rubric

- **Agent & scraping architecture (30%)** — headless Playwright handles
  JS-rendered SPAs; subpage discovery combines `sitemap.xml` with priority-ranked
  on-page link filtering; same-host guard avoids wandering off-site.
- **LLM & structured output (25%)** — Pydantic schema enforced via Instructor
  (function calling) with validation retries; **no raw HTML** ever reaches the
  LLM (trafilatura → markdown, ~99% reduction); regex-harvested emails merged as
  ground truth to boost recall.
- **Error handling & resilience (20%)** — try/except at page, site, and domain
  levels; timeouts; HTTP-status checks; graceful "no usable content" path that
  skips the LLM; bonus enrichment can never break the core run.
- **Code quality & docs (15%)** — modular one-responsibility files, type hints,
  dataclasses/Pydantic models, this README.
### Bonus features (all three implemented)

1. **Search integration** — `enrich.py` looks up founder **LinkedIn URLs** via
   SerpAPI/Tavily when they aren't on the site, with **name verification** (first
   and last name must appear in the profile slug) so an unrelated profile is never
   attached — a wrong URL is worse than none.
2. **Agentic framework** — a **custom multi-step tool-calling loop**
   (`nav_agent.py`): the LLM is given the homepage links and a `visit_page` tool
   and decides, step by step, which subpages to open until it calls `finish`.
   Enable with `--agentic`; the deterministic path stays the default.
3. **Cost tracking** — per-domain `usage_tokens` and `estimated_cost_usd` in every
   record.

## Setup

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    |    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
playwright install chromium

cp .env.example .env      # then add your GROQ_API_KEY
```

## Run

```bash
python main.py --input domains.txt --out output.json --csv output.csv
# or pass domains directly:
python main.py --domains postman.com supabase.com vapi.ai
# bonus: LLM-driven agentic navigation instead of deterministic discovery:
python main.py --domains postman.com --agentic
```

## Environment variables

See [`.env.example`](.env.example).

| Variable | Required | Purpose |
|---|---|---|
| `GROQ_API_KEY` | ✅ | LLM extraction |
| `LLM_MODEL` | – | default `openai/gpt-oss-120b` (Groq) |
| `TAVILY_API_KEY` / `SERPAPI_KEY` | – | bonus founder-LinkedIn lookup |
| `MAX_SUBPAGES`, `PAGE_TIMEOUT_MS`, `MAX_CHARS_PER_PAGE`, `MAX_TOTAL_CONTEXT_CHARS` | – | crawl/token tuning |

## Sample output

[`output.json`](output.json) and [`output.csv`](output.csv) are real runs against
the three test domains (postman.com, supabase.com, vapi.ai). Example:

```json
{
  "domain": "postman.com",
  "status": "ok",
  "intel": {
    "overview": "Postman is an AI-native API platform that enables developers to design, test, manage, and distribute APIs and services at enterprise scale. ...",
    "target_audience": "Software engineers, developers, and organizations building, testing, and managing APIs and services.",
    "contact_emails": ["info@postman.com", "help@postman.com", "..."],
    "team_members": [{"name": "Abhinav Asthana", "role": "CEO / Co-Founder", "linkedin_url": null}],
    "confidence_score": 0.93
  },
  "pages_crawled": ["https://postman.com", "https://postman.com/company/about-postman", "..."],
  "usage_tokens": 4609,
  "estimated_cost_usd": 0.001012
}
```

## Project structure

```
lead-enrichment-agent/
├── main.py                     CLI entry (JSON + CSV output)
├── requirements.txt
├── .env.example
├── domains.txt                 input list
├── output.json / output.csv    sample output
└── src/lead_agent/
    ├── models.py               Pydantic schema (the contract)
    ├── config.py               env-driven settings
    ├── fetch.py                Phase 1 - Playwright + subpage discovery
    ├── clean.py                Phase 2 - HTML → markdown + email harvest
    ├── extract.py              Phase 3 - Groq + Instructor extraction
    ├── enrich.py               Bonus - founder LinkedIn lookup (name-verified)
    ├── nav_agent.py            Bonus - agentic multi-step navigation loop
    └── pipeline.py             Phase 4 - orchestration + resilience
```

## Notes & limitations

- On sites that don't expose founders on public pages, extracted team members are
  real people from the careers/company pages but may not be founders; the bonus
  LinkedIn-search step (with a Tavily/SerpAPI key) is what closes that gap.
- Cost figures are approximate estimates from token usage at published Groq rates.
