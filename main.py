"""CLI entry point for the Lead Enrichment Agent.

Usage:
    python main.py --domains postman.com supabase.com vapi.ai
    python main.py --input domains.txt --out output.json --csv output.csv
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
from pathlib import Path
from typing import List

from src.lead_agent.config import settings
from src.lead_agent.models import DomainResult
from src.lead_agent.pipeline import run


def load_domains(args: argparse.Namespace) -> List[str]:
    domains: List[str] = []
    if args.domains:
        domains.extend(args.domains)
    if args.input:
        text = Path(args.input).read_text(encoding="utf-8")
        domains.extend(
            line.strip() for line in text.splitlines() if line.strip() and not line.startswith("#")
        )
    # De-duplicate, preserve order.
    seen = set()
    unique = []
    for d in domains:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return unique


def write_json(results: List[DomainResult], path: str) -> None:
    payload = [r.model_dump() for r in results]
    Path(path).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def write_csv(results: List[DomainResult], path: str) -> None:
    """Flattened CSV view (one row per domain)."""
    fields = [
        "domain",
        "status",
        "error",
        "overview",
        "target_audience",
        "contact_emails",
        "team_members",
        "confidence_score",
        "pages_crawled",
    ]
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        for r in results:
            intel = r.intel
            writer.writerow(
                {
                    "domain": r.domain,
                    "status": r.status,
                    "error": r.error or "",
                    "overview": intel.overview if intel else "",
                    "target_audience": intel.target_audience if intel else "",
                    "contact_emails": "; ".join(intel.contact_emails) if intel else "",
                    "team_members": (
                        "; ".join(
                            f"{m.name} ({m.role or '?'}) {m.linkedin_url or ''}".strip()
                            for m in intel.team_members
                        )
                        if intel
                        else ""
                    ),
                    "confidence_score": intel.confidence_score if intel else "",
                    "pages_crawled": "; ".join(r.pages_crawled),
                }
            )


def main() -> None:
    parser = argparse.ArgumentParser(description="Autonomous Lead Enrichment Agent")
    parser.add_argument("--domains", nargs="*", help="Company domains to process.")
    parser.add_argument("--input", help="Path to a text file with one domain per line.")
    parser.add_argument("--out", default="output.json", help="Output JSON path.")
    parser.add_argument("--csv", dest="csv_path", help="Optional output CSV path.")
    parser.add_argument(
        "--agentic",
        action="store_true",
        help="Use the LLM-driven agentic navigation loop instead of deterministic discovery.",
    )
    args = parser.parse_args()

    domains = load_domains(args)
    if not domains:
        parser.error("No domains provided. Use --domains or --input.")

    if args.agentic:
        settings.agentic = True
        print("[mode] agentic navigation enabled")

    results = asyncio.run(run(domains))

    write_json(results, args.out)
    print(f"Wrote {len(results)} records -> {args.out}")
    if args.csv_path:
        write_csv(results, args.csv_path)
        print(f"Wrote CSV -> {args.csv_path}")


if __name__ == "__main__":
    main()
