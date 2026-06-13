"use client";

import Link from "next/link";
import { describeRoles, useViewer } from "@/lib/viewer";

export default function Home() {
  const { viewer, error } = useViewer();

  return (
    <div className="flex flex-col gap-8">
      <section>
        <h1 className="text-2xl font-semibold tracking-tight">GitInsight</h1>
        <p className="mt-1 max-w-2xl text-black/60 dark:text-white/60">
          Narrative + per-engineer insight from GitHub activity. Pick who you&apos;re acting
          as (top right) to see how the RBAC visibility boundary changes what you can see —
          the same screens reveal different data per viewer.
        </p>
      </section>

      {error && (
        <p className="rounded-md bg-red-100 px-3 py-2 text-sm text-red-800">
          Couldn&apos;t reach the API ({error}). Is the backend running on :8000?
        </p>
      )}

      {viewer && (
        <p className="text-sm text-black/60 dark:text-white/60">
          You are <span className="font-medium text-foreground">{viewer.name}</span> @{" "}
          {viewer.org_name} — <span className="italic">{describeRoles(viewer.roles)}</span>.
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Card
          href="/digest"
          title="My Digest"
          body="Your own 5-axis profile as a trend over time, recent PR receipts, and an automated weekly summary. Always visible to you."
        />
        <Card
          href="/dashboard"
          title="Manager Dashboard"
          body="Per-person breakdown for teams you directly manage; aggregate-only for the rest. Try switching viewers to watch 403s and aggregate views appear."
        />
      </div>

      <section className="rounded-lg border border-black/10 dark:border-white/15 p-4 text-sm text-black/55 dark:text-white/55">
        <p className="font-medium text-foreground">How visibility works</p>
        <ul className="mt-2 list-disc pl-5 space-y-1">
          <li>You always see yourself in full.</li>
          <li>A manager sees individuals on teams they directly manage (not sub-teams).</li>
          <li>Everyone else is aggregate-only — no leaderboards, no composite score.</li>
          <li>Cross-org access is blocked at the database (row-level security).</li>
        </ul>
      </section>
    </div>
  );
}

function Card({ href, title, body }: { href: string; title: string; body: string }) {
  return (
    <Link
      href={href}
      className="group rounded-xl border border-black/10 dark:border-white/15 p-5 transition-colors hover:border-blue-500/60 hover:bg-blue-500/[0.03]"
    >
      <h2 className="font-medium group-hover:text-blue-600">{title} →</h2>
      <p className="mt-1 text-sm text-black/60 dark:text-white/60">{body}</p>
    </Link>
  );
}
