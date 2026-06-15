import { NavLink, Outlet } from "react-router-dom";
import { useDashboardContext } from "@/context/DashboardContext";
import { fmtTimeShort } from "@/utils/format";

const nav = [
  { to: "/", label: "Overview", end: true },
  { to: "/devices", label: "Devices" },
  { to: "/infrastructure", label: "Infrastructure" },
  { to: "/timeline", label: "Timeline" },
  { to: "/reports", label: "Reports" },
  { to: "/diagnostics", label: "Diagnostics" },
];

function navClass(isActive: boolean): string {
  return `block rounded-lg px-3 py-2.5 min-h-11 text-sm font-medium transition-colors ${
    isActive
      ? "bg-zl-accent/15 text-zl-accent"
      : "text-zl-muted hover:bg-zl-surface-2 hover:text-zl-text"
  }`;
}

function ConnectionDot({ connected, loading }: { connected: boolean; loading: boolean }) {
  const color = loading ? "bg-zl-watch animate-pulse" : connected ? "bg-zl-healthy" : "bg-zl-critical";
  const label = loading ? "Refreshing" : connected ? "Connected" : "Disconnected";
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-zl-muted" title={label}>
      <span className={`h-2 w-2 rounded-full ${color}`} aria-hidden="true" />
      {label}
    </span>
  );
}

function ModeBanner({ connected, mqttConnected }: { connected: boolean; mqttConnected: boolean | null }) {
  if (!connected) {
    return (
      <div className="border-b border-zl-critical/40 bg-zl-critical/10 px-4 py-2 text-sm text-zl-critical sm:px-6">
        ThreadLens Core API is unreachable. Check that Core is running and retry.
      </div>
    );
  }
  if (mqttConnected === false) {
    return (
      <div className="border-b border-zl-watch/40 bg-zl-watch/10 px-4 py-2 text-sm text-zl-watch sm:px-6">
        Core is running, but MQTT publishing is not connected.
      </div>
    );
  }
  return (
    <div className="border-b border-zl-healthy/30 bg-zl-healthy/10 px-4 py-2 text-sm text-zl-healthy sm:px-6">
      Live mode: connected to ThreadLens Core
    </div>
  );
}

export function AppShell() {
  const { data, connected, loading, lastUpdated, refresh } = useDashboardContext();
  const version = data?.threadlens?.version ?? "—";
  const apiConnected = Boolean(data?.threadlens?.api_connected);
  const mqttConnected = data?.mqtt?.connected ?? null;
  const updatedLabel = lastUpdated ? fmtTimeShort(lastUpdated.toISOString()) : "—";

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      <aside className="hidden w-60 shrink-0 flex-col border-r border-zl-border bg-zl-surface lg:flex">
        <div className="border-b border-zl-border p-5">
          <div className="flex items-center gap-2">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-zl-accent/20 text-sm font-bold text-zl-accent">
              TL
            </div>
            <div>
              <div className="font-semibold tracking-tight">ThreadLens</div>
              <div className="text-xs text-zl-muted">Read-only diagnostics</div>
            </div>
          </div>
        </div>
        <nav className="flex-1 space-y-1 p-3" aria-label="Main navigation">
          {nav.map((item) => (
            <NavLink key={item.to} to={item.to} end={item.end} className={({ isActive }) => navClass(isActive)}>
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="border-t border-zl-border p-4 text-xs text-zl-muted">
          <div className="mb-1">Updated {updatedLabel}</div>
          <div>v{version}</div>
        </div>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col overflow-x-hidden">
        <header className="flex flex-wrap items-center justify-between gap-3 border-b border-zl-border bg-zl-surface/80 px-4 py-3 backdrop-blur sm:px-6">
          <div className="flex items-center gap-3">
            <span className="font-semibold tracking-tight lg:hidden">ThreadLens</span>
            <h1 className="hidden text-sm font-medium text-zl-muted sm:block">
              Thread and Matter-over-Thread observability
            </h1>
            <ConnectionDot connected={apiConnected && connected} loading={loading} />
          </div>
          <button
            type="button"
            onClick={() => void refresh()}
            disabled={loading}
            className="min-h-11 rounded-lg border border-zl-border bg-zl-bg px-4 py-2 text-sm text-zl-text hover:bg-zl-surface-2 disabled:opacity-60"
          >
            {loading ? "Refreshing…" : "Refresh"}
          </button>
        </header>

        <nav
          className="flex gap-1 overflow-x-auto scroll-px-3 border-b border-zl-border bg-zl-surface px-3 py-2 lg:hidden"
          aria-label="Main navigation"
        >
          {nav.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `whitespace-nowrap rounded-lg px-3 py-2 min-h-11 text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-zl-accent/15 text-zl-accent"
                    : "text-zl-muted hover:bg-zl-surface-2 hover:text-zl-text"
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>

        <ModeBanner connected={apiConnected && connected} mqttConnected={mqttConnected} />

        <main
          className="flex-1 overflow-auto p-4 sm:p-6 pb-[max(1rem,env(safe-area-inset-bottom))]"
          id="main-content"
        >
          <Outlet />
        </main>
      </div>
    </div>
  );
}
