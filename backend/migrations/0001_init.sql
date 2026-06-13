-- GitInsight prototype schema — implements README §4 verbatim, plus:
--   * a `reviews` table (needed by the Collaboration axis; §4's SQL block omits it but
--     CLAUDE.md / README MVP scope tracks "code reviews with timestamps").
--   * RLS on every org-bearing table, FORCE'd so the table owner is also subject to it.
--   * a non-superuser `app_user` role for the read/app path (superusers BYPASS RLS, so the
--     tenant test must run as a non-superuser).
--
-- Tenant isolation: every org-bearing table filters by current_setting('app.org_id').
-- The org-GUC session helper (db/session.py) sets that per request transaction.

-- gen_random_uuid() is core in PG13+.

-- ============================================================================
-- Tenancy & users
-- ============================================================================
CREATE TABLE organizations (
    id   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    plan VARCHAR(50) DEFAULT 'startup'
);

CREATE TABLE users (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id         UUID NOT NULL REFERENCES organizations(id),
    email          VARCHAR(255) UNIQUE NOT NULL,
    name           VARCHAR(255),
    role           VARCHAR(50) DEFAULT 'engineer',  -- display-only; authority is in role_assignments
    vcs_identities JSONB                             -- admin-managed: VCS logins -> this user
);

-- ============================================================================
-- Org hierarchy
-- ============================================================================
CREATE TABLE teams (
    id             UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id         UUID NOT NULL REFERENCES organizations(id),
    parent_team_id UUID REFERENCES teams(id),
    name           VARCHAR(255) NOT NULL
);

CREATE TABLE team_memberships (
    id      UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id  UUID NOT NULL REFERENCES organizations(id),  -- denormalized for RLS
    team_id UUID NOT NULL REFERENCES teams(id),
    user_id UUID NOT NULL REFERENCES users(id),
    UNIQUE (team_id, user_id)
);

-- ============================================================================
-- Scoped roles — the heart of RBAC
-- ============================================================================
CREATE TABLE role_assignments (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id     UUID NOT NULL REFERENCES organizations(id),
    user_id    UUID NOT NULL REFERENCES users(id),
    role       VARCHAR(50) NOT NULL,        -- engineer | manager | director | org_admin
    scope_type VARCHAR(20) NOT NULL,        -- 'org' | 'team'
    scope_id   UUID,                        -- team_id when scope_type='team'; NULL for org-wide
    UNIQUE (user_id, role, scope_type, scope_id)
);

-- ============================================================================
-- Repositories & projects
-- ============================================================================
CREATE TABLE repositories (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       UUID NOT NULL REFERENCES organizations(id),
    vcs_provider VARCHAR(50),
    external_id  VARCHAR(255),
    name         VARCHAR(255)
);

CREATE TABLE projects (
    id     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id UUID NOT NULL REFERENCES organizations(id),
    name   VARCHAR(255),
    status VARCHAR(50)
);

-- ============================================================================
-- Activity (timestamps are load-bearing — almost every feature is a time-window query)
-- ============================================================================
CREATE TABLE commits (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id      UUID NOT NULL REFERENCES organizations(id),
    repo_id     UUID REFERENCES repositories(id),
    user_id     UUID REFERENCES users(id),     -- NULL => unattributed bucket (unmapped/bot)
    sha         VARCHAR(40) UNIQUE NOT NULL,
    message     TEXT,
    authored_at TIMESTAMPTZ,
    ai_category VARCHAR(50),                    -- enum-constrained via structured output
    ai_summary  TEXT
);

CREATE TABLE pull_requests (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id     UUID NOT NULL REFERENCES organizations(id),
    repo_id    UUID REFERENCES repositories(id),
    author_id  UUID REFERENCES users(id),       -- NULL => unattributed bucket
    number     INTEGER,
    title      TEXT,
    description TEXT,
    diff       TEXT,                            -- representative diff hunk (prototype corpus)
    state      VARCHAR(50),
    created_at TIMESTAMPTZ,
    merged_at  TIMESTAMPTZ,
    -- AI impact read (structured output) — see CLAUDE.md schema
    ai_category       VARCHAR(50),
    ai_scope          VARCHAR(20),              -- trivial | small | moderate | substantial | major
    ai_risk           VARCHAR(20),              -- low | medium | high
    ai_surfaces       JSONB,                    -- subsystems touched
    ai_has_tests      BOOLEAN,
    ai_impact_summary TEXT                       -- triple-use: metric input, receipt, summary feed
);

CREATE TABLE reviews (
    id           UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    org_id       UUID NOT NULL REFERENCES organizations(id),
    pr_id        UUID REFERENCES pull_requests(id),
    reviewer_id  UUID REFERENCES users(id),     -- NULL => unattributed
    state        VARCHAR(50),                   -- approved | changes_requested | commented
    submitted_at TIMESTAMPTZ
);

-- ============================================================================
-- Indexes — org_id everywhere + every *_at timestamp
-- ============================================================================
CREATE INDEX idx_users_org              ON users(org_id);
CREATE INDEX idx_teams_org              ON teams(org_id);
CREATE INDEX idx_team_memberships_org   ON team_memberships(org_id);
CREATE INDEX idx_team_memberships_team  ON team_memberships(team_id);
CREATE INDEX idx_team_memberships_user  ON team_memberships(user_id);
CREATE INDEX idx_role_assignments_org   ON role_assignments(org_id);
CREATE INDEX idx_role_assignments_user  ON role_assignments(user_id);
CREATE INDEX idx_role_assignments_scope ON role_assignments(scope_type, scope_id);
CREATE INDEX idx_repositories_org       ON repositories(org_id);
CREATE INDEX idx_projects_org           ON projects(org_id);
CREATE INDEX idx_commits_org            ON commits(org_id);
CREATE INDEX idx_commits_user           ON commits(user_id);
CREATE INDEX idx_commits_authored_at    ON commits(authored_at);
CREATE INDEX idx_pull_requests_org      ON pull_requests(org_id);
CREATE INDEX idx_pull_requests_author   ON pull_requests(author_id);
CREATE INDEX idx_pull_requests_created  ON pull_requests(created_at);
CREATE INDEX idx_pull_requests_merged   ON pull_requests(merged_at);
CREATE INDEX idx_reviews_org            ON reviews(org_id);
CREATE INDEX idx_reviews_reviewer       ON reviews(reviewer_id);
CREATE INDEX idx_reviews_submitted_at   ON reviews(submitted_at);

-- ============================================================================
-- Row-Level Security — tenant backstop
-- ----------------------------------------------------------------------------
-- Policy uses current_setting('app.org_id', true): the `true` makes it return NULL
-- (instead of erroring) when the GUC is unset, so an unset session sees NO rows.
-- FORCE ROW LEVEL SECURITY makes the table OWNER also subject to RLS. (Superusers and
-- BYPASSRLS roles still bypass — that is why app_user below is a plain role.)
-- ============================================================================

-- NOTE: NULLIF(..., '') matters. After a transaction-local SET, an unset GUC reads back as
-- '' (empty string), not NULL — and ''::uuid throws. NULLIF turns '' into NULL so an unset
-- session cleanly matches no rows instead of erroring.

-- organizations: tenant key is its own id
ALTER TABLE organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE organizations FORCE  ROW LEVEL SECURITY;
CREATE POLICY org_isolation ON organizations
    USING (id = NULLIF(current_setting('app.org_id', true), '')::uuid)
    WITH CHECK (id = NULLIF(current_setting('app.org_id', true), '')::uuid);

-- every other table: org_id
DO $$
DECLARE t text;
BEGIN
    FOREACH t IN ARRAY ARRAY[
        'users','teams','team_memberships','role_assignments',
        'repositories','projects','commits','pull_requests','reviews'
    ] LOOP
        EXECUTE format('ALTER TABLE %I ENABLE ROW LEVEL SECURITY;', t);
        EXECUTE format('ALTER TABLE %I FORCE  ROW LEVEL SECURITY;', t);
        EXECUTE format(
            'CREATE POLICY org_isolation ON %I '
            'USING (org_id = NULLIF(current_setting(''app.org_id'', true), '''')::uuid) '
            'WITH CHECK (org_id = NULLIF(current_setting(''app.org_id'', true), '''')::uuid);', t);
    END LOOP;
END $$;

-- ============================================================================
-- app_user — non-superuser role for the FastAPI read/app path (RLS enforced).
-- Trusted batch writers (migrate/seed/enrich) connect as the superuser and bypass RLS.
-- ============================================================================
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'app_user') THEN
        CREATE ROLE app_user LOGIN PASSWORD 'app_pw';
    END IF;
END $$;

GRANT USAGE ON SCHEMA public TO app_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO app_user;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO app_user;
