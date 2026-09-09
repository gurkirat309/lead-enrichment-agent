# Loom Walkthrough Script (target ~2:45)

A shot-by-shot script. For each beat: **🖥️ ON SCREEN** = what to have visible,
**🖱️ DO** = where to click/navigate, **🎤 SAY** = what to narrate.

---

## ✅ Before you hit record (do this first — off camera)

1. Open the project in your editor (VS Code) **and** an integrated terminal
   (`` Ctrl+` ``), already `cd`'d into `C:\lead-enrichment-agent`.
2. **Warm-up run** so the live demo is fast on camera (this also confirms the
   browser is installed):
   ```powershell
   .\.venv\Scripts\python.exe main.py --domains postman.com --out warmup.json
   ```
   Delete `warmup.json` after — it's just to warm the cache.
3. Make sure `output.json` already exists (the full 3-domain result) so you can
   open it instantly. If not, run the full command once.
4. In the editor's file explorer, have the `src/lead_agent/` folder expanded.
5. Close secrets: do **not** open `.env` on camera (it has your API keys).

---

## 0:00 – 0:20 · Intro
**🖥️ ON SCREEN:** Editor with the project file tree visible on the left.
**🖱️ DO:** Slowly hover/expand the `src/lead_agent/` folder so all files show.
**🎤 SAY:**
> "Hi, I'm [Name]. This is my Autonomous Lead Enrichment Agent. You give it
> company domains, and it crawls their public website with a headless browser,
> cleans the content, and uses an LLM to return structured company intelligence —
> overview, ideal customer, contact emails, leadership, and a confidence score."

## 0:20 – 1:00 · Architecture / code tour
**🖥️ ON SCREEN:** The `src/lead_agent/` files.
**🖱️ DO:** Click each file as you name it — `fetch.py`, then `clean.py`, then
`extract.py`, then `pipeline.py`. Just a quick scroll through each, ~5 seconds.
**🎤 SAY:**
> "It's a clean, modular pipeline. `fetch.py` uses Playwright to render even
> JavaScript-heavy pages, and discovers sub-pages like /about and /contact from
> the sitemap and on-page links." *(click clean.py)*
> "`clean.py` strips out all the CSS, scripts and menus and converts the page to
> plain markdown — about a 99% size reduction — so I never dump raw HTML into the
> LLM. It also regex-harvests emails as ground truth." *(click extract.py)*
> "`extract.py` calls Groq through Instructor with a Pydantic schema, so the model
> is forced to return valid structured JSON." *(click pipeline.py)*
> "And `pipeline.py` runs each domain in isolation, so one broken site never
> crashes the whole run."

**🖱️ DO:** Click `models.py`, highlight the `CompanyIntel` class with your cursor.
**🎤 SAY:**
> "This Pydantic model is the contract — these five fields are exactly what every
> run produces."

## 1:00 – 1:35 · Run it live
**🖥️ ON SCREEN:** The terminal.
**🖱️ DO:** Type (or paste) and run:
```powershell
.\.venv\Scripts\python.exe main.py --input domains.txt --out output.json --csv output.csv
```
**🎤 SAY (while it runs):**
> "Let me run it on the three test domains — Postman, Supabase, and Vapi. You can
> see it processing each one, printing the pages crawled, the confidence score,
> and the number of tokens used per domain. Notice no browser window opens — it's
> fully headless and automated."

## 1:35 – 2:05 · The output + Bonus #3 (cost tracking)
**🖥️ ON SCREEN:** Open `output.json` in the editor.
**🖱️ DO:** Scroll to the `postman.com` record. Cursor-highlight `overview`, then
`target_audience`, then `contact_emails`, then `team_members`, then
`confidence_score`. Then scroll to `usage_tokens` and `estimated_cost_usd`.
**🎤 SAY:**
> "Here's the structured result — a clean two-sentence overview, the ideal
> customer profile, the public emails, the leadership team with roles, and a 0.9-plus
> confidence score." *(scroll to tokens/cost)*
> "As a bonus, every record also logs the exact tokens used and the estimated API
> cost per domain — this run is about a tenth of a cent each."

## 2:05 – 2:25 · Bonus #1 (LinkedIn search)
**🖥️ ON SCREEN:** Still in `output.json`, on a `team_members` entry with a
`linkedin_url` filled in (e.g. Abhinav Asthana → linkedin.com/in/abhinavasthana).
**🖱️ DO:** Highlight the `linkedin_url` value. Optionally click `enrich.py` for a
second.
**🎤 SAY:**
> "For the founders, when a LinkedIn URL isn't on the company's own site, the agent
> searches for it using SerpAPI — and it verifies the name matches the profile
> before attaching it, so it never links the wrong person. That's this
> `enrich.py` module."

## 2:25 – 2:40 · Bonus #2 (agentic navigation)
**🖥️ ON SCREEN:** Terminal.
**🖱️ DO:** Run:
```powershell
.\.venv\Scripts\python.exe main.py --domains postman.com --agentic
```
**🎤 SAY:**
> "There's also an agentic mode. Instead of fixed rules, the LLM is given the
> homepage links and a 'visit page' tool, and it decides step by step which pages
> to open until it has what it needs — a custom multi-step tool-calling loop in
> `nav_agent.py`."

## 2:40 – 2:55 · Resilience + close
**🖥️ ON SCREEN:** Terminal.
**🖱️ DO:** Run a broken domain first, then a good one:
```powershell
.\.venv\Scripts\python.exe main.py --domains not-a-real-site-xyz123.com vapi.ai --out demo.json
```
**🎤 SAY:**
> "And resilience — I pass a broken domain first. It's captured as an error record
> and the run just continues to the next site; it never crashes. Setup is a
> standard venv plus a Groq key — it's all in the README. Thanks for watching!"

---

## Quick tips
- Speak a touch slower than feels natural; 2:45 of content fits ~3 minutes.
- If a live run feels slow, cut to the already-open `output.json` and keep talking.
- Do NOT show `.env` — mention keys live in it, but don't open it.
- If you want a safety net, record the runs once, then narrate over them.
