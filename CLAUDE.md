# CLAUDE.md — GitInsight

Working context for AI assistants on this codebase. Read this before writing any code.

---

## What This Is

**GitInsight** is a B2B SaaS platform that turns GitHub activity (commits, PRs, reviews) into automated narrative and per-engineer insight for engineering teams. It is positioned as *narrative-and-automation led* — the hero feature is automated summaries, not surveillance. Individual analytics are central but deliberately constrained.

Full product spec: `README.md`.

---

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js + TypeScript |
| Backend | FastAPI (async Python) |
| Database | PostgreSQL (storage + FTS) |
| Queue | Redis + Celery/RQ workers |
| AI | Anthropic Claude (Haiku / Sonnet / Opus — tiered) |
| Deploy | Docker Compose, single host |

**Do not introduce:**
- Elasticsearch (use Postgres FTS until scale demands otherwise)
- Kubernetes (Docker Compose is the MVP deploy target)
- OpenAI or any non-Anthropic AI provider

---

## Key Architectural Constraints

### 1. RBAC is a core primitive — not an afterthought

Authorization operates on two boundaries:

- **Tenant isolation** → enforced by **Postgres Row-Level Security** (RLS). Every tenant-scoped table has an `org_id` column. RLS policies filter by `org_id`. This is the hard backstop that prevents Org A from seeing Org B. Never bypass it.
- **Intra-org visibility** → enforced in a **single application policy function**: `visible_subjects(viewer, requested_scope) → (user_ids_visible_individually, teams_visible_in_aggregate)`. Do not scatter visibility logic. Every analytics query must compose its `WHERE` clause from this function's output.

The visibility predicate (in order):
1. Different org → DENY
2. S is the viewer → ALLOW (full)
3. Viewer directly manages S's team → ALLOW (per-person, direct team only — not full subtree)
4. Otherwise → AGGREGATE ONLY

### 2. Management is team-derived — no `manager_id` on users

A manager is someone with a `manager` role scoped to a team (`role_assignments` table). There is no `manager_id` column on `users`. Management authority comes from `role_assignments`, not from a hierarchical user field.

### 3. Roles are `(user, role, scope_type, scope_id)` tuples

A person can be `manager` of one team and `engineer` on another simultaneously. Do not read authority from `users.role` — that field is display-only. Read it from `role_assignments`.

### 4. Individual metrics are a profile, never a score

Never generate, store, or surface a single composite metric per engineer. The output is a 5-axis profile (Delivery, Collaboration, Impact/Complexity, Quality, Breadth/Focus). No leaderboards by default. No peer ranking. Primary view is trend over time (self-comparison).

### 5. Impact is read from PR diffs, not commit volume

- Per-commit: message-only categorization on **Haiku**
- Per-merged-PR: full diff impact read on **Sonnet** with structured output
- Never count lines of code as a proxy for impact

The `ai_impact_summary` field on `pull_requests` is triple-use: metric input, drill-down receipt, team summary sentence. One Claude call produces all three.

---

## AI Model Usage

Use the Anthropic Python SDK (`anthropic`). Match the model to the task:

| Task | Model | Notes |
|---|---|---|
| Per-commit categorization | `claude-haiku-4-5` | High volume, enum classification |
| Per-PR impact reads, daily/weekly summaries | `claude-sonnet-4-6` | Diff-reading quality |
| Monthly exec reports | `claude-opus-4-8` | Low volume, quality matters |

**Cost levers to apply:**
- Batches API for all nightly/weekly/monthly work (50% off, latency-insensitive)
- Prompt caching on stable prefixes (instructions + team context; only activity list changes)
- Structured outputs (enum-constrained) for categorization and impact reads → clean `ai_*` column values

Structured output schema for PR impact reads:
```json
{ "category": "Feature|BugFix|Refactor|Infrastructure|Security|Documentation",
  "scope": "trivial|small|moderate|substantial|major",
  "risk": "low|medium|high",
  "surfaces": ["list of subsystems"],
  "has_tests": true,
  "impact_summary": "one sentence" }
```

---

## Database Conventions

- Every table that stores org data **must have `org_id UUID NOT NULL`** and an RLS policy on it.
- Timestamp columns on activity tables: `authored_at`/`created_at`/`merged_at` must be `TIMESTAMPTZ`. Almost every feature is a time-window query — missing timestamps breaks the product.
- `commits.user_id` and `pull_requests.author_id` may be NULL — this is the **unattributed bucket** for VCS identities not mapped to a registered user. Unattributed activity counts in aggregates but never in individual metrics.
- `users.vcs_identities` (JSONB) is admin-managed: maps GitHub logins → this user record.

Core tables: `organizations`, `users`, `teams`, `team_memberships`, `role_assignments`, `repositories`, `projects`, `commits`, `pull_requests`. Full schema in `README.md §4`.

---

## What Not to Do

- Do not add a `manager_id` column to `users`.
- Do not compute a single composite score per engineer.
- Do not scatter visibility checks — use `visible_subjects()`.
- Do not use `users.role` for authorization decisions.
- Do not pull commit-level data through the expensive Sonnet model.
- Do not let unattributed commits appear as anyone's individual metrics.
- Do not position the product as an auto-rater for performance reviews. It surfaces evidence for human decisions. Mandatory human-in-the-loop. This keeps it clear of NYC Local Law 144 and EU AI Act high-risk automated-employment-decision scope.
- Do not add Elasticsearch or Kubernetes until the README's explicit trigger conditions are met.

---

## Ingestion Pipeline Shape

1. FastAPI webhook endpoint (`POST /api/v1/webhooks/github`) receives GitHub events, validates HMAC, pushes to Redis queue.
2. Celery/RQ workers:
   - Persist relational data (commit/PR/review rows) to Postgres.
   - Dispatch Haiku categorization job per commit.
   - On PR merge: dispatch Sonnet impact-read job.
   - Nightly cron: dispatch Batches API job for team/project summaries.
3. Worker writes results back into `ai_*` columns.

---

## API Conventions

- All endpoints are under `/api/v1/`.
- Every analytics endpoint must call `visible_subjects(viewer, scope)` and apply the returned filter before querying. Never return rows without this.
- Return 403 (not 404) when a resource exists but the viewer lacks visibility — 404 would leak existence.
- Key endpoints:
  - `GET /api/v1/me/digest` — authenticated engineer's own digest
  - `GET /api/v1/engineers/{user_id}/profile` — scoped per visibility predicate
  - `GET /api/v1/teams/{team_id}/summary` — manager-scoped team data
  - `GET /api/v1/analytics/org` — director/admin only
  - `POST /api/v1/webhooks/github` — async ingestion

---

## Prototype Build (current target — 1 week)

The first build is a **value-thesis prototype**, not the production pipeline. It deliberately inverts the architecture: prove narrative + per-engineer profile + RBAC visibility on controlled data, defer the real-time plumbing.

**Scope decisions (locked):**
- **Synthetic seed data** — no GitHub App/webhooks/PAT for the prototype. A `seed.py` generates the org graph and a corpus of ~40 realistic PR templates (title + description + representative diff hunk, spanning all 6 categories and the full scope range). Generate the corpus once via Claude, then sample/vary it across engineers and time windows.
- **The AI enrichment runs for real** on that synthetic-but-realistic content — Haiku categorizes real messages, Sonnet impact-reads real diffs. This is the part that must be authentic; do not stub it.
- **Two Next.js screens** — Manager Dashboard + Engineer Digest.

**Prototype-only substitutions (revert to README architecture for production):**
- `seed.py` replaces webhook ingestion. → Production: GitHub App + webhooks (§Ingestion Pipeline).
- **Direct async enrichment loop** (`asyncio.gather`, concurrency cap) replaces Batches + Celery. At synthetic scale Batches' latency hurts iteration; the `messages.parse()` structured-output call shape is identical, so swapping to Batches later is a ~10-line change. → Production: Batches API via Celery workers.
- No Redis, no Celery, no Postgres FTS in the prototype.

**Seed deliberately includes the edge cases** (only synthetic data guarantees they appear in the demo): a couple of unmapped logins (`dependabot[bot]`, one contractor) to exercise the **unattributed bucket**, and one person who is `manager` on one team and `engineer` on another to exercise **scoped roles**.

**Known gap:** the prototype does NOT prove GitHub ingestion (pagination, real identity resolution, webhook HMAC). That is the first post-prototype work.

**Do NOT shortcut these even in the prototype:** real schema with `org_id` + RLS on; `visible_subjects()` as a real function; identity mapping + unattributed bucket; AI tiering with structured outputs.

**5-axis profile is deterministic SQL over `ai_*` columns — no AI in the metric itself** (keeps it auditable and contestable). Each axis is shown as a trend across windows, never summed:
```
scope_weight: trivial=1 small=2 moderate=4 substantial=6 major=8
risk_weight:  low=1 medium=1.5 high=2
Delivery       = Σ scope_weight over merged PRs
Impact/Complex = Σ (scope_weight × risk_weight) over authored merged PRs
Collaboration  = reviews_given + turnaround signal
Quality        = share of merged PRs with ai_has_tests (− revert rate)
Breadth        = distinct count over ai_surfaces[]
```

**Day plan:** (1) schema + RLS + org-GUC session helper; (2) `seed.py` + corpus; (3) `enrich.py` direct loop; (4) `visible_subjects()` + 5-axis rollup + weekly summaries + 3 FastAPI endpoints; (5) two Next.js screens + polish. Day 3 is the load-bearing day.

---

## Development Phases (reference)

- **Phase 1 (MVP):** GitHub App + webhook ingestion, RBAC/org model, Haiku categorization + Sonnet PR reads, Manager Dashboard + engineer digest.
- **Phase 2:** Batches-based nightly summaries, Executive Dashboard, prompt caching.
- **Phase 3:** GitLab/Bitbucket, Jira/Linear, Project Intelligence. Elasticsearch only if Postgres search latency actually hurts.
- **Phase 4:** SSO/SAML, Kubernetes, agent-based reporting, SOC2.
