"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { api, getToken, setToken } from "./api";
import type { Filters, Meta, User } from "./types";

type Ctx = {
  user: User | null;
  meta: Meta | null;
  filters: Filters;
  setFilters: (f: Partial<Filters>) => void;
  can: (perm: string) => boolean;
  logout: () => void;
  loading: boolean;
  error: string | null;
};

const AppCtx = createContext<Ctx | null>(null);

export function AppProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [meta, setMeta] = useState<Meta | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filters, setFiltersState] = useState<Filters>({ start: "", end: "", platforms: [], categories: [], search: "" });

  useEffect(() => {
    if (!getToken()) {
      window.location.href = "/login";
      return;
    }
    Promise.all([api<User>("/api/auth/me"), api<Meta>("/api/meta")])
      .then(([u, m]) => {
        setUser(u);
        setMeta(m);
        setFiltersState((f) => ({ ...f, start: m.project.period_start, end: m.project.period_end }));
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  const setFilters = useCallback((f: Partial<Filters>) => setFiltersState((prev) => ({ ...prev, ...f })), []);
  const can = useCallback((perm: string) => !!user && (user.permissions.includes(perm) || user.role === "admin"), [user]);
  const logout = useCallback(() => {
    setToken(null);
    window.location.href = "/login";
  }, []);

  const value = useMemo(() => ({ user, meta, filters, setFilters, can, logout, loading, error }),
    [user, meta, filters, setFilters, can, logout, loading, error]);
  return <AppCtx.Provider value={value}>{children}</AppCtx.Provider>;
}

export function useApp() {
  const v = useContext(AppCtx);
  if (!v) throw new Error("useApp di luar AppProvider");
  return v;
}

/** Parameter filter global untuk query API (tanggal, platform, kategori). */
export function useFilterParams() {
  const { filters } = useApp();
  return useMemo(() => ({ start: filters.start, end: filters.end, platforms: filters.platforms, categories: filters.categories }),
    [filters.start, filters.end, filters.platforms, filters.categories]);
}

/** Hook data sederhana dengan status loading/error. */
export function useApi<T>(path: string | null, deps: unknown[] = []) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tick, setTick] = useState(0);
  useEffect(() => {
    if (!path) return;
    let alive = true;
    setLoading(true);
    setError(null);
    api<T>(path)
      .then((d) => alive && setData(d))
      .catch((e) => alive && setError(e.message))
      .finally(() => alive && setLoading(false));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [path, tick, ...deps]);
  return { data, error, loading, reload: () => setTick((t) => t + 1), setData };
}
