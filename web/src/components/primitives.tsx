import type { ReactNode } from "react";
import type { HealthState } from "../api/types";
import { healthTone, type Tone } from "../utils/health";

export function Badge({
  tone,
  children,
}: {
  tone: Tone;
  children: ReactNode;
}) {
  return <span className={`tl-badge tl-tone-${tone}`}>{children}</span>;
}

export function HealthBadge({ state }: { state: HealthState | null | undefined }) {
  const label = state || "unknown";
  return <Badge tone={healthTone(state)}>{label}</Badge>;
}

export function Card({
  title,
  actions,
  className,
  children,
}: {
  title?: ReactNode;
  actions?: ReactNode;
  className?: string;
  children: ReactNode;
}) {
  return (
    <section className={`tl-card${className ? ` ${className}` : ""}`}>
      {(title || actions) && (
        <header className="tl-card-head">
          {title && <h2 className="tl-card-title">{title}</h2>}
          {actions && <div className="tl-card-actions">{actions}</div>}
        </header>
      )}
      {children}
    </section>
  );
}

export interface KeyValueRow {
  label: ReactNode;
  value: ReactNode;
}

export function KeyValue({ rows }: { rows: KeyValueRow[] }) {
  return (
    <dl className="tl-kv">
      {rows.map((row, idx) => (
        <div className="tl-kv-row" key={idx}>
          <dt>{row.label}</dt>
          <dd>{row.value}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Collapsible({
  summary,
  children,
  defaultOpen = false,
  className,
}: {
  summary: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  className?: string;
}) {
  return (
    <details className={`tl-collapsible${className ? ` ${className}` : ""}`} open={defaultOpen}>
      <summary>{summary}</summary>
      <div className="tl-collapsible-body">{children}</div>
    </details>
  );
}

export function EmptyHint({ children }: { children: ReactNode }) {
  return <p className="tl-muted tl-empty">{children}</p>;
}
