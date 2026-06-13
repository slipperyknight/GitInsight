"use client";

// Narrative summary panel — the hero feature (narrative-and-automation led). The backend
// returns a Sonnet-written summary when an API key is present, or a clearly-labelled
// deterministic placeholder otherwise; we surface that distinction honestly.

export function SummaryPanel({ summary }: { summary: string }) {
  const placeholder = summary.startsWith("[auto/non-AI placeholder]");
  return (
    <div className="rounded-lg border border-black/10 dark:border-white/15 bg-black/[0.02] dark:bg-white/[0.03] p-4">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold">Weekly summary</h3>
        {placeholder && (
          <span className="rounded bg-amber-100 px-1.5 py-0.5 text-[11px] font-medium text-amber-800 dark:bg-amber-900/40 dark:text-amber-200">
            placeholder · set ANTHROPIC_API_KEY
          </span>
        )}
      </div>
      <p className="mt-2 text-sm leading-relaxed text-black/70 dark:text-white/70">
        {placeholder ? summary.replace("[auto/non-AI placeholder] ", "") : summary}
      </p>
    </div>
  );
}
