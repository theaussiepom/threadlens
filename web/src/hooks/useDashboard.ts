import { useCallback, useEffect, useRef, useState } from "react";
import { DashboardError, fetchDashboard } from "../api/client";
import type { DashboardPayload } from "../api/types";

const REFRESH_INTERVAL_MS = 30_000;

export interface DashboardStatus {
  data: DashboardPayload | null;
  error: string | null;
  loading: boolean;
  /** True once at least one fetch has completed (success or failure). */
  hasLoaded: boolean;
  lastUpdated: Date | null;
  /** Whether the latest payload reports the Core API as connected. */
  connected: boolean;
  refresh: () => void;
}

/**
 * Polls `api/v1/dashboard` every 30s and exposes loading/error/stale state.
 * Keeps the last good payload visible while a refresh is in flight or fails,
 * so transient API blips do not blank the incident console.
 */
export function useDashboard(): DashboardStatus {
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const load = useCallback(async () => {
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    try {
      const payload = await fetchDashboard(controller.signal);
      if (controller.signal.aborted) return;
      setData(payload);
      setError(payload.error ?? null);
      setLastUpdated(new Date());
    } catch (err) {
      if (controller.signal.aborted) return;
      const message =
        err instanceof DashboardError || err instanceof Error
          ? err.message
          : "Failed to load ThreadLens data";
      setError(message);
      setLastUpdated(new Date());
    } finally {
      if (!controller.signal.aborted) {
        setLoading(false);
        setHasLoaded(true);
      }
    }
  }, []);

  useEffect(() => {
    void load();
    const timer = window.setInterval(() => void load(), REFRESH_INTERVAL_MS);
    return () => {
      window.clearInterval(timer);
      abortRef.current?.abort();
    };
  }, [load]);

  return {
    data,
    error,
    loading,
    hasLoaded,
    lastUpdated,
    connected: Boolean(data?.threadlens?.api_connected),
    refresh: load,
  };
}
