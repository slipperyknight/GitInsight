# GitInsight Prototype — Progress

Single source of truth for "where are we." Updated at the **end of every phase**.
Build plan: value-thesis prototype per `CLAUDE.md` Day Plan. Full plan archived in the
approved plan file.

**Current state:** Phases 0–1 complete & verified. **Phase 4 complete & verified end-to-end**
against live data using an **offline enrichment fixture** (no API key yet). The real AI
enrichment (`enrich.py`, real Haiku/Sonnet) is still pending an `ANTHROPIC_API_KEY` — the
prototype currently runs on heuristic `ai_*` values so Phase 4 could be built/verified offline.
**Next action:** the prototype is feature-complete (Phases 0–5). Remaining: when a key is
available, set `ANTHROPIC_API_KEY` and run
`uv run python -m corpus.generate_corpus` → `uv run python seed.py` → `uv run python enrich.py`
to replace the heuristic `ai_*` values with real Haiku/Sonnet output (no code change in
Phase 4/5). After that, the first post-prototype work is real GitHub ingestion (README §1).

**Run the full stack:** start Postgres (host-network docker note below) →
`cd backend && uv run uvicorn main:app --port 8000` → `cd frontend && npm run dev`.
The frontend proxies `/api/v1/*` to `:8000` (configurable via `BACKEND_ORIGIN`). Open
http://localhost:3000 and use the "Acting as" picker to switch viewers.

> ⚠️ **Real-AI still blocked:** `ANTHROPIC_API_KEY` is **not set**. Phase 4 was verified with
> `dev/offline_enrich.py` (deterministic heuristic — **not** the product). Run the real chain
> above once a key exists; `enrich.py` re-reads the rows and overwrites the placeholder values.

> 🐳 **Docker note (this host):** the default compose bridge network fails here
> (`veth … operation not supported`). Workaround: run Postgres with host networking —
> `docker run -d --name gitinsight-db --network host -e POSTGRES_USER=gitinsight
> -e POSTGRES_PASSWORD=gitinsight -e POSTGRES_DB=gitinsight -v gitinsight_pgdata:/var/lib/postgresql/data postgres:16`.
> Binds host :5432 directly; the app's localhost URLs work unchanged.

---

## Phase checklist

- [x] **Phase 0 — Scaffold & progress file**
- [x] **Phase 1 — Schema + RLS + org-GUC session helper** (CLAUDE.md Day 1)
- [x] **Phase 2 — `seed.py` + PR corpus** (Day 2) — seeded live; corpus is an offline fixture
      (`corpus/pr_templates.json`, hand-authored) pending real Opus generation when key exists
- [~] **Phase 3 — `enrich.py` direct AI loop** (Day 3) — code complete; **real run blocked on
      API key.** `ai_*` columns populated via `dev/offline_enrich.py` (heuristic) for now
- [x] **Phase 4 — `visible_subjects()` + 5-axis rollup + summaries + API** (Day 4) — verified
- [x] **Phase 5 — Two Next.js screens + polish** (Day 5) — verified (build + RBAC demo flows)

---

## How to run

```bash
# Postgres
docker compose up -d

# Backend (uv); uv is installed at ~/.local/bin/uv
cd backend && uv run uvicorn main:app --reload      # (once main.py exists, Phase 4)

# Frontend
cd frontend && npm run dev
```

DB connection (matches `docker-compose.yml`):
`postgresql://gitinsight:gitinsight@localhost:5432/gitinsight`

---

## Notes & decisions log

### 2026-06-12 — Phase 0
- **Tooling decided:** Python via **uv** (single `pyproject.toml`); installed to
  `~/.local/bin/uv` (was not preinstalled). Repo layout `backend/` + `frontend/`.
- **Backend** initialized with: fastapi, uvicorn[standard], asyncpg, pydantic, anthropic
  (0.109.1), python-dotenv. Imports verified.
- **Frontend** scaffolded via `create-next-app` (TypeScript, Tailwind, ESLint, App Router,
  Turbopack, `@/*` alias).
- **Postgres** runs via `docker-compose.yml` (postgres:16, single service — no Redis/Celery
  per prototype scope). Verified reachable (`pg_isready` + `select version()` → PG 16.14).
- **`.env.example`** created with `DATABASE_URL` + `ANTHROPIC_API_KEY`. `.gitignore` already
  ignores `.env`, `.venv`, `node_modules`.
- **Flagged:** `ANTHROPIC_API_KEY` not set in env — see blocker above. Does not block
  Phases 1–2 (schema/seed), but Phase 2's corpus generation and Phase 3 enrichment need it.

### 2026-06-12 — Phase 1
- **`migrations/0001_init.sql`** applied: 10 tables (README §4 verbatim + a `reviews` table
  for the Collaboration axis). Indexes on `org_id` + every `*_at`. RLS ENABLED + FORCED on
  all 10 org-bearing tables.
- **Two-role design:** superuser `gitinsight` (bypasses RLS → migrate/seed/enrich) vs
  non-superuser `app_user` (RLS enforced → FastAPI). This is why RLS isn't silently
  bypassed. `app_user` created in the migration with table grants + default privileges.
- **org-GUC helper** (`db/session.py`): `org_session(org_id)` sets `app.org_id` via
  `set_config(..., is_local=true)` inside a transaction → no cross-request leak. Plus
  `admin_session()` for batch writers.
- **Policy gotcha fixed:** after a transaction-local SET, an unset GUC reads back as `''`
  (not NULL), and `''::uuid` throws. Policies use `NULLIF(current_setting(...), '')::uuid`
  so an unset session cleanly returns 0 rows. (Applied to live DB + migration file.)
- **Verified:** `uv run python -m db.test_isolation` → Org A sees only A, Org B only B,
  no-GUC session sees 0 rows. ✅
- **New env var:** `APP_DATABASE_URL` (app_user) added to `.env.example`. Code defaults to
  local URLs so no `.env` is required for the prototype.

### 2026-06-12 — Phase 2–3 (code written, run blocked)
- **AI surface verified:** anthropic 0.109.1 supports `messages.parse(output_format=Model)`;
  result on `.parsed_output`. Modern structured-output API — used in `ai/client.py`.
- **`ai/schemas.py`:** `CommitCategory` + `PRImpact` (Literal-enum fields mirroring the
  CLAUDE.md impact schema). **`ai/client.py`:** model constants (HAIKU/SONNET/OPUS),
  `parse_structured()`, `text_completion()`; raises a clear error if the key is missing.
- **`corpus/generate_corpus.py`:** one-time Opus generator, ~7 PRs/category across the scope
  range → `corpus/pr_templates.json`. category/scope are *hints* for balanced sampling only,
  never fed to enrichment.
- **`seed.py`:** builds Acme (Platform→Billing/Auth) + Globex; edge cases included —
  **Jordan Lee = manager(Auth) + engineer(Billing)**, and **unattributed** dependabot PR +
  contractor commit (NULL author/user). Leaves `ai_*` NULL. Deterministic (seed=42).
- **`enrich.py`:** semaphore-capped `asyncio.gather`; Haiku per commit, Sonnet per merged PR;
  writes all 6 `ai_*` PR columns + commit `ai_category`/`ai_summary`.
- **All modules `py_compile` + import clean.** Pydantic schemas emit JSON-schema keys
  matching the `ai_*` columns 1:1.
- **▶ To unblock:** `export ANTHROPIC_API_KEY=...` (or add to `.env`), then run the chain in
  "Next action" above.

### 2026-06-13 — Phase 4 (visible_subjects + 5-axis rollup + summaries + API) ✅
- **Offline data path (no key):** hand-authored `corpus/pr_templates.json` (18 templates, all
  6 categories × scope range) so `seed.py` runs offline; `dev/offline_enrich.py` populates the
  `ai_*` columns via a deterministic heuristic (clearly labelled — **not** the product AI).
  Real `enrich.py` overwrites these once a key exists. Live DB: 2 orgs, 33 PRs, 71 commits.
- **`rbac/visibility.py`** — single `visible_subjects(conn, viewer, scope)` policy fn. Authority
  read from `role_assignments` only (no `manager_id`, not `users.role`). Individual visibility =
  self ∪ direct-managed-team members (no subtree). Returns `(individual_user_ids,
  aggregate_team_ids)` + context (`managed_team_ids`, `can_view_org`, `denied_individual`).
- **`analytics/rollup.py`** — deterministic 5-axis SQL, exact CLAUDE.md weights, returned as a
  per-window **trend** (8 weekly windows), never a composite. Unattributed excluded from
  individual axes, opt-in for aggregates.
- **`analytics/summaries.py`** — Sonnet `text_completion` (real path) with a labelled
  deterministic fallback when no key, so endpoints stay functional offline.
- **`api/v1/endpoints.py` + `main.py`** — 4 routes: `/me/digest`, `/engineers/{id}/profile`,
  `/teams/{id}/summary`, `/analytics/org`. Dev-auth via `X-User-Id` header. All data access
  through RLS-enforced `org_session()`. 403-not-404 for exists-but-not-visible.
- **Verified (20/20 cases):** auth (401), self (rule 2), manager→member (rule 3), non-manager
  →403 (rule 4), **Jordan dual-role** (sees Auth, 403 on Billing), org_admin constrained out of
  individuals but allowed org/team aggregate, **cross-org→404 via RLS**, director gate on
  `/analytics/org`. Payloads confirmed: 5 separate axes, no composite, receipts, per_person vs
  aggregate shapes, unattributed in org aggregate. Server ran clean (no errors in log).
- **Run the API:** `cd backend && uv run uvicorn main:app --reload` (Postgres must be up).

### 2026-06-13 — Phase 5 (two Next.js screens) ✅
- **Same-origin proxy:** `next.config.ts` rewrites `/api/v1/*` → FastAPI (`BACKEND_ORIGIN`,
  default `:8000`). No CORS; `X-User-Id` dev-auth header flows through.
- **Dev-auth directory:** added `GET /api/v1/dev/identities` + `/api/v1/dev/teams` (admin pool,
  clearly dev-only) so the "Acting as" viewer picker survives reseeds instead of hardcoding UUIDs.
- **Frontend:** `lib/` (types, api client, viewer context w/ localStorage), `components/`
  (dependency-free `AxisTrend` sparkbars, `Receipts`, `SummaryPanel`, `Nav`, `ViewerPicker`),
  pages `/` (picker + explainer), `/digest` (My Digest → `/me/digest`), `/dashboard`
  (Manager Dashboard → `/teams/{id}/summary`, handles per_person / aggregate / 403 / 404).
- **Framing:** 5 axes shown separately as trends (never summed), per-person ordered by name
  (not ranked), summary panel flags the non-AI placeholder when no key is set.
- **Verified:** `tsc --noEmit` clean, `eslint` clean (fixed React 19 `set-state-in-effect`),
  `next build` ✓ (all routes). Runtime through the Next proxy: digest loads (8 windows, 5
  receipts); dashboard RBAC states confirmed — sarah→Billing `per_person` 200, alex→Billing
  403, riya→Billing `aggregate` 200, sarah→Globex Core 404 (cross-org RLS).
