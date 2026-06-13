"use client";

import Link from "next/link";
import { describeRoles, useViewer } from "@/lib/viewer";

export default function Home() {
  const { viewer, error } = useViewer();

  return (
    <div className="relative flex flex-col gap-10">
      {/* Aurora backdrop — animated, blurred colour blobs behind the hero */}
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div
          className="aurora-blob h-[42vh] w-[42vh] bg-blue-500/40"
          style={{ top: "-8%", left: "8%" }}
        />
        <div
          className="aurora-blob h-[38vh] w-[38vh] bg-violet-500/30"
          style={{ top: "2%", right: "6%", animationDelay: "3s" }}
        />
        <div
          className="aurora-blob h-[34vh] w-[34vh] bg-teal-500/25"
          style={{ top: "30%", left: "38%", animationDelay: "6s" }}
        />
      </div>

      {/* Hero */}
      <section className="animate-fade-up pt-6">
        <span className="inline-flex items-center gap-2 rounded-full border border-black/10 dark:border-white/15 px-3 py-1 text-xs text-black/55 dark:text-white/55">
          <span className="h-1.5 w-1.5 rounded-full bg-blue-600" />
          Narrative-led engineering insight
        </span>
        <h1 className="mt-4 text-4xl font-semibold tracking-tight sm:text-5xl">
          Git
          <span className="bg-gradient-to-r from-blue-600 via-violet-500 to-teal-500 bg-clip-text text-transparent">
            Insight
          </span>
        </h1>
        <p className="mt-3 max-w-2xl text-black/60 dark:text-white/60">
          Per-engineer profiles and automated narrative from GitHub activity. Pick who
          you&apos;re acting as (top right) — the same screens reveal different data per viewer,
          enforced by row-level security and a single visibility policy.
        </p>
      </section>

      {error && (
        <p className="animate-fade-up rounded-md bg-red-100 px-3 py-2 text-sm text-red-800">
          Couldn&apos;t reach the API ({error}). Is the backend running on :8000?
        </p>
      )}

      {viewer && (
        <p
          className="animate-fade-up inline-flex w-fit items-center gap-2 rounded-full bg-black/[0.04] dark:bg-white/[0.06] px-3 py-1.5 text-sm text-black/65 dark:text-white/65"
          style={{ animationDelay: "80ms" }}
        >
          Acting as <span className="font-medium text-foreground">{viewer.name}</span> @{" "}
          {viewer.org_name} · <span className="italic">{describeRoles(viewer.roles)}</span>
        </p>
      )}

      <div className="grid gap-4 sm:grid-cols-2">
        <Card
          href="/digest"
          title="My Digest"
          body="Your own 5-axis profile as a trend over time, recent PR receipts, and an automated weekly summary. Always visible to you."
          delay={120}
        />
        <Card
          href="/dashboard"
          title="Manager Dashboard"
          body="Per-person breakdown for teams you directly manage; aggregate-only for the rest. Switch viewers to watch 403s and aggregate views appear."
          delay={200}
        />
      </div>

      <section
        className="animate-fade-up rounded-xl border border-black/10 dark:border-white/15 p-5 text-sm text-black/55 dark:text-white/55"
        style={{ animationDelay: "280ms" }}
      >
        <p className="font-medium text-foreground">How visibility works</p>
        <ul className="mt-2 list-disc space-y-1 pl-5">
          <li>You always see yourself in full.</li>
          <li>A manager sees individuals on teams they directly manage (not sub-teams).</li>
          <li>Everyone else is aggregate-only — no leaderboards, no composite score.</li>
          <li>Cross-org access is blocked at the database (row-level security).</li>
        </ul>
      </section>
    </div>
  );
}

function Card({
  href,
  title,
  body,
  delay,
}: {
  href: string;
  title: string;
  body: string;
  delay: number;
}) {
  return (
    <Link
      href={href}
      style={{ animationDelay: `${delay}ms` }}
      className="group animate-fade-up rounded-xl border border-black/10 dark:border-white/15 p-5
                 transition-all duration-300 ease-out hover:-translate-y-1
                 hover:border-blue-500/60 hover:bg-blue-500/[0.04]
                 hover:shadow-lg hover:shadow-blue-500/10"
    >
      <h2 className="flex items-center gap-1.5 font-medium group-hover:text-blue-600">
        {title}
        <span className="transition-transform duration-300 group-hover:translate-x-1">→</span>
      </h2>
      <p className="mt-1 text-sm text-black/60 dark:text-white/60">{body}</p>
    </Link>
  );
}
