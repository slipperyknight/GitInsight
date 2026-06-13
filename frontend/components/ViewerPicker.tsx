"use client";

import { describeRoles, useViewer } from "@/lib/viewer";

// "Acting as" selector — choosing an identity sets the X-User-Id dev-auth header for every
// request, which is how the RBAC visibility boundary is demoed live.
export function ViewerPicker() {
  const { identities, viewer, setViewerId, loading } = useViewer();

  if (loading) return <span className="text-sm text-black/40">loading identities…</span>;

  return (
    <label className="flex items-center gap-2 text-sm">
      <span className="text-black/50 dark:text-white/50">Acting as</span>
      <select
        className="rounded-md border border-black/15 dark:border-white/20 bg-transparent px-2 py-1 text-sm"
        value={viewer?.id ?? ""}
        onChange={(e) => setViewerId(e.target.value)}
      >
        {identities.map((i) => (
          <option key={i.id} value={i.id}>
            {i.name} ({i.org_name}) — {describeRoles(i.roles)}
          </option>
        ))}
      </select>
    </label>
  );
}
