# Loom Walkthrough Script (2–3 min)

Keep it tight. Screen-share your editor + a terminal. Aim ~2:30.

## 0:00–0:20 — Intro (what & why)
> "Hi, I'm [Name]. This is my Autonomous Lead Enrichment Agent. You give it
> company domains; it crawls their public site with a headless browser, cleans
> the content, and an LLM returns structured intelligence — overview, ICP,
> contact emails, leadership, and a confidence score."

## 0:20–1:00 — Architecture / code structure
Open `src/lead_agent/` and scroll the files as you talk:
> "It's a modular pipeline. `fetch.py` uses Playwright to render JS pages and
> discovers subpages via sitemap plus link filtering. `clean.py` converts HTML to
> lean markdown with trafilatura — about a 99% size cut, so no raw HTML hits the
> LLM — and regex-harvests emails as ground truth. `extract.py` uses Groq with
> Instructor and a Pydantic schema for strict structured output. `pipeline.py`
> orchestrates each domain in isolation so one bad site never crashes the run."

Briefly show `models.py` (the Pydantic schema) — "this is the contract."

## 1:00–1:50 — Run it live
In the terminal:
```bash
python main.py --input domains.txt --out output.json --csv output.csv
```
> "Running it on the three test domains — postman, supabase, vapi. You can see it
> processing each: pages crawled, confidence score, and token usage per domain."

## 1:50–2:20 — Show the output
Open `output.json`:
> "Here's the structured result — a clean two-sentence overview, the ICP, the
> public emails, leadership with roles, a 0.93 confidence score, and token/cost
> tracking per domain."

## 2:20–2:40 — Resilience (the differentiator)
```bash
python main.py --domains bad-domain-xyz-123.com vapi.ai --out demo.json
```
> "And resilience — I pass a broken domain first. It's captured as an error
> record and the run continues to the next domain. It never crashes midway."

## 2:40–2:50 — Close
> "Setup is a standard venv, requirements, and a Groq key in .env. Everything's
> in the README. Thanks for watching."

### Tips
- Have the venv activated and `.env` populated **before** recording.
- Do one dry run first so the Playwright/model calls are warm and quick.
- If you added a Tavily/SerpAPI key, mention the bonus LinkedIn lookup filling in profile URLs.
