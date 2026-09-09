"""Central configuration, loaded from environment variables (.env)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()


# Relevant subpaths to look for during subpage discovery (Phase 1).
DEFAULT_SUBPAGE_HINTS: List[str] = [
    "about",
    "about-us",
    "company",
    "team",
    "leadership",
    "people",
    "contact",
    "contact-us",
    "pricing",
    "careers",
]


@dataclass
class Settings:
    # --- LLM (Groq) ---
    groq_api_key: str = field(default_factory=lambda: os.getenv("GROQ_API_KEY", ""))
    llm_model: str = field(
        default_factory=lambda: os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
    )

    # --- Bonus: LinkedIn founder lookup ---
    serpapi_key: str = field(default_factory=lambda: os.getenv("SERPAPI_KEY", ""))
    tavily_api_key: str = field(default_factory=lambda: os.getenv("TAVILY_API_KEY", ""))

    # --- Crawling behavior ---
    max_subpages: int = field(default_factory=lambda: int(os.getenv("MAX_SUBPAGES", "5")))
    page_timeout_ms: int = field(
        default_factory=lambda: int(os.getenv("PAGE_TIMEOUT_MS", "20000"))
    )
    max_chars_per_page: int = field(
        default_factory=lambda: int(os.getenv("MAX_CHARS_PER_PAGE", "6000"))
    )
    max_total_context_chars: int = field(
        default_factory=lambda: int(os.getenv("MAX_TOTAL_CONTEXT_CHARS", "20000"))
    )

    subpage_hints: List[str] = field(default_factory=lambda: list(DEFAULT_SUBPAGE_HINTS))

    def require_groq(self) -> None:
        if not self.groq_api_key:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Copy .env.example to .env and add your key."
            )


settings = Settings()
