"""One-time corpus generator: ~40 realistic PR templates via Claude (Opus).

Each template = title + description + representative diff hunk, labelled with a
category/scope *hint* used only to guarantee balanced coverage at seed time (the hints are
NEVER fed to enrichment — Phase 3 re-derives category/scope from the content for real).

Run once (needs ANTHROPIC_API_KEY):
    uv run python -m corpus.generate_corpus
Writes corpus/pr_templates.json (stable, re-runnable, version-controllable).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Literal

from pydantic import BaseModel

from ai.client import OPUS, get_client
from ai.schemas import Category, Scope

OUT = Path(__file__).parent / "pr_templates.json"

CATEGORIES: list[Category] = [
    "Feature", "BugFix", "Refactor", "Infrastructure", "Security", "Documentation"
]
# Spread scopes so the demo profile has range. ~7 per category => ~42 templates.
SCOPE_PLAN: list[Scope] = [
    "trivial", "small", "small", "moderate", "moderate", "substantial", "major"
]


class PRTemplate(BaseModel):
    category_hint: Category
    scope_hint: Scope
    title: str
    description: str
    diff: str  # a representative unified-diff hunk


class TemplateBatch(BaseModel):
    templates: list[PRTemplate]


SYSTEM = (
    "You generate realistic pull-request training data for an engineering-analytics tool. "
    "Each PR must look like real software work: a concise conventional title, a 2-4 sentence "
    "description, and a representative unified-diff hunk (realistic file paths, +/- lines, "
    "real-looking code — not placeholders). Vary subsystems (auth, billing, api, db, "
    "frontend, infra, etc.). Make the diff's actual content match the requested category and "
    "scope so an AI reading ONLY the diff would independently reach the same read."
)


async def gen_category(category: Category) -> list[PRTemplate]:
    client = get_client()
    scopes = ", ".join(SCOPE_PLAN)
    user = (
        f"Generate {len(SCOPE_PLAN)} pull requests in the '{category}' category, one for "
        f"each of these scopes in order: {scopes}. 'trivial' = a few lines; 'major' = a "
        f"large, multi-file change. Set category_hint='{category}' and scope_hint to the "
        f"matching scope. Make each diff genuinely representative of that scope."
    )
    msg = await client.messages.parse(
        model=OPUS,
        max_tokens=8000,
        system=SYSTEM,
        messages=[{"role": "user", "content": user}],
        output_format=TemplateBatch,
    )
    return msg.parsed_output.templates


async def main() -> None:
    batches = await asyncio.gather(*(gen_category(c) for c in CATEGORIES))
    templates = [t.model_dump() for batch in batches for t in batch]
    OUT.write_text(json.dumps(templates, indent=2))
    print(f"Wrote {len(templates)} PR templates -> {OUT}")
    # coverage report
    from collections import Counter
    cats = Counter(t["category_hint"] for t in templates)
    scopes = Counter(t["scope_hint"] for t in templates)
    print("by category:", dict(cats))
    print("by scope:   ", dict(scopes))


if __name__ == "__main__":
    asyncio.run(main())
