"use client";

// PR "receipts" — the drill-down evidence behind the profile. ai_impact_summary is the
// receipt sentence (triple-use field per CLAUDE.md). Evidence for a human, not a rating.

import type { Receipt } from "@/lib/types";

const RISK_COLOR: Record<string, string> = {
  low: "bg-green-100 text-green-800 dark:bg-green-900/40 dark:text-green-200",
  medium: "bg-amber-100 text-amber-800 dark:bg-amber-900/40 dark:text-amber-200",
  high: "bg-red-100 text-red-800 dark:bg-red-900/40 dark:text-red-200",
};

function Tag({ children, className = "" }: { children: React.ReactNode; className?: string }) {
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${className}`}>{children}</span>
  );
}

export function Receipts({ receipts }: { receipts: Receipt[] }) {
  if (!receipts.length)
    return <p className="text-sm text-black/45">No merged PRs in range.</p>;
  return (
    <ul className="flex flex-col gap-3">
      {receipts.map((r) => (
        <li
          key={r.number}
          className="rounded-lg border border-black/10 dark:border-white/15 p-3"
        >
          <div className="flex flex-wrap items-center gap-2">
            <Tag className="bg-black/5 dark:bg-white/10">#{r.number}</Tag>
            <Tag className="bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200">
              {r.category}
            </Tag>
            <Tag className="bg-violet-100 text-violet-800 dark:bg-violet-900/40 dark:text-violet-200">
              {r.scope}
            </Tag>
            <Tag className={RISK_COLOR[r.risk] ?? "bg-black/5"}>{r.risk} risk</Tag>
            {r.has_tests && (
              <Tag className="bg-teal-100 text-teal-800 dark:bg-teal-900/40 dark:text-teal-200">
                tests
              </Tag>
            )}
          </div>
          <p className="mt-2 text-sm font-medium">{r.title}</p>
          <p className="text-sm text-black/60 dark:text-white/60">{r.impact_summary}</p>
          {Array.isArray(r.surfaces) && r.surfaces.length > 0 && (
            <p className="mt-1 text-xs text-black/40">surfaces: {r.surfaces.join(", ")}</p>
          )}
        </li>
      ))}
    </ul>
  );
}
