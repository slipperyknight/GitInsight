# GitInsight — Engineer Activity Intelligence Platform

A B2B SaaS platform that automatically turns the scattered output of software engineers — commits, pull requests, reviews, deployments — into business-readable narrative, automated documentation, and defensible per-engineer insight, across multiple repositories and projects.

---

## 0. Key Product Decisions

This section records the deliberate choices that shape everything below. Read it first.

1. **Narrative-and-automation led, not surveillance led.** The hero of the product is *automated work narrative* (daily/weekly summaries, blocked-work alerts, release notes) — the things teams actively want. Individual analytics are rich and central, but built responsibly (see #3). Same data pipeline, engineer-friendly framing.
2. **RBAC is a core architectural primitive, not a Phase-4 enterprise checkbox.** Who sees *what altitude of data about whom* is enforced from day one. Retrofitting per-row authorization later is prohibitively painful.
3. **Lean into individual metrics — done defensibly.** Per-person data is a core selling point, but:
   - Output is a **multi-axis profile, never a single composite score** (no leaderboard by default).
   - Primary view is **per-person trend over time**, not peer ranking.
   - Substance is **read from PR diffs by AI** (measuring impact, not counting volume).
   - Every number **drills to its receipts** and reads are **contestable**.
   - Perf-review use is **evidence for a human decision, with mandatory human-in-the-loop — never an auto-rater.** This keeps us clear of automated-employment-decision regulation (NYC Local Law 144, EU AI Act high-risk category) and keeps engineers on side.
4. **AI engine is Anthropic Claude, tiered by cost.** Haiku for high-volume classification, Sonnet for impact analysis and summaries, Opus for low-volume high-value reports. Batches + prompt caching for margin.
5. **MVP stack is deliberately small.** No Elasticsearch, no Kubernetes for the MVP — Postgres-only storage, single-host/Compose deploy. Both are explicitly deferred until scale demands them.

---

## 1. Product Requirements Document (PRD)

### Executive Summary
GitInsight gives engineering managers, directors, and executives an automatically-maintained, business-readable view of the work their teams actually do — and gives engineers an automatically-maintained record of their own work. It aggregates signals from version control (and later CI/CD and ticketing), uses AI to translate technical activity into readable narrative, and surfaces what needs attention (blocked PRs, review bottlenecks, delivery risk). Individual analytics are rich but framed as evidence for human judgment, never as an automated verdict.

### Core Problem
Engineering work is scattered across commits, PRs, reviews, deployments, and tickets in multiple systems. Managers can't see the shape of it without manual status-gathering; engineers spend real time writing updates and self-assessments; executives have no honest read on where engineering effort goes. GitInsight converts the raw activity into narrative, documentation, and insight automatically.

### Who It Serves (via RBAC — see §3)
- **Engineers** — their own auto-generated accomplishments digest / "brag doc" / standup feed, plus their personal metrics and trend. *First-class consumer of their own data.*
- **Managers** — auto-summaries of their team's work, blocked-work and bottleneck alerts, and per-person profiles **for their direct team only**.
- **Directors/Execs** — project health, delivery risk, work-allocation by type, team-level rollups across the org.

### Key Features
1. **VCS Integration (GitHub first):** Track commits, pull requests, branches, merges, reviews, deployments.
2. **Automated Work Narrative:** AI-generated daily reports, weekly team summaries, monthly project reports, and release notes — the product's lead feature.
3. **Attention Surfacing:** Blocked PRs, slow reviews, review bottlenecks, delivery-risk flags. "What a good manager wishes they had time to notice."
4. **AI-Powered Work Analysis:** Classify work into Feature / Bug Fix / Refactor / Infrastructure / Security / Documentation; read *impact* from diffs, not volume from line counts.
5. **Individual Insight (defensible):** Per-engineer multi-axis profile + trend over time, with full drill-down receipts. Evidence for human-run reviews, never an auto-rater.
6. **Project Intelligence:** Map activity to projects; show where effort goes by work type and subsystem.
7. **RBAC-Scoped Dashboards:** Engineer / Manager / Director views, each showing a role-appropriate altitude of data, enforced in the backend.

### MVP Scope
- **Integrations:** GitHub Cloud only (GitHub App + webhooks).
- **Tracking:** Commits, PRs, and code reviews (with timestamps).
- **RBAC:** Orgs, teams, team-derived management, three roles (engineer / manager / org-admin), org-level isolation + the visibility predicate (§3). Built in from the start.
- **AI Engine:** Per-commit categorization (Haiku) + per-merged-PR impact read (Sonnet, structured output) + nightly team summaries (Sonnet via Batches).
- **Individual metrics:** 5-axis profile + per-person trend + drill-down receipts.
- **Dashboards:** Manager Dashboard (timeline, velocity context, AI team summary, blocked-PR alerts) + the engineer's own accomplishments digest.
- **Reporting:** Automated weekly email summaries.

### Explicitly Deferred (Post-MVP)
- Elasticsearch (Postgres FTS covers MVP search), Kubernetes (single-host/Compose for MVP).
- GitLab, Bitbucket, Jira, Linear, Slack/Teams integrations.
- Nested team subtrees beyond one level, explicit per-user reporting lines, custom roles, fine-grained capability editing.
- Cohort comparison and any cross-person/side-by-side views (org-gated when added — never default).
- Org-gated skip-level individual drill-down and org-gated composite score (only if a deal demands them).
- SOC2, SSO/SAML, on-prem, custom-trained models.

---

## 2. System Architecture

Cloud-native, but deliberately minimal for the MVP.

### MVP Stack
- **Frontend:** Next.js + TypeScript
- **Backend:** FastAPI (async — fits webhook ingestion)
- **Database:** PostgreSQL (the entire storage + search tier for the MVP; use Postgres full-text search, not Elasticsearch)
- **Queue/Workers:** Redis as broker + Celery/RQ workers
- **AI:** Anthropic Claude — Haiku / Sonnet / Opus, tiered (see §6)
- **Deploy:** Docker Compose on a single host (Fly.io / Railway / ECS). **No Kubernetes yet.**

### Deferred Infrastructure
- **Elasticsearch** — add in Phase 3 only if Postgres search latency actually hurts.
- **Kubernetes** — Phase 4, when multi-tenant scale and ops staffing justify it.

### Data Flow
1. **Ingestion:** FastAPI webhook workers receive GitHub events and push them to a Redis queue.
2. **Processing:** Celery/RQ workers pull events, persist relational data to Postgres, and dispatch AI work:
   - per-commit categorization (Haiku, real-time-ish),
   - per-merged-PR impact analysis (Sonnet, structured output),
   - nightly team/project summaries (Sonnet via the Batches API).
3. **Storage:** All relational data and AI outputs in PostgreSQL. (Searchable summaries live in Postgres FTS for now.)
4. **Presentation:** Next.js queries FastAPI; every analytics query is scoped through the RBAC policy layer (§3) before returning rows.

---

## 3. RBAC & Org Model (core primitive)

Two distinct boundaries, enforced differently:

- **Tenant isolation (catastrophic if breached):** Org A must never see Org B. Enforced with **Postgres Row-Level Security** as a hard backstop — every tenant-scoped table carries `org_id`; the session sets the org from the authenticated token; an RLS policy asserts it. Simple, cheap, DB-enforced even if app code forgets a filter.
- **Intra-org visibility (a feature, survivable if buggy):** Who sees whom *within* an org. Enforced in a single, well-tested **application policy layer** — too nuanced (recursive team trees, multi-role composition) to live comfortably in RLS.

### Org structure
`organizations` → `teams` (nestable via `parent_team_id`) → `team_memberships` (many-to-many; people are on multiple teams in reality).

**Management is team-derived:** a manager is *scoped to a team*; their reports are that team's members. No per-user `manager_id` to drift out of sync. (Explicit reporting lines may be added later only for orgs that don't fit a team tree.)

### Roles are scoped, not global
A role is a relationship between a user and a *scope*, stored as `(user, role, scope_type, scope_id)`. One person can simultaneously be manager of Billing, IC on Architecture, and org-admin. Authority lives in `role_assignments`; `users.role` is display-only.

### The visibility predicate (decided)
"Can viewer V see **individual** metrics about subject S?", evaluated in order:
1. **Different org?** → DENY (tenant gate, always first, always hard).
2. **S is V?** → ALLOW (you always see yourself fully).
3. **Does V directly manage S's team?** → ALLOW per-person. **Direct team only** — per-person visibility does *not* cascade down the full subtree.
4. **Otherwise** → AGGREGATE-ONLY (team rollups for teams V belongs to; never S's individual rows).

Result: **individual data is visible to exactly three parties — the person, their one direct team manager, and a capability-bearing org admin.** No lateral peer visibility, no skip-level individual drill-down. This is a feature and a security-team selling point.

Implementation note: don't scatter this logic. One function — `visible_subjects(viewer, requested_scope) → (user_ids_visible_individually, teams_visible_in_aggregate)` — and every analytics query composes its `WHERE` clause from its output. One place to audit and test.

### Deliberate consequences
- **Directors lose per-person sight below their direct reports** — they get team aggregates, not individuals, for teams managed by someone else. Framed as: per-person data stays with the manager who has the context. (An org-level `allow_skiplevel_individual_view` toggle is the future escape hatch — not built now.)
- **Orphan teams are individually invisible to management.** A team with no assigned manager has members nobody can see individually (except admin). Correct behavior — so onboarding must nudge admins to assign a manager to every team.

### Capability vs role (direction, not MVP)
Model roles as mapping to **capability sets** (`view_individual_metrics`, `manage_users`, `manage_integrations`, `view_org_analytics`, `manage_billing`) so an admin can later manage the account *without* seeing metrics. MVP ships fixed roles; the capability layer is the enterprise direction.

---

## 4. Database Schema

Core relational data in PostgreSQL. (Deltas from the original: new `teams`, `team_memberships`, `role_assignments`; timestamps on activity tables; identity-mapping support.)

```sql
-- Tenancy & users
CREATE TABLE organizations (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    plan VARCHAR(50) DEFAULT 'startup'
);

CREATE TABLE users (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(id),
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(50) DEFAULT 'engineer',   -- display-only "primary role"; authority is in role_assignments
    vcs_identities JSONB                    -- admin-managed mapping of VCS logins -> this user
);

-- Org hierarchy
CREATE TABLE teams (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(id),
    parent_team_id UUID REFERENCES teams(id),
    name VARCHAR(255) NOT NULL
);

CREATE TABLE team_memberships (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(id),   -- denormalized for RLS
    team_id UUID NOT NULL REFERENCES teams(id),
    user_id UUID NOT NULL REFERENCES users(id),
    UNIQUE (team_id, user_id)
);

-- Scoped roles (the heart of RBAC)
CREATE TABLE role_assignments (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(id),
    user_id UUID NOT NULL REFERENCES users(id),
    role VARCHAR(50) NOT NULL,            -- engineer | manager | director | org_admin
    scope_type VARCHAR(20) NOT NULL,      -- 'org' | 'team'
    scope_id UUID,                        -- team_id when scope_type='team'; NULL for org-wide
    UNIQUE (user_id, role, scope_type, scope_id)
);

-- Repositories & projects
CREATE TABLE repositories (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(id),
    vcs_provider VARCHAR(50),
    external_id VARCHAR(255),
    name VARCHAR(255)
);

CREATE TABLE projects (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(id),
    name VARCHAR(255),
    status VARCHAR(50)
);

-- Activity tracking (note the timestamps — almost every feature is a time-window query)
CREATE TABLE commits (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(id),
    repo_id UUID REFERENCES repositories(id),
    user_id UUID REFERENCES users(id),    -- NULL => unattributed bucket (unmapped/bot identity)
    sha VARCHAR(40) UNIQUE NOT NULL,
    message TEXT,
    authored_at TIMESTAMPTZ,
    ai_category VARCHAR(50),              -- enum-constrained via structured output
    ai_summary TEXT
);

CREATE TABLE pull_requests (
    id UUID PRIMARY KEY,
    org_id UUID NOT NULL REFERENCES organizations(id),
    repo_id UUID REFERENCES repositories(id),
    author_id UUID REFERENCES users(id),
    state VARCHAR(50),
    created_at TIMESTAMPTZ,
    merged_at TIMESTAMPTZ,
    -- AI impact read (structured output); see §5
    ai_category VARCHAR(50),
    ai_scope VARCHAR(20),                 -- trivial | small | moderate | substantial | major
    ai_risk VARCHAR(20),                  -- low | medium | high
    ai_surfaces JSONB,                    -- subsystems touched
    ai_has_tests BOOLEAN,
    ai_impact_summary TEXT                -- triple-use: metric input, drill-down receipt, summary feed
);
```

Add indexes on the `*_at` timestamp columns and on `org_id` everywhere. Enable RLS on every `org_id`-bearing table.

### VCS identity mapping & the unattributed bucket (decided)
- Commits from VCS logins not mapped to a user go to an **`unattributed`** bucket (`user_id = NULL`).
- Unattributed activity **counts toward team/project aggregates** (honest totals) but **never appears as anyone's individual metric** (no misattribution — critical when this data touches perf reviews).
- Admins get a standing "map these identities" task and can mark an identity **bot/excluded** (CI, Dependabot) so it doesn't pollute even the aggregates.

---

## 5. Individual Metrics Design

Lean into per-person data, built so it survives a skeptical engineer.

### Profile, not score
An individual's output is a **5-axis profile** — never a single composite number (no default leaderboard):

| Axis | Captures | Why |
|---|---|---|
| **Delivery** | Work shipped (merged-and-deployed PRs, weighted by substance) | Weighted by impact, not count |
| **Collaboration** | Reviews given, review turnaround, unblocking others | Where senior engineers show up; makes the tool one they advocate for |
| **Impact/Complexity** | AI-read substance of the work | The moat — separates a race-condition fix from a rename |
| **Quality** | Tests included, low revert/hotfix rate | Rewards doing it right |
| **Breadth vs Focus** | Range of subsystems touched | Context, not judgment |

### Trend over comparison
**Primary view is per-person trend over time** — compare a person to their own trajectory, not to peers. This is the answer to "you can't compare a staff architect's 200 lines/week to a junior's 2,000." Any comparison is **within cohort** (similar role/team), never global, and never the default.

### How impact is read (and how it stays cheap)
For each unit of work, send message + diff to Claude with **structured output**:

```
{ category, scope, surfaces[], risk, has_tests, impact_summary }
```

- **Per-commit:** message-only categorization on **Haiku** — powers the timeline, trivial cost.
- **Per-merged-PR:** full-diff impact read on **Sonnet** — PRs are the unit of shipped work and ~1/10th the volume of commits, so this is where substance comes from without breaking the cost model.

`impact_summary` is triple-use: a metric input, the **drill-down receipt** an engineer sees, and a sentence that feeds the team summary. One Claude call, three products.

This is also the anti-gaming argument: impact is read from the real diff at PR level, so commit-splitting doesn't inflate it, padded lines don't help, and a boastful message over a one-line change fools nothing.

### Trust mechanics
- **Every number drills to its receipts** — the PRs/commits/reviews behind it, each with the model's read, linked to GitHub.
- **Reads are contestable** — a manager or engineer can flag a misjudged PR; this corrects the data and gives a model-quality signal.

### Perf-review boundary (decided)
The product surfaces **evidence and narrative for a human-run review, with mandatory human-in-the-loop. It never auto-rates.** This is both the ethical posture and the one that keeps GitInsight out of the automated-employment-decision regulatory bucket (NYC Local Law 144; EU AI Act high-risk worker-management). Marketed as "organized evidence for your review conversation," never "the system that decides ratings."

---

## 6. AI Engine

Anthropic Claude, tiered by cost and latency.

| Stage | Model | Why |
|---|---|---|
| Per-commit categorization | **Claude Haiku 4.5** ($1 / $5 per 1M) | High volume, simple enum classification |
| Per-PR impact read + daily/weekly summaries | **Claude Sonnet 4.6** ($3 / $15 per 1M) | Synthesis and diff-reading quality |
| Monthly exec/project reports, impact analysis | **Claude Opus 4.8** ($5 / $25 per 1M) | Low volume, quality > cost |

Margin levers (these map onto the pricing tiers):
- **Batches API** for all non-real-time work (nightly/weekly/monthly summaries) — 50% off, latency-insensitive.
- **Prompt caching** on the summary step — the instructions + team/project context are a stable prefix; only the activity list changes. ~90% cheaper on the repeated portion.
- **Structured outputs** for categorization and impact reads — enum-constrained, clean to parse, populate the `ai_*` columns directly.
- **Feed diffs selectively** — categorize cheaply from the message; only fetch and analyze the diff when the message is low-signal or at PR level (cost + GitHub rate limits).

Future (Enterprise tier): a **Claude agent** handed a repo + time window and tools (fetch commits/diffs/reviews) that writes the report autonomously — more flexible and higher quality than the fixed pipeline, held back as a differentiator.

---

## 7. API Design

RESTful endpoints in FastAPI. **Every analytics endpoint resolves through `visible_subjects()` before returning rows.**

- **`GET /api/v1/me/digest`**: The authenticated engineer's own accomplishments digest + profile/trend.
- **`GET /api/v1/engineers/{user_id}/profile`**: Individual profile + trend. Authorized per the §3 predicate (self, or direct manager, or capable admin) — otherwise 403.
- **`GET /api/v1/teams/{team_id}/summary`**: AI team summary, velocity context, blocked-work alerts, timeline. Scoped to the viewer's visible teams.
- **`GET /api/v1/analytics/org`**: Org-wide rollups (delivery, work allocation, project health) — director/admin scope.
- **`GET /api/v1/projects/{project_id}/intelligence`**: AI-categorized work and effort-by-type per project.
- **`POST /api/v1/webhooks/github`**: Ingests GitHub events asynchronously.

---

## 8. User Flows & Dashboard Wireframes

### Flow A: Manager checks daily team status
1. Lands on Manager Dashboard.
2. Sees actionable alerts ("2 PRs blocked > 48h", "review bottleneck in Auth").
3. Reads the AI Team Summary of yesterday's work.
4. Scrolls the Daily Activity Timeline for granular logs; can open any engineer's profile (direct reports only).

### Flow B: Engineer reviews their own week
1. Opens their digest.
2. Sees an auto-written summary of what they shipped, their 5-axis profile, and how it's trending.
3. Exports it as standup notes / perf-review evidence.

### Flow C: Executive reviews delivery
1. Opens the Executive Dashboard.
2. Reads work-allocation by *type* (Feature / Bugfix / Tech Debt) and project health.
3. Reviews Project Intelligence to see where effort goes. (Per-person drill-down is intentionally absent unless they directly manage a team.)

### Manager Dashboard
```text
================================================================================
[Logo] GitInsight | Dashboard | Team | Projects | Reports         [Profile]
================================================================================
Good morning, Sarah (Engineering Manager — Billing)

[Alert: 2 PRs Blocked >48h]   [Alert: Review bottleneck in Auth module]

--- TEAM ACTIVITY (Last 7 Days, context) --------------------------------------
Commits: 142 | PRs Merged: 34 | Avg Review Time: 4.2 hrs
--------------------------------------------------------------------------------

--- AI TEAM SUMMARY -----------------------------------------------------------
"The team focused on the Billing API this week. 45% of work was Feature
Development, primarily on Stripe webhook handling; bug-fix load fell vs last
week. One refactor reduced auth-module churn."
--------------------------------------------------------------------------------

--- DAILY ACTIVITY TIMELINE ---------------------------------------------------
[Today]
* 10:30 AM - Alex merged PR #102: "Implement Stripe Webhooks" [Feature, substantial]
* 09:15 AM - Jordan reviewed PR #101.
* 09:00 AM - Sam pushed 3 commits to `fix-login-bug` [Bugfix]
================================================================================
```

### Executive Dashboard
```text
================================================================================
[Logo] GitInsight | Executive Overview | Projects | Org Health     [Profile]
================================================================================

--- ORGANIZATION HEALTH -------------------------------------------------------
Active Engineers: 45 | Work Streams: 8 | Delivery Risk: LOW
--------------------------------------------------------------------------------

--- WORK ALLOCATION (AI Classified, by type) ----------------------------------
[===== Feature: 55% =====][=== Bugfix: 25% ===][= Refactor: 15% =][ Ops: 5% ]
--------------------------------------------------------------------------------

--- PROJECT INTELLIGENCE ------------------------------------------------------
Project Name        | Relative Effort  | Health Status
--------------------------------------------------------------------------------
Project Phoenix     | High             | [Green] On Track
Legacy Migration    | Medium           | [Yellow] Needs Attention
Mobile App v2.0     | High             | [Red] Blocked
================================================================================
```
*(Note: "Eng. Hours (Est)" was removed — hours-from-git is false precision. Effort is shown as relative activity, and the per-person contribution pie was dropped from the default exec view by design — see §0.3.)*

---

## 9. Development Roadmap & Monetization

### Roadmap
- **Phase 1 (Months 1–2): MVP & Core Tracking**
  GitHub App + webhook pipeline, RBAC/org model, Postgres storage, Haiku categorization + Sonnet PR-impact reads, Manager Dashboard + engineer digest, weekly email.
- **Phase 2 (Months 3–4): AI Intelligence & Reporting**
  Nightly/weekly summaries via Batches, work-allocation analytics, Executive Dashboard, prompt-caching cost optimization.
- **Phase 3 (Months 5–6): Integrations & Project Mapping**
  GitLab/Bitbucket, Jira/Linear, Project Intelligence mapping. Add Elasticsearch only if Postgres search latency demands it.
- **Phase 4 (Months 7+): Enterprise Scale**
  SSO/SAML → scoped capabilities, Kubernetes, agent-based reporting, org-gated advanced analytics, SOC2, on-prem.

### Monetization (B2B SaaS, per tracked engineer / month)
- **Tier 1 — Startup ($15):** GitHub integration, Manager dashboard + engineer digests, standard AI summaries, 30-day retention.
- **Tier 2 — Growth ($35):** Per-PR impact reads + individual profiles/trends, Executive dashboard, Project Intelligence, Jira integration, 1-year retention.
- **Tier 3 — Enterprise (~$65+, custom):** GitLab/Bitbucket + on-prem, SSO/SAML + scoped capabilities, agent-based reporting, SOC2, dedicated CSM.

The pricing tiers map directly onto the AI model tiering (§6): cheap classification underpins Startup; Sonnet impact-reads and individual analytics define Growth; Opus/agent reporting anchors Enterprise.
```
