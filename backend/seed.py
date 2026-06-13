"""seed.py — synthetic org graph + activity (prototype substitute for webhook ingestion).

Builds two orgs (Acme = the demo org; Globex = a second org so the API can prove cross-org
403s on real data), samples the PR corpus across engineers and an 8-week window, and writes
commits / pull_requests / reviews. Leaves the ai_* columns NULL — enrich.py fills them.

Deliberately includes the locked edge cases (CLAUDE.md):
  * Unattributed bucket: commits/PRs from unmapped logins (dependabot[bot], a contractor)
    with user_id / author_id = NULL.
  * Scoped roles: one person who is `manager` on one team and `engineer` on another.

Run (no API key needed; needs the corpus file from generate_corpus.py):
    uv run python seed.py
"""

from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg

from db.session import admin_session, close_pools

CORPUS_PATH = Path(__file__).parent / "corpus" / "pr_templates.json"
NOW = datetime.now(timezone.utc)
RNG = random.Random(42)  # deterministic

ALL_TABLES = [
    "reviews", "commits", "pull_requests", "projects", "repositories",
    "role_assignments", "team_memberships", "teams", "users", "organizations",
]


def _ts(weeks_ago: float, hour: int = 10) -> datetime:
    return (NOW - timedelta(weeks=weeks_ago)).replace(hour=hour, minute=RNG.randint(0, 59))


def _sha() -> str:
    return "".join(RNG.choice("0123456789abcdef") for _ in range(40))


async def wipe(conn: asyncpg.Connection) -> None:
    await conn.execute(f"TRUNCATE {', '.join(ALL_TABLES)} RESTART IDENTITY CASCADE;")


async def _add_user(conn, org_id, email, name, vcs_logins) -> str:
    return await conn.fetchval(
        "INSERT INTO users (org_id, email, name, vcs_identities) "
        "VALUES ($1,$2,$3,$4) RETURNING id",
        org_id, email, name, json.dumps({"github": vcs_logins}),
    )


async def _add_team(conn, org_id, name, parent=None) -> str:
    return await conn.fetchval(
        "INSERT INTO teams (org_id, name, parent_team_id) VALUES ($1,$2,$3) RETURNING id",
        org_id, name, parent,
    )


async def _member(conn, org_id, team_id, user_id) -> None:
    await conn.execute(
        "INSERT INTO team_memberships (org_id, team_id, user_id) VALUES ($1,$2,$3)",
        org_id, team_id, user_id,
    )


async def _role(conn, org_id, user_id, role, scope_type, scope_id) -> None:
    await conn.execute(
        "INSERT INTO role_assignments (org_id, user_id, role, scope_type, scope_id) "
        "VALUES ($1,$2,$3,$4,$5)",
        org_id, user_id, role, scope_type, scope_id,
    )


async def _repo(conn, org_id, name) -> str:
    return await conn.fetchval(
        "INSERT INTO repositories (org_id, vcs_provider, external_id, name) "
        "VALUES ($1,'github',$2,$3) RETURNING id",
        org_id, f"ext-{name}", name,
    )


async def _pr(conn, org_id, repo_id, author_id, number, tmpl, state, created, merged) -> str:
    return await conn.fetchval(
        "INSERT INTO pull_requests "
        "(org_id, repo_id, author_id, number, title, description, diff, state, "
        " created_at, merged_at) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10) RETURNING id",
        org_id, repo_id, author_id, number, tmpl["title"], tmpl["description"],
        tmpl["diff"], state, created, merged,
    )


async def _commit(conn, org_id, repo_id, user_id, message, authored) -> None:
    await conn.execute(
        "INSERT INTO commits (org_id, repo_id, user_id, sha, message, authored_at) "
        "VALUES ($1,$2,$3,$4,$5,$6)",
        org_id, repo_id, user_id, _sha(), message, authored,
    )


async def _review(conn, org_id, pr_id, reviewer_id, state, submitted) -> None:
    await conn.execute(
        "INSERT INTO reviews (org_id, pr_id, reviewer_id, state, submitted_at) "
        "VALUES ($1,$2,$3,$4,$5)",
        org_id, pr_id, reviewer_id, state, submitted,
    )


async def build_acme(conn, corpus: list[dict]) -> None:
    org = await conn.fetchval(
        "INSERT INTO organizations (name, plan) VALUES ('Acme Corp','growth') RETURNING id"
    )
    # GUC needed? No — superuser bypasses RLS. Insert freely.

    # Teams: Platform (parent) -> Billing, Auth (one nesting level)
    platform = await _add_team(conn, org, "Platform")
    billing = await _add_team(conn, org, "Billing", parent=platform)
    auth = await _add_team(conn, org, "Auth", parent=platform)

    # People
    sarah = await _add_user(conn, org, "sarah@acme.test", "Sarah Chen", ["sarah-gh"])
    alex = await _add_user(conn, org, "alex@acme.test", "Alex Kim", ["alex-gh"])
    sam = await _add_user(conn, org, "sam@acme.test", "Sam Ortiz", ["sam-gh"])
    jordan = await _add_user(conn, org, "jordan@acme.test", "Jordan Lee", ["jordan-gh"])
    priya = await _add_user(conn, org, "priya@acme.test", "Priya Rao", ["priya-gh"])
    riya = await _add_user(conn, org, "riya@acme.test", "Riya Das", ["riya-gh"])

    # Memberships
    for u in (sarah, alex, sam, jordan):
        await _member(conn, org, billing, u)
    for u in (jordan, priya):  # jordan is ALSO on Auth
        await _member(conn, org, auth, u)

    # Roles (authority lives here, not users.role)
    await _role(conn, org, sarah, "manager", "team", billing)   # manages Billing
    await _role(conn, org, jordan, "manager", "team", auth)     # EDGE CASE: dual role —
    #   jordan manages Auth but is an engineer on Billing
    await _role(conn, org, riya, "org_admin", "org", None)      # org admin
    for u in (alex, sam, jordan):
        await _role(conn, org, u, "engineer", "team", billing)
    await _role(conn, org, priya, "engineer", "team", auth)

    # Repos & projects
    billing_repo = await _repo(conn, org, "billing-service")
    auth_repo = await _repo(conn, org, "auth-service")
    core_repo = await _repo(conn, org, "platform-core")
    await conn.execute(
        "INSERT INTO projects (org_id, name, status) VALUES "
        "($1,'Project Phoenix','green'),($1,'Legacy Migration','yellow')", org,
    )

    # Activity: map each engineer to a primary repo
    plan = [
        (alex, billing_repo), (sam, billing_repo), (jordan, billing_repo),
        (priya, auth_repo), (sarah, core_repo),
    ]
    reviewers = [sarah, alex, sam, jordan, priya]
    pr_no = {billing_repo: 100, auth_repo: 100, core_repo: 100}

    for author, repo in plan:
        n = RNG.randint(4, 6)
        for _ in range(n):
            tmpl = RNG.choice(corpus)
            pr_no[repo] += 1
            weeks = RNG.uniform(0.2, 7.5)
            created = _ts(weeks)
            # most merged; a couple left open & old enough to be "blocked"
            if RNG.random() < 0.18:
                state, merged = "open", None
            else:
                state = "merged"
                merged = created + timedelta(hours=RNG.randint(3, 60))
            pr_id = await _pr(conn, org, repo, author, pr_no[repo], tmpl, state,
                              created, merged)
            # commits backing the PR
            for _ in range(RNG.randint(1, 4)):
                await _commit(conn, org, repo, author, tmpl["title"],
                              created - timedelta(hours=RNG.randint(1, 20)))
            # reviews (turnaround = a few hours after creation)
            for rev in RNG.sample(reviewers, RNG.randint(1, 2)):
                if rev == author:
                    continue
                await _review(conn, org, pr_id, rev,
                              RNG.choice(["approved", "commented", "changes_requested"]),
                              created + timedelta(hours=RNG.randint(1, 8)))

    # --- Unattributed bucket: unmapped logins (NULL author/user) ---
    tmpl = RNG.choice(corpus)
    pr_no[core_repo] += 1
    dep_created = _ts(1.0)
    await _pr(conn, org, core_repo, None, pr_no[core_repo],
              {"title": "Bump lodash 4.17.20 -> 4.17.21",
               "description": "Automated dependency update.", "diff": tmpl["diff"]},
              "merged", dep_created, dep_created + timedelta(hours=2))
    await _commit(conn, org, core_repo, None, "chore(deps): bump lodash", _ts(1.0))
    await _commit(conn, org, billing_repo, None, "fix: patch from external contractor",
                  _ts(2.0))

    print(f"  Acme org: {org}")
    print("  Dual-role user (manager Auth + engineer Billing): Jordan Lee")
    print("  Unattributed: dependabot[bot] PR + contractor commit (NULL author/user)")


async def build_globex(conn, corpus: list[dict]) -> None:
    org = await conn.fetchval(
        "INSERT INTO organizations (name, plan) VALUES ('Globex','startup') RETURNING id"
    )
    team = await _add_team(conn, org, "Core")
    gus = await _add_user(conn, org, "gus@globex.test", "Gus Vale", ["gus-gh"])
    await _member(conn, org, team, gus)
    await _role(conn, org, gus, "manager", "team", team)
    repo = await _repo(conn, org, "globex-app")
    for i in range(3):
        tmpl = RNG.choice(corpus)
        created = _ts(RNG.uniform(0.5, 4))
        await _pr(conn, org, repo, gus, 10 + i, tmpl, "merged", created,
                  created + timedelta(hours=5))
        await _commit(conn, org, repo, gus, tmpl["title"], created)
    print(f"  Globex org: {org} (for cross-org 403 tests)")


async def main() -> None:
    if not CORPUS_PATH.exists():
        raise SystemExit(
            f"Corpus not found at {CORPUS_PATH}. Run: uv run python -m corpus.generate_corpus"
        )
    corpus = json.loads(CORPUS_PATH.read_text())
    print(f"Loaded {len(corpus)} PR templates.")
    async with admin_session() as conn:
        await wipe(conn)
        print("Building Acme...")
        await build_acme(conn, corpus)
        print("Building Globex...")
        await build_globex(conn, corpus)

    # summary counts
    async with admin_session() as conn:
        for t in ("organizations", "users", "teams", "role_assignments",
                  "pull_requests", "commits", "reviews"):
            c = await conn.fetchval(f"SELECT count(*) FROM {t}")
            print(f"  {t:18} {c}")
        unattr_pr = await conn.fetchval(
            "SELECT count(*) FROM pull_requests WHERE author_id IS NULL")
        unattr_c = await conn.fetchval(
            "SELECT count(*) FROM commits WHERE user_id IS NULL")
        print(f"  unattributed PRs={unattr_pr} commits={unattr_c}")
    await close_pools()
    print("Seed complete.")


if __name__ == "__main__":
    asyncio.run(main())
