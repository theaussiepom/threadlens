import { useMemo, useState } from "react";
import { useDashboardContext } from "@/context/DashboardContext";
import { MatterNodeCard } from "@/components/cards";
import { EmptyState, ErrorState, LoadingState, SectionHeading } from "@/components/ui";
import type { MatterNode } from "@/api/types";

const CLASS_ORDER = [
  "unavailable",
  "needs_attention",
  "recently_unstable",
  "diagnostics_limited",
  "unknown",
  "healthy",
];

function compareNodes(a: MatterNode, b: MatterNode): number {
  const ai = CLASS_ORDER.indexOf(a.classification);
  const bi = CLASS_ORDER.indexOf(b.classification);
  if (ai !== bi) return ai - bi;
  return (a.name || "").localeCompare(b.name || "");
}

export function DevicesPage() {
  const { data, error, hasLoaded, connected, refresh } = useDashboardContext();
  const [search, setSearch] = useState("");
  const [classification, setClassification] = useState("");

  const nodes = data?.matter.nodes ?? [];

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    return nodes
      .filter((n) => {
        if (classification && n.classification !== classification) return false;
        if (!q) return true;
        const hay = `${n.name} ${n.matter_name ?? ""} ${n.serial ?? ""} ${n.ha_device_name ?? ""}`.toLowerCase();
        return hay.includes(q);
      })
      .sort(compareNodes);
  }, [nodes, search, classification]);

  if (!data && !hasLoaded) return <LoadingState />;
  if (!data && hasLoaded) return <ErrorState message={error || "Cannot reach ThreadLens API"} onRetry={refresh} />;
  if (!connected) {
    return <ErrorState message={error || "ThreadLens API disconnected"} onRetry={refresh} />;
  }

  const concerning = filtered.filter((n) => n.classification !== "healthy");
  const healthy = filtered.filter((n) => n.classification === "healthy");

  return (
    <div className="max-w-6xl space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Matter devices</h1>
        <p className="mt-1 text-zl-muted">Bad-first. Select a node for read probes, events, and assessment.</p>
      </div>

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        <input
          type="search"
          placeholder="Search name, serial, HA name…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="min-h-11 flex-1 rounded-lg border border-zl-border bg-zl-bg px-3 text-sm text-zl-text"
        />
        <select
          value={classification}
          onChange={(e) => setClassification(e.target.value)}
          className="rounded-lg border border-zl-border bg-zl-bg px-3 text-sm text-zl-text"
        >
          <option value="">All classifications</option>
          {CLASS_ORDER.map((c) => (
            <option key={c} value={c}>
              {c.replace(/_/g, " ")}
            </option>
          ))}
        </select>
      </div>

      <section className="space-y-3">
        <SectionHeading>Needs attention ({concerning.length})</SectionHeading>
        {concerning.length === 0 ? (
          <EmptyState title="No concerning Matter nodes in this filter" />
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {concerning.map((node) => (
              <MatterNodeCard key={node.subject_id ?? `${node.server_id}:${node.node_id}`} node={node} />
            ))}
          </div>
        )}
      </section>

      <section className="space-y-3">
        <SectionHeading>Healthy ({healthy.length})</SectionHeading>
        {healthy.length === 0 ? (
          <EmptyState title="No healthy Matter nodes in this filter" />
        ) : (
          <div className="grid gap-3 md:grid-cols-2">
            {healthy.map((node) => (
              <MatterNodeCard key={node.subject_id ?? `${node.server_id}:${node.node_id}`} node={node} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
