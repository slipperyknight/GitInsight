# Engineer Activity Intelligence Platform

A B2B SaaS platform designed to automatically track and document daily, weekly, and monthly work performed by software engineers across multiple repositories and projects.

---

## 1. Product Requirements Document (PRD)

### Executive Summary
The Engineer Activity Intelligence Platform provides engineering managers, directors, and executives with unprecedented visibility into the actual work performed by their engineering teams. By aggregating signals from VCS, CI/CD, and ticketing systems, the platform uses AI to translate technical activity into business-readable insights and automated documentation.

### Core Problem
Engineering managers struggle to understand actual work completed because commits, pull requests, code reviews, deployments, and Jira tasks are scattered across multiple systems. The platform converts technical activity into business-readable reports and insights.

### Key Features
1. **GitHub/GitLab/Bitbucket Integration:** Track commits, pull requests, branches, merges, reviews, and deployments.
2. **Engineer Activity Tracking:** Daily activity timeline, commits per project, PRs opened/reviewed/merged.
3. **AI-Powered Work Analysis:** Analyze commit messages and code changes, classifying work into Feature Development, Bug Fixes, Refactoring, Infrastructure, Security, and Documentation.
4. **Automated Documentation:** Daily reports, weekly engineering summaries, monthly project reports, release notes.
5. **Project Intelligence:** Map engineer activity to projects, calculate contribution percentages.
6. **Executive Dashboard:** Engineering velocity, delivery metrics, project health, team workload distribution.
7. **Manager Dashboard:** Team contributions, open PRs, blocked work, review bottlenecks.
8. **AI Insights:** Impact analysis, productivity trends, technical debt indicators.

### MVP Scope
*   **Integrations:** GitHub Cloud only.
*   **Tracking:** Commits, PRs, and Code Reviews.
*   **AI Engine:** Basic commit message categorization and daily summaries via OpenAI API.
*   **Dashboards:** Single Manager Dashboard showing team activity timeline and basic metrics.
*   **Reporting:** Automated weekly email summaries.

### Enterprise Features (Post-MVP)
*   **Advanced Integrations:** GitLab, Bitbucket (On-Premise), Jira, Linear, Slack, MS Teams.
*   **Security & Compliance:** SOC2 compliance, SSO/SAML integration, Role-Based Access Control (RBAC), on-prem deployment.
*   **Advanced AI:** Custom-trained models for company-specific jargon and technical debt risk scoring.

---

## 2. System Architecture

The platform uses a scalable cloud-native architecture.

*   **Frontend:** Next.js + TypeScript
*   **Backend:** FastAPI
*   **Database:** PostgreSQL
*   **Cache:** Redis
*   **Search:** Elasticsearch
*   **AI:** OpenAI / Claude
*   **Deployment:** Docker + Kubernetes

### Data Flow
1. **Ingestion:** Fast webhook workers receive events from GitHub/GitLab and push them to a Redis Queue.
2. **Processing:** Celery/RQ workers pull events, fetch code diffs, and send them to the AI Engine.
3. **Storage:** Relational data goes to PostgreSQL; processed summaries and searchable metrics go to Elasticsearch.
4. **Presentation:** Next.js frontend queries the FastAPI backend, which aggregates data from PostgreSQL and Elasticsearch.

---

## 3. Database Schema

Core relational data in PostgreSQL:

```sql
-- Organizations & Users
CREATE TABLE organizations (
    id UUID PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    plan VARCHAR(50) DEFAULT 'startup'
);

CREATE TABLE users (
    id UUID PRIMARY KEY,
    org_id UUID REFERENCES organizations(id),
    email VARCHAR(255) UNIQUE NOT NULL,
    role VARCHAR(50) DEFAULT 'engineer',
    vcs_identities JSONB
);

-- Repositories & Projects
CREATE TABLE repositories (
    id UUID PRIMARY KEY,
    vcs_provider VARCHAR(50),
    external_id VARCHAR(255),
    name VARCHAR(255)
);

CREATE TABLE projects (
    id UUID PRIMARY KEY,
    name VARCHAR(255),
    status VARCHAR(50)
);

-- Activity Tracking
CREATE TABLE commits (
    id UUID PRIMARY KEY,
    repo_id UUID REFERENCES repositories(id),
    user_id UUID REFERENCES users(id),
    sha VARCHAR(40) UNIQUE NOT NULL,
    message TEXT,
    ai_category VARCHAR(50),
    ai_summary TEXT
);

CREATE TABLE pull_requests (
    id UUID PRIMARY KEY,
    repo_id UUID REFERENCES repositories(id),
    author_id UUID REFERENCES users(id),
    state VARCHAR(50)
);
```

---

## 4. API Design

RESTful endpoints in FastAPI:

*   **`GET /api/v1/analytics/executive`**: Returns org-wide metrics (velocity, work allocation).
*   **`GET /api/v1/analytics/team/{team_id}`**: Metrics tailored for a specific manager's team.
*   **`GET /api/v1/engineers/{user_id}/activity`**: Retrieves the daily activity timeline (commits, PRs, reviews).
*   **`GET /api/v1/projects/{project_id}/intelligence`**: AI-categorized commits and estimated hours per project.
*   **`POST /api/v1/webhooks/github`**: Ingests GitHub events asynchronously.

---

## 5. User Flows & Dashboard Wireframes

### User Flows
**Flow A: Manager checks Daily Team Status**
1. Logs into the platform and lands on "Manager Dashboard".
2. Sees actionable alerts ("2 PRs blocked > 48h").
3. Reads the AI Team Summary of yesterday's work.
4. Scrolls through the Daily Activity Timeline for granular commit logs.

**Flow B: Executive reviews Monthly Productivity**
1. Logs in and views the "Executive Dashboard".
2. Analyzes the Work Allocation pie chart (Feature vs. Bugfix vs. Tech Debt).
3. Reviews the Project Intelligence table to see where engineering hours are spent.

### Wireframes

**Manager Dashboard:**
```text
================================================================================
[Logo] GitInsight | Dashboard | Team | Projects | Reports         [Profile]
================================================================================
Good morning, Sarah (Engineering Manager)

[Alert: 2 PRs Blocked]  [Alert: High Code Churn in Auth Module]

--- TEAM VELOCITY (Last 7 Days) ------------------------------------------------
Commits: 142 (+12%) | PRs Merged: 34 | Avg Review Time: 4.2 hrs
--------------------------------------------------------------------------------

--- AI TEAM SUMMARY ------------------------------------------------------------
"The team focused heavily on the Billing API this week. 45% of work was 
classified as Feature Development, primarily driven by Alex and Jordan."
--------------------------------------------------------------------------------

--- DAILY ACTIVITY TIMELINE ----------------------------------------------------
[Today]
* 10:30 AM - Alex merged PR #102: "Implement Stripe Webhooks" [Feature]
* 09:15 AM - Jordan reviewed PR #101.
* 09:00 AM - Sam pushed 3 commits to `fix-login-bug` [Bugfix]
================================================================================
```

**Executive Dashboard:**
```text
================================================================================
[Logo] GitInsight | Executive Overview | Projects | Org Matrix    [Profile]
================================================================================

--- ORGANIZATION HEALTH --------------------------------------------------------
Active Engineers: 45 | Work Streams: 8 | Delivery Risk: LOW
--------------------------------------------------------------------------------

--- WORK ALLOCATION (AI Classified) --------------------------------------------
[===== Feature: 55% =====][=== Bugfix: 25% ===][= Refactor: 15% =][ Ops: 5% ]
--------------------------------------------------------------------------------

--- PROJECT INTELLIGENCE -------------------------------------------------------
Project Name        | Eng. Hours (Est) | Health Status
--------------------------------------------------------------------------------
Project Phoenix     | 320 hrs          | [Green] On Track
Legacy Migration    | 150 hrs          | [Yellow] Needs Attention
Mobile App v2.0     | 280 hrs          | [Red] Blocked
================================================================================
```

---

## 6. Development Roadmap & Monetization Strategy

### Development Roadmap
*   **Phase 1 (Months 1-2): MVP & Core Tracking**
    *   GitHub Webhook integration, Data Pipeline, Basic OpenAI Classification. Next.js Manager Dashboard.
*   **Phase 2 (Months 3-4): AI Intelligence & Reporting**
    *   Automated daily/weekly summaries, Work Allocation analytics, Executive Dashboard.
*   **Phase 3 (Months 5-6): Integrations & Project Mapping**
    *   GitLab/Bitbucket support, Jira/Linear integrations, Project Intelligence mapping.
*   **Phase 4 (Months 7+): Enterprise Scale**
    *   SSO/SAML, Custom AI models, API access, On-prem deployments.

### Monetization Strategy (B2B SaaS)
*   **Tier 1: Startup ($15 / tracked engineer / month)**
    *   GitHub integration, Manager dashboards, standard AI summaries, 30-day retention.
*   **Tier 2: Growth ($35 / tracked engineer / month)**
    *   Jira integration, Executive dashboards, Project Intelligence, 1-year retention.
*   **Tier 3: Enterprise (Custom / ~$65+ / engineer / month)**
    *   GitLab/Bitbucket on-prem support, SSO/SAML, SOC2 reports, dedicated CSM, custom AI vocabulary.
