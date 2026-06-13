"""analytics/rollup.py — the deterministic 5-axis profile.

CLAUDE.md: "5-axis profile is deterministic SQL over ai_* columns — NO AI in the metric
itself (keeps it auditable and contestable)." Each axis is shown as a TREND across windows,
never summed into a single composite score. No leaderboards, no peer ranking.

Weights (verbatim from CLAUDE.md):
    scope_weight: trivial=1 small=2 moderate=4 substantial=6 major=8
    risk_weight:  low=1 medium=1.5 high=2
    Delivery       = Σ scope_weight over merged PRs
    Impact/Complex = Σ (scope_weight × risk_weight) over authored merged PRs
    Collaboration  = reviews_given + turnaround signal
    Quality        = share of merged PRs with ai_has_tests (− revert rate)
    Breadth        = distinct count over ai_surfaces[]

Attribution rule (CLAUDE.md): unattributed activity (author_id IS NULL) NEVER appears in
individual metrics, but DOES count in aggregates. Individual axes filter by author_id =
ANY(ids) which excludes NULL naturally; aggregate axes opt in via include_unattributed.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from uuid import UUID

import asyncpg

# SQL fragments for the weighted axes (kept here so the weights live in exactly one place).
_SCOPE_WEIGHT = (
    "CASE ai_scope WHEN 'trivial' THEN 1 WHEN 'small' THEN 2 WHEN 'moderate' THEN 4 "
    "WHEN 'substantial' THEN 6 WHEN 'major' THEN 8 ELSE 0 END"
)
_RISK_WEIGHT = (
    "CASE ai_risk WHEN 'low' THEN 1 WHEN 'medium' THEN 1.5 WHEN 'high' THEN 2 ELSE 1 END"
)
# Fast-review credit: full credit for an instant review, decaying to 0 by 48h. Deterministic.
_TURNAROUND_BONUS = (
    "GREATEST(0, (48 - EXTRACT(EPOCH FROM (r.submitted_at - pr.created_at)) / 3600.0) / 48.0)"
)


@dataclass
class Axes:
    """The 5 axes for one (subject, window). Reported separately — never summed."""

    delivery: float = 0.0
    impact: float = 0.0
    collaboration: float = 0.0
    quality: float = 0.0
    breadth: int = 0
    # supporting counts (drill-down context, not axes)
    merged_prs: int = 0
    reviews_given: int = 0


@dataclass
class WindowAxes:
    label: str
    start: str  # ISO
    end: str    # ISO
    axes: Axes


def weekly_windows(n: int = 8, now: datetime | None = None) -> list[tuple[str, datetime, datetime]]:
    """N consecutive 1-week windows, oldest first, ending at `now`."""
    now = now or datetime.now(timezone.utc)
    out: list[tuple[str, datetime, datetime]] = []
    for k in range(n - 1, -1, -1):
        end = now - timedelta(weeks=k)
        start = end - timedelta(weeks=1)
        out.append((start.date().isoformat(), start, end))
    return out


async def _pr_axes(
    conn: asyncpg.Connection,
    author_ids: list[UUID] | None,
    start: datetime,
    end: datetime,
    include_unattributed: bool,
) -> tuple[float, float, float, int, int]:
    """Returns (delivery, impact, quality, breadth, merged_prs) over merged PRs in window."""
    where = ["pr.state = 'merged'", "pr.merged_at >= $1", "pr.merged_at < $2"]
    params: list = [start, end]
    if author_ids is not None and include_unattributed:
        params.append(author_ids)
        where.append(f"(pr.author_id = ANY(${len(params)}::uuid[]) OR pr.author_id IS NULL)")
    elif author_ids is not None:
        params.append(author_ids)
        where.append(f"pr.author_id = ANY(${len(params)}::uuid[])")
    elif include_unattributed:
        pass  # all PRs (org aggregate), attributed + unattributed
    clause = " AND ".join(where)

    row = await conn.fetchrow(
        f"SELECT "
        f"  COALESCE(SUM({_SCOPE_WEIGHT}), 0)                       AS delivery, "
        f"  COALESCE(SUM(({_SCOPE_WEIGHT}) * ({_RISK_WEIGHT})), 0)  AS impact, "
        f"  COUNT(*)                                                AS merged_prs, "
        f"  COALESCE(SUM(CASE WHEN ai_has_tests THEN 1 ELSE 0 END), 0) AS with_tests, "
        f"  COALESCE(SUM(CASE WHEN pr.title ILIKE 'revert%' THEN 1 ELSE 0 END), 0) AS reverts "
        f"FROM pull_requests pr WHERE {clause}",
        *params,
    )
    merged = row["merged_prs"]
    quality = 0.0
    if merged:
        quality = (float(row["with_tests"]) - float(row["reverts"])) / merged
    # Breadth — distinct subsystems across the same PR set.
    breadth = await conn.fetchval(
        f"SELECT COUNT(DISTINCT s) FROM pull_requests pr, "
        f"jsonb_array_elements_text(pr.ai_surfaces) s WHERE {clause}",
        *params,
    )
    return (
        float(row["delivery"]), float(row["impact"]), quality, int(breadth or 0), int(merged)
    )


async def _collab(
    conn: asyncpg.Connection,
    reviewer_ids: list[UUID] | None,
    start: datetime,
    end: datetime,
) -> tuple[float, int]:
    """Collaboration = reviews_given + turnaround bonus. Returns (collaboration, reviews_given)."""
    where = ["r.submitted_at >= $1", "r.submitted_at < $2"]
    params: list = [start, end]
    if reviewer_ids is not None:
        params.append(reviewer_ids)
        where.append(f"r.reviewer_id = ANY(${len(params)}::uuid[])")
    clause = " AND ".join(where)
    row = await conn.fetchrow(
        f"SELECT COUNT(*) AS reviews_given, "
        f"COALESCE(SUM({_TURNAROUND_BONUS}), 0) AS bonus "
        f"FROM reviews r JOIN pull_requests pr ON pr.id = r.pr_id WHERE {clause}",
        *params,
    )
    reviews = int(row["reviews_given"])
    return (reviews + float(row["bonus"]), reviews)


async def axes_for(
    conn: asyncpg.Connection,
    *,
    subject_ids: list[UUID] | None,
    start: datetime,
    end: datetime,
    include_unattributed: bool = False,
) -> Axes:
    """Compute the 5 axes for a subject set over one window.

    subject_ids=None means "all subjects in the org_session" (org aggregate). Individual
    callers pass a single id; aggregate callers pass member ids (+ include_unattributed).
    """
    delivery, impact, quality, breadth, merged = await _pr_axes(
        conn, subject_ids, start, end, include_unattributed
    )
    collaboration, reviews = await _collab(conn, subject_ids, start, end)
    return Axes(
        delivery=round(delivery, 2),
        impact=round(impact, 2),
        collaboration=round(collaboration, 2),
        quality=round(quality, 3),
        breadth=breadth,
        merged_prs=merged,
        reviews_given=reviews,
    )


async def axes_trend(
    conn: asyncpg.Connection,
    *,
    subject_ids: list[UUID] | None,
    windows: list[tuple[str, datetime, datetime]] | None = None,
    include_unattributed: bool = False,
) -> list[dict]:
    """The 5-axis trend across windows (self-comparison view — the primary product view)."""
    windows = windows or weekly_windows()
    out: list[dict] = []
    for label, start, end in windows:
        axes = await axes_for(
            conn, subject_ids=subject_ids, start=start, end=end,
            include_unattributed=include_unattributed,
        )
        out.append(
            WindowAxes(label=label, start=start.isoformat(), end=end.isoformat(), axes=axes)
        )
    return [{"label": w.label, "start": w.start, "end": w.end, "axes": asdict(w.axes)} for w in out]
