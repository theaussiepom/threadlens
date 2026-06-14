export function LoadingState() {
  return (
    <div className="tl-card tl-state">
      <div className="tl-spinner" aria-hidden="true" />
      <p className="tl-muted">Loading ThreadLens data…</p>
    </div>
  );
}

export function ErrorState({
  message,
  onRetry,
  stale,
}: {
  message: string;
  onRetry: () => void;
  stale?: boolean;
}) {
  return (
    <div className="tl-card tl-state tl-error">
      <h2>{stale ? "ThreadLens data may be stale" : "ThreadLens dashboard unavailable"}</h2>
      <p>{message}</p>
      <p className="tl-muted">
        Could not reach <code>api/v1/dashboard</code>. Check that ThreadLens Core is running and
        reachable, then retry.
      </p>
      <div className="tl-btn-row">
        <button type="button" className="tl-btn" onClick={onRetry}>
          Retry
        </button>
      </div>
    </div>
  );
}

export function StaleBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="tl-stale-banner">
      <span>
        Showing last known data — refresh failed: {message}
      </span>
      <button type="button" className="tl-btn tl-btn-secondary tl-btn-small" onClick={onRetry}>
        Retry
      </button>
    </div>
  );
}
