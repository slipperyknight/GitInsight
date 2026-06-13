"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { TeamRef, TeamSummary } from "@/lib/types";
import { useViewer } from "@/lib/viewer";
import { AxisTrend } from "@/components/AxisTrend";
import { SummaryPanel } from "@/components/SummaryPanel";

export default function DashboardPage() {
  const { viewer } = useViewer();
  const [teams, setTeams] = useState<TeamRef[]>([]);
  const [teamId, setTeamId] = useState<string>("");
  const [data, setData] = useState<TeamSummary | null>(null);
  const [err, setErr] = useState<{ status: number; msg: string } | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.teams().then(setTeams).catch(() => setTeams([]));
  }, []);

  useEffect(() => {
    let active = true;
    const load = async () => {
      if (!viewer || !teamId) {
        setData(null);
        setErr(null);
        return;
      }
      setLoading(true);
      setErr(null);
      setData(null);
      try {
        const d = await api.teamSummary(teamId, viewer.id);
        if (active) setData(d);
      } catch (e: unknown) {
        if (!active) return;
        if (e instanceof ApiError) setErr({ status: e.status, msg: e.message });
        else setErr({ status: 0, msg: String(e) });
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    return () => {
      active = false;
    };
  }, [viewer, teamId]);

  if (!viewer)
    return <p className="text-sm text-black/55">Pick an identity (top right) first.</p>;

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">Manager Dashboard</h1>
        <p className="text-sm text-black/55 dark:text-white/55">
          Per-person breakdown for teams you directly manage; aggregate-only otherwise.
        </p>
      </div>

      <label className="flex items-center gap-2 text-sm">
        <span className="text-black/50 dark:text-white/50">Team</span>
        <select
          className="rounded-md border border-black/15 dark:border-white/20 bg-transparent px-2 py-1"
          value={teamId}
          onChange={(e) => setTeamId(e.target.value)}
        >
          <option value="">Select a team…</option>
          {teams.map((t) => (
            <option key={t.id} value={t.id}>
              {t.name} ({t.org_name})
            </option>
          ))}
        </select>
      </label>

      {loading && <p className="text-sm text-black/45">Loading…</p>}

      {err && <AccessNotice status={err.status} msg={err.msg} />}

      {data && (
        <>
          <div className="flex items-center gap-3">
            <h2 className="text-lg font-medium">{data.team.name}</h2>
            <Badge view={data.view} />
            <span className="text-sm text-black/45">{data.members_count} members</span>
          </div>

          <section className="rounded-xl border border-black/10 dark:border-white/15 p-5">
            <h3 className="mb-4 text-sm font-semibold">Team trend (aggregate)</h3>
            <AxisTrend trend={data.team_axes_trend} />
          </section>

          <SummaryPanel summary={data.weekly_summary} />

          {data.view === "per_person" ? (
            <section>
              <h3 className="mb-1 text-sm font-semibold">Per-person profiles</h3>
              <p className="mb-3 text-xs text-black/45">
                Evidence for human judgement — ordered by name, not ranked.
              </p>
              <div className="grid gap-3 sm:grid-cols-2">
                {data.per_person.map((p) => (
                  <div
                    key={p.id}
                    className="rounded-lg border border-black/10 dark:border-white/15 p-4"
                  >
                    <p className="mb-3 font-medium">{p.name}</p>
                    <AxisTrend trend={p.axes_trend} compact />
                  </div>
                ))}
              </div>
            </section>
          ) : (
            <p className="rounded-md bg-black/[0.03] dark:bg-white/[0.05] px-3 py-2 text-sm text-black/55 dark:text-white/55">
              You don&apos;t directly manage this team, so individual profiles are hidden.
              Aggregate metrics only — this is the visibility boundary working as designed.
            </p>
          )}
        </>
      )}
    </div>
  );
}

function Badge({ view }: { view: "per_person" | "aggregate" }) {
  const isPP = view === "per_person";
  return (
    <span
      className={`rounded px-2 py-0.5 text-xs font-medium ${
        isPP
          ? "bg-blue-100 text-blue-800 dark:bg-blue-900/40 dark:text-blue-200"
          : "bg-black/10 text-black/60 dark:bg-white/10 dark:text-white/60"
      }`}
    >
      {isPP ? "per-person (you manage this team)" : "aggregate only"}
    </span>
  );
}

function AccessNotice({ status, msg }: { status: number; msg: string }) {
  const title =
    status === 403
      ? "403 — Not authorized"
      : status === 404
        ? "404 — Not found"
        : "Error";
  const help =
    status === 403
      ? "This viewer can't see this team. Switch to its manager or an org admin."
      : status === 404
        ? "This team isn't in the current viewer's org — row-level security hides it (it returns 404, not 403, so existence isn't leaked)."
        : msg;
  return (
    <div className="rounded-md border border-amber-300/60 bg-amber-50 dark:bg-amber-900/20 px-3 py-2 text-sm">
      <p className="font-medium text-amber-900 dark:text-amber-200">{title}</p>
      <p className="text-amber-800/80 dark:text-amber-200/70">{help}</p>
    </div>
  );
}
