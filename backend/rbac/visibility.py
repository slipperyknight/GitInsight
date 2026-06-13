"""rbac/visibility.py — the single intra-org visibility policy function.

CLAUDE.md mandate: "Do not scatter visibility logic." Every analytics query composes its
WHERE clause from the output of `visible_subjects()`. This module is the only place the
predicate lives.

Two authorization boundaries (CLAUDE.md §Key Architectural Constraints #1):
  * Tenant isolation (Org A vs Org B) → enforced by Postgres RLS via org_session(). This
    module always runs inside an org_session, so every query here is already org-filtered;
    rule 1 of the predicate ("different org → DENY") is therefore the RLS backstop, not
    re-implemented here.
  * Intra-org visibility → THIS function.

Predicate, per subject S, in order (CLAUDE.md):
  1. Different org           → DENY            (handled by RLS — see above)
  2. S is the viewer         → ALLOW (full / individual)
  3. Viewer directly manages S's team → ALLOW (per-person, DIRECT team only — not subtree)
  4. Otherwise               → AGGREGATE ONLY

Authority is read from `role_assignments` tuples (user, role, scope_type, scope_id) — never
from users.role (display-only), and there is no manager_id on users (management is
team-derived). A person can be manager of one team and engineer on another simultaneously.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional
from uuid import UUID

import asyncpg

# Roles that may access the org-wide analytics endpoint. This is an ENDPOINT gate, separate
# from per-subject individual visibility — a director sees org AGGREGATES, not everyone's
# individual profile (individual analytics stay constrained to teams they directly manage).
ORG_ANALYTICS_ROLES = {"director", "org_admin"}


class ScopeType(str, Enum):
    SELF = "self"
    ENGINEER = "engineer"
    TEAM = "team"
    ORG = "org"


@dataclass(frozen=True)
class Scope:
    """What the viewer is asking to see. The endpoint constructs this."""

    type: ScopeType
    user_id: Optional[UUID] = None   # for ENGINEER
    team_id: Optional[UUID] = None   # for TEAM


@dataclass
class VisibleSubjects:
    """Output of the policy. Queries filter individual metrics to `individual_user_ids` and
    aggregate metrics to `aggregate_team_ids`."""

    individual_user_ids: set[UUID] = field(default_factory=set)
    aggregate_team_ids: set[UUID] = field(default_factory=set)
    # Context the endpoint needs for its 403 / shape decisions:
    viewer_id: Optional[UUID] = None
    managed_team_ids: set[UUID] = field(default_factory=set)
    can_view_org: bool = False
    # True when the viewer asked for a specific subject (engineer/team) they may NOT see
    # individually — the endpoint turns this into a 403 (resource exists, no visibility).
    denied_individual: bool = False

    def sees_individually(self, user_id: UUID) -> bool:
        return user_id in self.individual_user_ids


async def _managed_team_ids(conn: asyncpg.Connection, viewer_id: UUID) -> set[UUID]:
    """Teams the viewer DIRECTLY manages (manager role scoped to that team)."""
    rows = await conn.fetch(
        "SELECT scope_id FROM role_assignments "
        "WHERE user_id=$1 AND role='manager' AND scope_type='team' AND scope_id IS NOT NULL",
        viewer_id,
    )
    return {r["scope_id"] for r in rows}


async def _has_org_analytics_role(conn: asyncpg.Connection, viewer_id: UUID) -> bool:
    row = await conn.fetchval(
        "SELECT 1 FROM role_assignments "
        "WHERE user_id=$1 AND scope_type='org' AND role = ANY($2::text[]) LIMIT 1",
        viewer_id, list(ORG_ANALYTICS_ROLES),
    )
    return row is not None


async def _team_member_ids(conn: asyncpg.Connection, team_ids: set[UUID]) -> set[UUID]:
    if not team_ids:
        return set()
    rows = await conn.fetch(
        "SELECT DISTINCT user_id FROM team_memberships WHERE team_id = ANY($1::uuid[])",
        list(team_ids),
    )
    return {r["user_id"] for r in rows}


async def _all_team_ids(conn: asyncpg.Connection) -> set[UUID]:
    rows = await conn.fetch("SELECT id FROM teams")
    return {r["id"] for r in rows}


async def visible_subjects(
    conn: asyncpg.Connection, viewer_id: UUID, scope: Scope
) -> VisibleSubjects:
    """Resolve what `viewer_id` may see for `scope`, within the current org_session.

    Returns the (individually-visible user ids, aggregate-only team ids) pair plus the
    context an endpoint needs to decide between 200 (full), 200 (aggregate), and 403.
    """
    managed = await _managed_team_ids(conn, viewer_id)
    can_org = await _has_org_analytics_role(conn, viewer_id)

    # Rule 2 + Rule 3: individual visibility = self ∪ members of directly-managed teams.
    individual_all = {viewer_id} | await _team_member_ids(conn, managed)

    out = VisibleSubjects(
        viewer_id=viewer_id, managed_team_ids=managed, can_view_org=can_org
    )

    if scope.type == ScopeType.SELF:
        out.individual_user_ids = {viewer_id}
        return out

    if scope.type == ScopeType.ENGINEER:
        target = scope.user_id
        if target is not None and target in individual_all:
            out.individual_user_ids = {target}          # rule 2 or 3 → ALLOW full
        else:
            out.denied_individual = True                # rule 4 → no individual view → 403
        return out

    if scope.type == ScopeType.TEAM:
        team = scope.team_id
        if team is not None and team in managed:
            # rule 3: directly manages → per-person for that team's direct members
            out.individual_user_ids = await _team_member_ids(conn, {team})
        else:
            # rule 4: not a direct manager → aggregate-only for this team
            out.aggregate_team_ids = {team} if team is not None else set()
            # the viewer can still see themselves individually if they're on the team
            out.individual_user_ids = {viewer_id} & await _team_member_ids(
                conn, {team} if team is not None else set()
            )
        return out

    if scope.type == ScopeType.ORG:
        # Org rollup: individuals only where the predicate allows (self + managed teams);
        # everything else is aggregate-only at the team grain.
        out.individual_user_ids = individual_all
        out.aggregate_team_ids = await _all_team_ids(conn) - managed
        if not can_org:
            out.denied_individual = True  # endpoint gate: only director/org_admin → 403
        return out

    return out
