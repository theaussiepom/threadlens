import { useCallback, useEffect, useRef, useState } from "react";
import { DashboardError, fetchDashboard } from "../api/client";
import type { DashboardPayload } from "../api/types";
import { type ConnectionState, liveConnection } from "@/lib/events";

const REFRESH_INTERVAL_MS = 30_000;
const SSE_DEBOUNCE_MS = 350;

const DASHBOARD_EVENTS = ["dashboard_updated", "dashboard_update", "health_updated"];

export interface DashboardStatus {
  data: DashboardPayload | null;
  error: string | null;
  loading: boolean;
  /** True once at least one fetch has completed (success or failure). */
  hasLoaded: boolean;
  lastUpdated: Date | null;
  /** Whether the latest payload reports the Core API as connected. */
  connected: boolean;
  /** SSE connection state for the live indicator. */
  liveState: ConnectionState;
  refresh: () => void;
}

/**
 * Fetches `api/v1/dashboard` and keeps it fresh via debounced SSE refetches,
 * with 30s polling fallback when the event stream is unavailable.
 */
export function useDashboard(): DashboardStatus {
  const [data, setData] = useState<DashboardPayload | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [hasLoaded, setHasLoaded] = useState(false);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [liveState, setLiveState] = useState<ConnectionState>(liveConnection.getState());
  const abortRef = useRef<AbortController | null>(null);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

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

  useEffect(() => {
    const unsubscribeEvents = liveConnection.subscribeEvents((eventName) => {
      if (!DASHBOARD_EVENTS.includes(eventName)) return;
      if (debounceRef.current) clearTimeout(debounceRef.current);
      debounceRef.current = setTimeout(() => void load(), SSE_DEBOUNCE_MS);
    });
    const unsubscribeState = liveConnection.subscribeState(setLiveState);
    return () => {
      unsubscribeEvents();
      unsubscribeState();
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [load]);

  useEffect(() => {
    let interval: ReturnType<typeof setInterval> | null = null;
    const unsubscribe = liveConnection.subscribeState((state) => {
      if (interval) {
        clearInterval(interval);
        interval = null;
      }
      if (state === "disconnected") {
        interval = setInterval(() => void load(), REFRESH_INTERVAL_MS);
      }
    });
    return () => {
      unsubscribe();
      if (interval) clearInterval(interval);
    };
  }, [load]);

  return {
    data,
    error,
    loading,
    hasLoaded,
    lastUpdated,
    connected: Boolean(data?.threadlens?.api_connected),
    liveState,
    refresh: load,
  };
}
