"""enrich.py — direct async AI enrichment loop (prototype substitute for Batches + Celery).

  * Per-commit  -> Haiku, message-only categorization  -> commits.ai_category / ai_summary
  * Per-merged-PR -> Sonnet, full-diff impact read     -> pull_requests.ai_* (6 columns)

Concurrency-capped with a semaphore. The `messages.parse()` structured-output call shape is
identical to what a Batches job would submit, so swapping to the Batches API later is a
~10-line change (CLAUDE.md). Connects as the trusted superuser (bypasses RLS) — enrichment
is identity/org-agnostic, including the unattributed bucket.

Run (needs ANTHROPIC_API_KEY, and seed.py must have run):
    uv run python enrich.py
"""

from __future__ import annotations

import asyncio
import json

from ai.client import HAIKU, SONNET, parse_structured
from ai.schemas import CommitCategory, PRImpact
from db.session import admin_session, close_pools

CONCURRENCY = 6

COMMIT_SYSTEM = (
    "You categorize a single git commit from its message alone. Choose the best category "
    "and write one short human-readable summary sentence. Message-only — do not invent diff "
    "details."
)
PR_SYSTEM = (
    "You read a merged pull request (title, description, and a representative diff hunk) and "
    "produce a structured impact assessment. Judge scope and risk from what the diff actually "
    "changes, not from the message's tone. Set has_tests=true only if the diff adds or edits "
    "tests. List the concrete subsystems touched in 'surfaces'. impact_summary is one "
    "sentence an engineer would accept as an accurate receipt of the work."
)


async def enrich_commits(conn, sem: asyncio.Semaphore) -> int:
    rows = await conn.fetch(
        "SELECT id, message FROM commits WHERE ai_category IS NULL AND message IS NOT NULL"
    )

    async def one(row):
        async with sem:
            res = await parse_structured(
                model=HAIKU, system=COMMIT_SYSTEM,
                user_content=f"Commit message:\n{row['message']}",
                output_format=CommitCategory, max_tokens=300,
            )
        return row["id"], res

    results = await asyncio.gather(*(one(r) for r in rows))
    for cid, res in results:
        await conn.execute(
            "UPDATE commits SET ai_category=$1, ai_summary=$2 WHERE id=$3",
            res.category, res.summary, cid,
        )
    return len(results)


async def enrich_prs(conn, sem: asyncio.Semaphore) -> int:
    rows = await conn.fetch(
        "SELECT id, title, description, diff FROM pull_requests "
        "WHERE state='merged' AND ai_category IS NULL"
    )

    async def one(row):
        content = (
            f"Title: {row['title']}\n\nDescription:\n{row['description']}\n\n"
            f"Diff:\n{row['diff']}"
        )
        async with sem:
            res = await parse_structured(
                model=SONNET, system=PR_SYSTEM, user_content=content,
                output_format=PRImpact, max_tokens=1024,
            )
        return row["id"], res

    results = await asyncio.gather(*(one(r) for r in rows))
    for pid, res in results:
        await conn.execute(
            "UPDATE pull_requests SET ai_category=$1, ai_scope=$2, ai_risk=$3, "
            "ai_surfaces=$4, ai_has_tests=$5, ai_impact_summary=$6 WHERE id=$7",
            res.category, res.scope, res.risk, json.dumps(res.surfaces),
            res.has_tests, res.impact_summary, pid,
        )
    return len(results)


async def main() -> None:
    sem = asyncio.Semaphore(CONCURRENCY)
    async with admin_session() as conn:
        print("Categorizing commits (Haiku)...")
        nc = await enrich_commits(conn, sem)
        print(f"  enriched {nc} commits")
        print("Impact-reading merged PRs (Sonnet)...")
        npr = await enrich_prs(conn, sem)
        print(f"  enriched {npr} PRs")
    await close_pools()
    print("Enrichment complete.")


if __name__ == "__main__":
    asyncio.run(main())
