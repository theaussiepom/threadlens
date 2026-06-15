import type { ReactNode } from "react";
import type { HealthState, IncidentState, NodeClassification } from "@/api/types";
import {
  classificationLabel,
  classificationToSeverity,
  healthToSeverity,
  incidentToSeverity,
  severityBg,
  severityDot,
  severityLabel,
  type Severity,
} from "@/lib/severity";
import { fmtRelative } from "@/utils/format";

export function Card({
  title,
  subtitle,
  actions,
  children,
  className = "",
}: {
  title?: ReactNode;
  subtitle?: string;
  actions?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section
      className={`rounded-xl border border-zl-border bg-zl-surface p-5 shadow-sm ${className}`}
    >
      {(title || subtitle || actions) && (
        <header className="mb-4 flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0 flex-1">
            {title && <h2 className="text-base font-semibold text-zl-text">{title}</h2>}
            {subtitle && <p className="mt-1 text-sm text-zl-muted">{subtitle}</p>}
          </div>
          {actions && <div className="shrink-0">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export function SectionHeading({ children }: { children: ReactNode }) {
  return (
    <h2 className="text-xs font-semibold uppercase tracking-wide text-zl-muted">{children}</h2>
  );
}

export function Badge({
  children,
  severity,
  title,
}: {
  children: ReactNode;
  severity?: Severity;
  title?: string;
}) {
  return (
    <span
      title={title}
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${
        severity ? severityBg(severity) : "bg-zl-surface-2 text-zl-muted border-zl-border"
      }`}
    >
      {children}
    </span>
  );
}

export function SeverityBadge({ severity }: { severity: Severity }) {
  return (
    <Badge severity={severity}>
      <span className={`h-1.5 w-1.5 rounded-full ${severityDot(severity)}`} />
      {severityLabel(severity)}
    </Badge>
  );
}

export function HealthBadge({ state }: { state: HealthState | null | undefined }) {
  return <SeverityBadge severity={healthToSeverity(state)} />;
}

export function IncidentBadge({ state }: { state: IncidentState }) {
  return <SeverityBadge severity={incidentToSeverity(state)} />;
}

export function ClassificationBadge({ classification }: { classification: NodeClassification }) {
  return (
    <Badge severity={classificationToSeverity(classification)}>
      {classificationLabel(classification)}
    </Badge>
  );
}

export function MetricPill({
  label,
  value,
  severity,
}: {
  label: string;
  value: string | number;
  severity?: Severity;
}) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-1 text-xs ${
        severity && severity !== "healthy"
          ? severityBg(severity)
          : "border-zl-border bg-zl-bg/50 text-zl-muted"
      }`}
    >
      <span className="uppercase tracking-wide">{label}</span>
      <span className="font-semibold text-zl-text">{value}</span>
    </span>
  );
}

export function StatTile({
  label,
  value,
  severity,
  hint,
}: {
  label: string;
  value: string | number;
  severity?: Severity;
  hint?: string;
}) {
  return (
    <div className="rounded-lg border border-zl-border bg-zl-bg/50 px-4 py-3">
      <div className="text-xs uppercase tracking-wide text-zl-muted">{label}</div>
      <div
        className={`mt-1 text-2xl font-semibold ${
          severity ? severityBg(severity).split(" ")[1] : "text-zl-text"
        }`}
      >
        {value}
      </div>
      {hint && <div className="mt-0.5 text-xs text-zl-muted">{hint}</div>}
    </div>
  );
}

export function LastSeenText({ iso, prefix }: { iso?: string | null; prefix?: string }) {
  return (
    <span title={iso ?? undefined} className="text-zl-muted">
      {prefix ? `${prefix} ` : ""}
      {fmtRelative(iso)}
    </span>
  );
}

function EvidenceColumn({
  title,
  items,
  tone,
  emptyText,
}: {
  title: string;
  items: string[];
  tone: "positive" | "neutral" | "muted";
  emptyText: string;
}) {
  const border =
    tone === "positive"
      ? "border-zl-healthy/20"
      : tone === "neutral"
        ? "border-zl-border"
        : "border-zl-watch/20";
  return (
    <div className={`rounded-lg border ${border} bg-zl-bg/40 p-3`}>
      <h3 className="mb-2 text-xs font-semibold uppercase tracking-wide text-zl-muted">{title}</h3>
      {items.length === 0 ? (
        <p className="text-sm italic text-zl-muted">{emptyText}</p>
      ) : (
        <ul className="space-y-2">
          {items.map((item, i) => (
            <li key={i} className="text-sm leading-snug text-zl-text">
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

export function EvidenceList({
  items,
  emptyText = "No evidence recorded.",
}: {
  items: string[];
  emptyText?: string;
}) {
  return <EvidenceColumn title="Evidence" items={items} tone="positive" emptyText={emptyText} />;
}

export function LimitationsList({
  items,
  emptyText = "No limitations noted.",
}: {
  items: string[];
  emptyText?: string;
}) {
  return <EvidenceColumn title="Limitations" items={items} tone="muted" emptyText={emptyText} />;
}

export function KeyValue({ rows }: { rows: { label: ReactNode; value: ReactNode }[] }) {
  return (
    <dl className="grid gap-2">
      {rows.map((row, idx) => (
        <div
          key={idx}
          className="grid gap-1 border-b border-zl-border/50 pb-2 last:border-0 last:pb-0 sm:grid-cols-[minmax(8rem,30%)_1fr]"
        >
          <dt className="text-xs font-medium uppercase tracking-wide text-zl-muted">{row.label}</dt>
          <dd className="text-sm text-zl-text">{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function EmptyState({ title, detail }: { title: string; detail?: string }) {
  return (
    <div className="rounded-xl border border-dashed border-zl-border bg-zl-surface/50 p-10 text-center">
      <p className="font-medium text-zl-text">{title}</p>
      {detail && <p className="mt-2 text-sm text-zl-muted">{detail}</p>}
    </div>
  );
}

export function LoadingState({ label = "Loading ThreadLens…" }: { label?: string }) {
  return (
    <div className="flex items-center justify-center p-16 text-zl-muted">
      <div className="animate-pulse">{label}</div>
    </div>
  );
}

export function ErrorState({ message, onRetry }: { message: string; onRetry?: () => void }) {
  const friendly =
    message.includes("(500)") || message.includes("(503)")
      ? "ThreadLens Core is still starting or temporarily busy. This usually clears after a moment."
      : message.includes("not reachable") || message.includes("Failed to fetch")
        ? "ThreadLens Core is not reachable from your browser."
        : message;

  return (
    <div className="rounded-xl border border-zl-critical/40 bg-zl-critical/10 p-6 text-zl-critical">
      <p>{friendly}</p>
      {onRetry && (
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 min-h-11 rounded-lg border border-zl-critical/40 px-4 py-2 text-sm hover:bg-zl-critical/10"
        >
          Try again
        </button>
      )}
    </div>
  );
}

export function StaleBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-zl-watch/40 bg-zl-watch/10 px-4 py-3 text-sm text-zl-watch">
      <span>Showing last known data — refresh failed: {message}</span>
      <button
        type="button"
        onClick={onRetry}
        className="rounded-lg border border-zl-watch/40 px-3 py-1.5 text-sm hover:bg-zl-watch/10"
      >
        Retry
      </button>
    </div>
  );
}
