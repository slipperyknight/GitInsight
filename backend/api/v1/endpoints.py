"""api/v1/endpoints.py — the Phase 4 read API.

Every analytics endpoint:
  * resolves the viewer (prototype dev-auth: X-User-Id header),
  * opens an org_session(viewer.org_id) so Postgres RLS enforces tenant isolation,
  * calls visible_subjects(viewer, scope) and composes its filter from the result,
  * returns 403 (NOT 404) when a resource exists but the viewer lacks visibility — 404 would
    leak existence (CLAUDE.md API conventions).

No composite score is ever returned: profiles are the 5 axes as a per-window trend.
"""

from __future__ import annotations

import json
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel

from analytics.rollup import axes_trend, weekly_windows
from analytics.summaries import self_weekly_summary, team_weekly_summary
from db.session import get_admin_pool, org_session
from rbac.visibility import Scope, ScopeType, visible_subjects

router = APIRouter()


@router.get("/dev/identities")
async def dev_identities():
    """DEV-ONLY: list seeded users (across all orgs) so the prototype UI's viewer picker
    survives reseeds. Uses the admin pool (bypasses RLS) — this is the dev-auth directory,
    NOT a product endpoint. Production replaces X-User-Id dev-auth with a real session."""
    pool = await get_admin_pool()
    rows = await pool.fetch(
        "SELECT u.id, u.name, u.email, o.name AS org_name, "
        "  COALESCE(json_agg(json_build_object('role', ra.role, 'scope_type', ra.scope_type, "
        "    'team', t.name) ORDER BY ra.role) FILTER (WHERE ra.id IS NOT NULL), '[]') AS roles "
        "FROM users u "
        "JOIN organizations o ON o.id = u.org_id "
        "LEFT JOIN role_assignments ra ON ra.user_id = u.id "
        "LEFT JOIN teams t ON t.id = ra.scope_id "
        "GROUP BY u.id, u.name, u.email, o.name "
        "ORDER BY o.name, u.name"
    )
    return [
        {
            "id": str(r["id"]), "name": r["name"], "email": r["email"],
            "org_name": r["org_name"],
            "roles": json.loads(r["roles"]),
        }
        for r in rows
    ]


@router.get("/dev/teams")
async def dev_teams():
    """DEV-ONLY: list seeded teams (across all orgs) for the dashboard team picker."""
    pool = await get_admin_pool()
    rows = await pool.fetch(
        "SELECT t.id, t.name, o.name AS org_name FROM teams t "
        "JOIN organizations o ON o.id = t.org_id ORDER BY o.name, t.name"
    )
    return [
        {"id": str(r["id"]), "name": r["name"], "org_name": r["org_name"]} for r in rows
    ]


class Viewer(BaseModel):
    id: UUID
    org_id: UUID
    name: str | None


async def resolve_viewer(x_user_id: str | None) -> Viewer:
    """Prototype dev-auth: the X-User-Id header is the viewer. Production swaps this for a
    real session/JWT. Uses the admin pool only to map user → org (the auth bootstrap); all
    DATA access then goes through the RLS-enforced org_session."""
    if not x_user_id:
        raise HTTPException(status_code=401, detail="X-User-Id header required")
    try:
        uid = UUID(x_user_id)
    except ValueError:
        raise HTTPException(status_code=401, detail="X-User-Id must be a UUID")
    pool = await get_admin_pool()
    row = await pool.fetchrow("SELECT id, org_id, name FROM users WHERE id=$1", uid)
    if row is None:
        raise HTTPException(status_code=401, detail="unknown user")
    return Viewer(id=row["id"], org_id=row["org_id"], name=row["name"])


async def _receipts(conn, author_ids: list[UUID], limit: int = 10) -> list[dict]:
    """Recent merged-PR receipts (drill-down). ai_impact_summary is the receipt sentence."""
    rows = await conn.fetch(
        "SELECT number, title, ai_category, ai_scope, ai_risk, ai_surfaces, ai_has_tests, "
        "ai_impact_summary, merged_at FROM pull_requests "
        "WHERE state='merged' AND author_id = ANY($1::uuid[]) AND ai_category IS NOT NULL "
        "ORDER BY merged_at DESC LIMIT $2",
        author_ids, limit,
    )
    return [
        {
            "number": r["number"], "title": r["title"], "category": r["ai_category"],
            "scope": r["ai_scope"], "risk": r["ai_risk"],
            "surfaces": (
                json.loads(r["ai_surfaces"]) if isinstance(r["ai_surfaces"], str)
                else r["ai_surfaces"]
            ),
            "has_tests": r["ai_has_tests"], "impact_summary": r["ai_impact_summary"],
            "merged_at": r["merged_at"].isoformat() if r["merged_at"] else None,
        }
        for r in rows
    ]


@router.get("/me/digest")
async def me_digest(x_user_id: str | None = Header(default=None)):
    viewer = await resolve_viewer(x_user_id)
    windows = weekly_windows()
    async with org_session(str(viewer.org_id)) as conn:
        vs = await visible_subjects(conn, viewer.id, Scope(type=ScopeType.SELF))
        ids = list(vs.individual_user_ids)
        trend = await axes_trend(conn, subject_ids=ids, windows=windows)
        receipts = await _receipts(conn, ids)
        _, w_start, w_end = windows[-1]
        summary = await self_weekly_summary(
            conn, viewer.id, w_start, w_end, name=viewer.name or "you"
        )
    return {
        "viewer": {"id": str(viewer.id), "name": viewer.name},
        "scope": "self",
        "axes_trend": trend,
        "weekly_summary": summary,
        "recent_receipts": receipts,
    }


@router.get("/engineers/{user_id}/profile")
async def engineer_profile(user_id: UUID, x_user_id: str | None = Header(default=None)):
    viewer = await resolve_viewer(x_user_id)
    windows = weekly_windows()
    async with org_session(str(viewer.org_id)) as conn:
        # Existence check is RLS-scoped: a user in another org reads as absent (no leak).
        target = await conn.fetchrow("SELECT id, name FROM users WHERE id=$1", user_id)
        if target is None:
            raise HTTPException(status_code=404, detail="engineer not found")
        vs = await visible_subjects(
            conn, viewer.id, Scope(type=ScopeType.ENGINEER, user_id=user_id)
        )
        if vs.denied_individual:
            # Exists in-org but viewer may not see them individually → 403 (not 404).
            raise HTTPException(
                status_code=403, detail="not authorized to view this engineer individually"
            )
        trend = await axes_trend(conn, subject_ids=[user_id], windows=windows)
        receipts = await _receipts(conn, [user_id])
    return {
        "engineer": {"id": str(user_id), "name": target["name"]},
        "viewer_relationship": "self" if user_id == viewer.id else "managed",
        "axes_trend": trend,
        "recent_receipts": receipts,
    }


@router.get("/teams/{team_id}/summary")
async def team_summary(team_id: UUID, x_user_id: str | None = Header(default=None)):
    viewer = await resolve_viewer(x_user_id)
    windows = weekly_windows()
    async with org_session(str(viewer.org_id)) as conn:
        team = await conn.fetchrow("SELECT id, name FROM teams WHERE id=$1", team_id)
        if team is None:
            raise HTTPException(status_code=404, detail="team not found")
        vs = await visible_subjects(conn, viewer.id, Scope(type=ScopeType.TEAM, team_id=team_id))

        manages = team_id in vs.managed_team_ids
        if not manages and not vs.can_view_org:
            raise HTTPException(status_code=403, detail="not authorized to view this team")

        member_rows = await conn.fetch(
            "SELECT u.id, u.name FROM team_memberships tm JOIN users u ON u.id = tm.user_id "
            "WHERE tm.team_id=$1", team_id,
        )
        member_ids = [r["id"] for r in member_rows]

        # Team aggregate trend (no composite — the 5 axes, summed across members per window).
        team_trend = await axes_trend(conn, subject_ids=member_ids, windows=windows)

        # Per-person breakdown ONLY when the viewer directly manages the team (rule 3).
        per_person = []
        if manages:
            for r in member_rows:
                pp_trend = await axes_trend(conn, subject_ids=[r["id"]], windows=windows)
                per_person.append(
                    {"id": str(r["id"]), "name": r["name"], "axes_trend": pp_trend}
                )

        _, w_start, w_end = windows[-1]
        summary = await team_weekly_summary(
            conn, member_ids, w_start, w_end, team_name=team["name"]
        )
    return {
        "team": {"id": str(team_id), "name": team["name"]},
        "view": "per_person" if manages else "aggregate",
        "members_count": len(member_ids),
        "team_axes_trend": team_trend,
        "per_person": per_person,
        "weekly_summary": summary,
    }


@router.get("/analytics/org")
async def org_analytics(x_user_id: str | None = Header(default=None)):
    viewer = await resolve_viewer(x_user_id)
    windows = weekly_windows()
    async with org_session(str(viewer.org_id)) as conn:
        vs = await visible_subjects(conn, viewer.id, Scope(type=ScopeType.ORG))
        if not vs.can_view_org:
            raise HTTPException(status_code=403, detail="director/org_admin only")
        # Org aggregate includes the unattributed bucket (counts in aggregates, never in
        # individual metrics) — CLAUDE.md attribution rule.
        org_trend = await axes_trend(
            conn, subject_ids=None, windows=windows, include_unattributed=True
        )
        # Per-team aggregate breakdown (still no per-person, no composite).
        team_rows = await conn.fetch("SELECT id, name FROM teams ORDER BY name")
        per_team = []
        for t in team_rows:
            members = await conn.fetch(
                "SELECT user_id FROM team_memberships WHERE team_id=$1", t["id"]
            )
            ids = [m["user_id"] for m in members]
            per_team.append(
                {
                    "id": str(t["id"]), "name": t["name"],
                    "axes_trend": await axes_trend(conn, subject_ids=ids, windows=windows),
                }
            )
    return {
        "scope": "org",
        "org_axes_trend": org_trend,
        "per_team": per_team,
    }
