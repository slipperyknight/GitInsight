"use client";

// Dependency-free 5-axis trend. Each axis is a row of bars (one per weekly window) so the
// PRIMARY view is self-comparison over time — never a single composite score, never a
// cross-person ranking (CLAUDE.md: profile, not score).

import { AXES, type WindowAxes } from "@/lib/types";

function Sparkbars({
  values,
  color,
  compact,
}: {
  values: number[];
  color: string;
  compact?: boolean;
}) {
  const max = Math.max(...values, 1e-9);
  return (
    <div
      className={`flex items-end gap-[3px] ${compact ? "h-8" : "h-16"}`}
      role="img"
      aria-label="trend across windows"
    >
      {values.map((v, i) => {
        const pct = Math.max(2, (v / max) * 100);
        const latest = i === values.length - 1;
        return (
          <div
            key={i}
            className="flex-1 rounded-sm transition-all"
            style={{
              height: `${pct}%`,
              backgroundColor: color,
              opacity: latest ? 1 : 0.35,
            }}
            title={`${values[i]}`}
          />
        );
      })}
    </div>
  );
}

export function AxisTrend({
  trend,
  compact = false,
}: {
  trend: WindowAxes[];
  compact?: boolean;
}) {
  if (!trend.length) return null;
  return (
    <div className={compact ? "grid grid-cols-5 gap-3" : "flex flex-col gap-5"}>
      {AXES.map((axis) => {
        const values = trend.map((w) => Number(w.axes[axis.key] ?? 0));
        const latest = values[values.length - 1] ?? 0;
        return (
          <div
            key={axis.key}
            className={
              compact
                ? "flex flex-col gap-1"
                : "flex items-center gap-4 border-b border-black/5 dark:border-white/10 pb-4 last:border-0"
            }
          >
            <div className={compact ? "" : "w-48 shrink-0"}>
              <div className="flex items-baseline gap-2">
                <span className="font-medium text-sm">{axis.label}</span>
                <span
                  className="text-base font-semibold tabular-nums"
                  style={{ color: axis.color }}
                >
                  {axis.format(latest)}
                </span>
              </div>
              {!compact && (
                <p className="text-xs text-black/45 dark:text-white/40">{axis.blurb}</p>
              )}
            </div>
            <div className={compact ? "" : "flex-1"}>
              <Sparkbars values={values} color={axis.color} compact={compact} />
            </div>
          </div>
        );
      })}
    </div>
  );
}
