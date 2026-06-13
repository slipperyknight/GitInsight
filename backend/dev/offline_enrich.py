"""dev/offline_enrich.py — DEV-ONLY heuristic stand-in for enrich.py (NO API key).

⚠️  This is NOT the production enrichment path. `enrich.py` (real Haiku/Sonnet calls) is the
    authentic path per CLAUDE.md — "do not stub" the AI. This module exists purely so Phase 4
    (visible_subjects + 5-axis rollup + endpoints) can be built and verified offline before an
    ANTHROPIC_API_KEY is available. It populates the SAME ai_* columns enrich.py writes, using
    a deterministic heuristic over the same title/diff content. When the key lands, run the
    real `enrich.py` — it re-reads the rows and OVERWRITES these placeholder values.

It deliberately reuses enrich.py's exact DB read/write shape (same SELECTs, same UPDATEs,
same ai_schemas types) so swapping back to the real path changes nothing downstream.

Run:
    uv run python -m dev.offline_enrich
"""

from __future__ import annotations

import asyncio
import json
import re

from ai.schemas import CommitCategory, PRImpact, Category, Scope, Risk
from db.session import admin_session, close_pools

# --- heuristic knobs -------------------------------------------------------

_PREFIX_CATEGORY: list[tuple[str, Category]] = [
    ("feat", "Feature"),
    ("fix", "BugFix"),
    ("refactor", "Refactor"),
    ("perf", "Refactor"),
    ("chore", "Infrastructure"),
    ("build", "Infrastructure"),
    ("ci", "Infrastructure"),
    ("docs", "Documentation"),
]
_SCOPE_ORDER: list[Scope] = ["trivial", "small", "moderate", "substantial", "major"]
# upper bound (inclusive) of changed diff lines for each scope bucket
_SCOPE_THRESHOLDS: list[tuple[int, Scope]] = [
    (3, "trivial"), (10, "small"), (22, "moderate"), (45, "substantial")
]  # > 45 => major
_RISK_BY_SCOPE: dict[Scope, Risk] = {
    "trivial": "low", "small": "low", "moderate": "medium",
    "substantial": "medium", "major": "high",
}
# generic path segments that are not product subsystems
_NON_SURFACE = {"tests", "test", "__tests__", "dev", "null", "spec", "specs"}
_FILE_EXT_SURFACE = {"md": "docs", "yml": "infra", "yaml": "infra", "sql": "db"}


def _category(text: str, *, default: Category = "Refactor") -> Category:
    head = text.strip().lower()
    if "security" in head or "hmac" in head or "rls" in head or "isolation" in head:
        # security-flavoured fixes read as Security regardless of prefix
        if head.startswith("fix") or "secur" in head or "isolation" in head or "rls" in head:
            return "Security"
    for prefix, cat in _PREFIX_CATEGORY:
        if head.startswith(prefix):
            return cat
    return default


def _changed_lines(diff: str) -> int:
    n = 0
    for line in diff.splitlines():
        if line.startswith(("+++", "---", "@@")):
            continue
        if line.startswith(("+", "-")):
            n += 1
    return n


def _scope(diff: str) -> Scope:
    n = _changed_lines(diff)
    for upper, scope in _SCOPE_THRESHOLDS:
        if n <= upper:
            return scope
    return "major"


def _surfaces(diff: str) -> list[str]:
    out: list[str] = []
    for m in re.finditer(r"^[+-]{3} [ab]/(\S+)", diff, re.MULTILINE):
        path = m.group(1)
        if path == "dev/null":
            continue
        seg = path.split("/", 1)[0]
        if "/" not in path:  # root file — classify by extension
            ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
            seg = _FILE_EXT_SURFACE.get(ext, seg)
        if seg.lower() in _NON_SURFACE:
            continue
        if seg not in out:
            out.append(seg)
    return out or ["general"]


def _has_tests(diff: str) -> bool:
    low = diff.lower()
    return "test" in low or "spec" in low or "__tests__" in low


def _risk(category: Category, scope: Scope) -> Risk:
    base = _RISK_BY_SCOPE[scope]
    if category == "Security":
        return "high" if scope in ("moderate", "substantial", "major") else "medium"
    return base


def categorize_commit(message: str) -> CommitCategory:
    cat = _category(message)
    return CommitCategory(category=cat, summary=f"{cat} change: {message.strip()[:120]}")


def impact_read(title: str, description: str, diff: str) -> PRImpact:
    cat = _category(title)
    scope = _scope(diff)
    risk = _risk(cat, scope)
    surfaces = _surfaces(diff)
    has_tests = _has_tests(diff)
    summary = (
        f"{scope.capitalize()} {cat.lower()} touching {', '.join(surfaces)}"
        f"{'; adds tests' if has_tests else ''} ({risk} risk)."
    )
    return PRImpact(
        category=cat, scope=scope, risk=risk, surfaces=surfaces,
        has_tests=has_tests, impact_summary=summary,
    )


async def enrich_commits(conn) -> int:
    rows = await conn.fetch(
        "SELECT id, message FROM commits WHERE ai_category IS NULL AND message IS NOT NULL"
    )
    for row in rows:
        res = categorize_commit(row["message"])
        await conn.execute(
            "UPDATE commits SET ai_category=$1, ai_summary=$2 WHERE id=$3",
            res.category, res.summary, row["id"],
        )
    return len(rows)


async def enrich_prs(conn) -> int:
    rows = await conn.fetch(
        "SELECT id, title, description, diff FROM pull_requests "
        "WHERE state='merged' AND ai_category IS NULL"
    )
    for row in rows:
        res = impact_read(row["title"] or "", row["description"] or "", row["diff"] or "")
        await conn.execute(
            "UPDATE pull_requests SET ai_category=$1, ai_scope=$2, ai_risk=$3, "
            "ai_surfaces=$4, ai_has_tests=$5, ai_impact_summary=$6 WHERE id=$7",
            res.category, res.scope, res.risk, json.dumps(res.surfaces),
            res.has_tests, res.impact_summary, row["id"],
        )
    return len(rows)


async def main() -> None:
    print("⚠️  DEV offline enrichment (heuristic — not real AI). Run enrich.py once you have a key.")
    async with admin_session() as conn:
        nc = await enrich_commits(conn)
        print(f"  categorized {nc} commits (heuristic)")
        npr = await enrich_prs(conn)
        print(f"  impact-read {npr} merged PRs (heuristic)")
    await close_pools()
    print("Offline enrichment complete.")


if __name__ == "__main__":
    asyncio.run(main())
