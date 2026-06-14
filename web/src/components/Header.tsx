import { fmtTimeShort } from "../utils/format";
import { resolveUrl, REPORT_YAML_PATH } from "../api/paths";

export function Header({
  version,
  connected,
  lastUpdated,
  loading,
  onRefresh,
}: {
  version: string | null;
  connected: boolean;
  lastUpdated: Date | null;
  loading: boolean;
  onRefresh: () => void;
}) {
  const updatedLabel = lastUpdated ? fmtTimeShort(lastUpdated.toISOString()) : "—";
  return (
    <header className="tl-header">
      <div className="tl-brand">
        <span className="tl-logo" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="22" height="22" role="img" aria-label="ThreadLens">
            <circle cx="12" cy="12" r="3" fill="currentColor" />
            <circle cx="12" cy="12" r="9" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.55" />
            <circle cx="12" cy="3" r="1.6" fill="currentColor" />
            <circle cx="20" cy="16" r="1.6" fill="currentColor" />
            <circle cx="4" cy="16" r="1.6" fill="currentColor" />
          </svg>
        </span>
        <div className="tl-brand-text">
          <h1>ThreadLens</h1>
          <span className="tl-version">v{version || "?"}</span>
        </div>
      </div>

      <div className="tl-header-status">
        <span
          className={`tl-conn tl-conn-${connected ? "up" : "down"}`}
          title={connected ? "Connected to ThreadLens Core API" : "ThreadLens Core API unreachable"}
        >
          <span className="tl-conn-dot" aria-hidden="true" />
          {connected ? "Connected" : "Disconnected"}
        </span>
        <span className="tl-updated tl-muted">Updated {updatedLabel}</span>
        <a
          className="tl-icon-link"
          href={resolveUrl(REPORT_YAML_PATH)}
          target="_blank"
          rel="noopener"
          title="Open YAML report"
        >
          Report
        </a>
        <button
          type="button"
          className="tl-btn tl-btn-icon"
          onClick={onRefresh}
          disabled={loading}
          aria-label="Refresh dashboard"
        >
          <span className={`tl-refresh-icon${loading ? " tl-spin" : ""}`} aria-hidden="true">
            ↻
          </span>
          <span className="tl-btn-label">{loading ? "Refreshing" : "Refresh"}</span>
        </button>
      </div>
    </header>
  );
}
