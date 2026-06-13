"""Anthropic client + model tiering + structured-output helpers.

Model tiering per CLAUDE.md / README §6:
  * Haiku  — high-volume per-commit categorization (enum classification)
  * Sonnet — per-PR diff impact reads + daily/weekly summaries
  * Opus   — low-volume, high-value (corpus generation, monthly exec reports)

Structured output uses the modern `messages.parse(output_format=PydanticModel)` API; the
parsed instance is on `.parsed_output`. (Swapping to the Batches API later keeps this call
shape — a ~10-line change, per CLAUDE.md.)
"""

from __future__ import annotations

import os
from typing import TypeVar

from anthropic import AsyncAnthropic
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv()

# Model tier constants (exact IDs from CLAUDE.md).
HAIKU = "claude-haiku-4-5"
SONNET = "claude-sonnet-4-6"
OPUS = "claude-opus-4-8"

T = TypeVar("T", bound=BaseModel)

_client: AsyncAnthropic | None = None


def get_client() -> AsyncAnthropic:
    """Lazy singleton. Raises a clear error if the API key is missing."""
    global _client
    if _client is None:
        if not os.getenv("ANTHROPIC_API_KEY"):
            raise RuntimeError(
                "ANTHROPIC_API_KEY is not set. Export it or add it to .env "
                "(copy from .env.example). Phases 2 (corpus) and 3 (enrichment) need it."
            )
        _client = AsyncAnthropic()
    return _client


async def parse_structured(
    *,
    model: str,
    system: str,
    user_content: str,
    output_format: type[T],
    max_tokens: int = 1024,
) -> T:
    """One structured-output call. Returns a validated instance of `output_format`."""
    client = get_client()
    msg = await client.messages.parse(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_content}],
        output_format=output_format,
    )
    return msg.parsed_output


async def text_completion(
    *, model: str, system: str, user_content: str, max_tokens: int = 1024
) -> str:
    """Plain text call (used for the weekly team summary narrative)."""
    client = get_client()
    msg = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=system,
        messages=[{"role": "user", "content": user_content}],
    )
    return "".join(b.text for b in msg.content if getattr(b, "type", None) == "text")
