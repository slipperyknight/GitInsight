"""analytics/summaries.py — narrative summaries (the product's hero feature).

CLAUDE.md positions GitInsight as narrative-and-automation led. Summaries are written by
Claude (Sonnet — daily/weekly per the model-tiering table) from the structured ai_* data,
NOT from raw diffs again. The ai_impact_summary field is triple-use: it feeds the metric,
the drill-down receipt, AND this team-summary sentence.

The Claude call is the real production path (text_completion → Sonnet). If ANTHROPIC_API_KEY
is absent (prototype, pre-key), we fall back to a DETERMINISTIC, clearly-labelled summary
built from the same ai_* rows so the endpoints stay functional offline. The fallback is not
the product — it is a placeholder that disappears the moment a key is present.
"""

from __future__ import annotations

import os
from collections import Counter
from datetime import datetime
from uuid import UUID

import asyncpg

from ai.client import SONNET, text_completion

_TEAM_SYSTEM = (
    "You write a concise weekly engineering summary for a manager. Use only the provided "
    "structured PR impact data. 2-4 sentences. Lead with the narrative of what shipped and "
    "its risk profile; mention test coverage and breadth of subsystems. Neutral, evidence-"
    "based tone — this surfaces evidence for a human, it is NOT a performance rating."
)
_SELF_SYSTEM = (
    "You write a short, encouraging weekly digest addressed to an engineer about their own "
    "work. Use only the provided structured PR impact data. 2-3 sentences. Factual and "
    "self-reflective; highlight what shipped and where focus went. No score, no ranking."
)


async def _recent_pr_facts(
    conn: asyncpg.Connection,
    author_ids: list[UUID] | None,
    start: datetime,
    end: datetime,
    include_unattributed: bool,
    limit: int = 25,
) -> list[dict]:
    where = ["state = 'merged'", "merged_at >= $1", "merged_at < $2", "ai_category IS NOT NULL"]
    params: list = [start, end]
    if author_ids is not None and include_unattributed:
        params.append(author_ids)
        where.append(f"(author_id = ANY(${len(params)}::uuid[]) OR author_id IS NULL)")
    elif author_ids is not None:
        params.append(author_ids)
        where.append(f"author_id = ANY(${len(params)}::uuid[])")
    params.append(limit)
    rows = await conn.fetch(
        f"SELECT ai_category, ai_scope, ai_risk, ai_has_tests, ai_surfaces, ai_impact_summary "
        f"FROM pull_requests WHERE {' AND '.join(where)} "
        f"ORDER BY merged_at DESC LIMIT ${len(params)}",
        *params,
    )
    return [dict(r) for r in rows]


def _deterministic_summary(facts: list[dict], *, who: str) -> str:
    if not facts:
        return f"(no AI summary — no merged PRs in this window for {who}.)"
    cats = Counter(f["ai_category"] for f in facts)
    tested = sum(1 for f in facts if f["ai_has_tests"])
    high_risk = sum(1 for f in facts if f["ai_risk"] == "high")
    cat_phrase = ", ".join(f"{n} {c.lower()}" for c, n in cats.most_common())
    return (
        f"[auto/non-AI placeholder] {who} merged {len(facts)} PR(s): {cat_phrase}. "
        f"{tested}/{len(facts)} included tests; {high_risk} high-risk. "
        f"Set ANTHROPIC_API_KEY and run enrichment for the real narrative summary."
    )


def _facts_to_prompt(facts: list[dict]) -> str:
    lines = []
    for f in facts:
        surfaces = ", ".join(f["ai_surfaces"]) if f.get("ai_surfaces") else "-"
        lines.append(
            f"- [{f['ai_category']}/{f['ai_scope']}/{f['ai_risk']} risk] "
            f"tests={f['ai_has_tests']} surfaces=({surfaces}): {f['ai_impact_summary']}"
        )
    return "Merged PRs this window:\n" + "\n".join(lines)


async def _summarize(system: str, facts: list[dict], *, who: str) -> str:
    if not os.getenv("ANTHROPIC_API_KEY"):
        return _deterministic_summary(facts, who=who)
    if not facts:
        return f"No merged PRs in this window for {who}."
    return await text_completion(
        model=SONNET, system=system, user_content=_facts_to_prompt(facts), max_tokens=400
    )


async def team_weekly_summary(
    conn: asyncpg.Connection, member_ids: list[UUID], start: datetime, end: datetime,
    *, team_name: str = "the team", include_unattributed: bool = False,
) -> str:
    facts = await _recent_pr_facts(conn, member_ids, start, end, include_unattributed)
    return await _summarize(_TEAM_SYSTEM, facts, who=team_name)


async def self_weekly_summary(
    conn: asyncpg.Connection, user_id: UUID, start: datetime, end: datetime, *, name: str = "you",
) -> str:
    facts = await _recent_pr_facts(conn, [user_id], start, end, include_unattributed=False)
    return await _summarize(_SELF_SYSTEM, facts, who=name)
