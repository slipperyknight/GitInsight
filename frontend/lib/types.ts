// Types mirroring the FastAPI Phase 4 read API (backend/api/v1/endpoints.py).

export interface Axes {
  delivery: number;
  impact: number;
  collaboration: number;
  quality: number; // 0..1 (share of merged PRs with tests, minus revert rate)
  breadth: number; // distinct subsystems
  merged_prs: number;
  reviews_given: number;
}

export interface WindowAxes {
  label: string; // ISO date of the window start
  start: string;
  end: string;
  axes: Axes;
}

export interface Receipt {
  number: number;
  title: string;
  category: string;
  scope: string;
  risk: string;
  surfaces: string[] | null;
  has_tests: boolean;
  impact_summary: string;
  merged_at: string | null;
}

export interface Digest {
  viewer: { id: string; name: string | null };
  scope: string;
  axes_trend: WindowAxes[];
  weekly_summary: string;
  recent_receipts: Receipt[];
}

export interface PersonTrend {
  id: string;
  name: string | null;
  axes_trend: WindowAxes[];
}

export interface TeamSummary {
  team: { id: string; name: string };
  view: "per_person" | "aggregate";
  members_count: number;
  team_axes_trend: WindowAxes[];
  per_person: PersonTrend[];
  weekly_summary: string;
}

export interface Role {
  role: string;
  scope_type: string;
  team: string | null;
}

export interface Identity {
  id: string;
  name: string | null;
  email: string;
  org_name: string;
  roles: Role[];
}

export interface TeamRef {
  id: string;
  name: string;
  org_name: string;
}

// The 5-axis profile definition — labels + descriptions surfaced in the UI.
// Order and meaning track CLAUDE.md exactly. Never summed into one score.
export const AXES: {
  key: keyof Pick<
    Axes,
    "delivery" | "impact" | "collaboration" | "quality" | "breadth"
  >;
  label: string;
  blurb: string;
  color: string;
  format: (v: number) => string;
}[] = [
  {
    key: "delivery",
    label: "Delivery",
    blurb: "Σ scope weight over merged PRs",
    color: "#2563eb",
    format: (v) => v.toFixed(1),
  },
  {
    key: "impact",
    label: "Impact / Complexity",
    blurb: "Σ (scope × risk) over authored merged PRs",
    color: "#7c3aed",
    format: (v) => v.toFixed(1),
  },
  {
    key: "collaboration",
    label: "Collaboration",
    blurb: "reviews given + turnaround signal",
    color: "#0d9488",
    format: (v) => v.toFixed(1),
  },
  {
    key: "quality",
    label: "Quality",
    blurb: "share of merged PRs with tests (− reverts)",
    color: "#16a34a",
    format: (v) => `${Math.round(v * 100)}%`,
  },
  {
    key: "breadth",
    label: "Breadth / Focus",
    blurb: "distinct subsystems touched",
    color: "#ea580c",
    format: (v) => String(v),
  },
];
