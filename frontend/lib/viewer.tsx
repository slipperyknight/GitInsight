"use client";

// Viewer context: the prototype's "Acting as" selector. Holds the chosen identity (whose id
// becomes the X-User-Id dev-auth header) and persists it in localStorage so it survives
// navigation between the two screens. Production replaces this with a real session.

import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { api } from "./api";
import type { Identity, Role } from "./types";

const STORAGE_KEY = "gitinsight.viewerId";

interface ViewerCtx {
  identities: Identity[];
  viewer: Identity | null;
  setViewerId: (id: string) => void;
  loading: boolean;
  error: string | null;
}

const Ctx = createContext<ViewerCtx | null>(null);

export function ViewerProvider({ children }: { children: ReactNode }) {
  const [identities, setIdentities] = useState<Identity[]>([]);
  const [viewerId, setViewerIdState] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api
      .identities()
      .then((list) => {
        if (!active) return;
        setIdentities(list);
        const saved =
          typeof window !== "undefined"
            ? window.localStorage.getItem(STORAGE_KEY)
            : null;
        const initial =
          (saved && list.find((i) => i.id === saved)?.id) ?? list[0]?.id ?? null;
        setViewerIdState(initial);
      })
      .catch((e) => active && setError(String(e?.message ?? e)))
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, []);

  const setViewerId = (id: string) => {
    setViewerIdState(id);
    if (typeof window !== "undefined") window.localStorage.setItem(STORAGE_KEY, id);
  };

  const viewer = useMemo(
    () => identities.find((i) => i.id === viewerId) ?? null,
    [identities, viewerId],
  );

  return (
    <Ctx.Provider value={{ identities, viewer, setViewerId, loading, error }}>
      {children}
    </Ctx.Provider>
  );
}

export function useViewer() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error("useViewer must be used within ViewerProvider");
  return ctx;
}

// Human-readable role summary, e.g. "manager · Auth, engineer · Billing".
export function describeRoles(roles: Role[]): string {
  if (!roles.length) return "no roles";
  return roles
    .map((r) => (r.team ? `${r.role} · ${r.team}` : `${r.role} · org`))
    .join(", ");
}
