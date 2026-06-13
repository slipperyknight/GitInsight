"use client";

import { useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Digest } from "@/lib/types";
import { useViewer } from "@/lib/viewer";
import { AxisTrend } from "@/components/AxisTrend";
import { Receipts } from "@/components/Receipts";
import { SummaryPanel } from "@/components/SummaryPanel";

export default function DigestPage() {
  const { viewer } = useViewer();
  const [data, setData] = useState<Digest | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!viewer) return;
    let active = true;
    const load = async () => {
      setLoading(true);
      setErr(null);
      try {
        const d = await api.digest(viewer.id);
        if (active) setData(d);
      } catch (e: unknown) {
        if (active)
          setErr(e instanceof ApiError ? `${e.status}: ${e.message}` : String(e));
      } finally {
        if (active) setLoading(false);
      }
    };
    load();
    return () => {
      active = false;
    };
  }, [viewer]);

  if (!viewer) return <Prompt />;

  return (
    <div className="animate-fade-up flex flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold tracking-tight">
          {data?.viewer.name ?? viewer.name}&apos;s digest
        </h1>
        <p className="text-sm text-black/55 dark:text-white/55">
          Your 5-axis profile across the last 8 weeks — a self-comparison trend, not a score.
        </p>
      </div>

      {loading && <p className="text-sm text-black/45">Loading…</p>}
      {err && <p className="rounded-md bg-red-100 px-3 py-2 text-sm text-red-800">{err}</p>}

      {data && (
        <>
          <section className="rounded-xl border border-black/10 dark:border-white/15 p-5">
            <AxisTrend trend={data.axes_trend} />
          </section>
          <SummaryPanel summary={data.weekly_summary} />
          <section>
            <h2 className="mb-3 text-sm font-semibold">Recent PR receipts</h2>
            <Receipts receipts={data.recent_receipts} />
          </section>
        </>
      )}
    </div>
  );
}

function Prompt() {
  return (
    <p className="text-sm text-black/55">Pick an identity (top right) to load your digest.</p>
  );
}
