import { useState } from "react";
import { useDashboard } from "./hooks/useDashboard";
import type { MatterNode } from "./api/types";
import { Header } from "./components/Header";
import { IncidentSummary } from "./components/IncidentSummary";
import { MatterNodeHealth } from "./components/MatterNodeHealth";
import { NodeDrilldown } from "./components/NodeDrilldown";
import { OtbrSection } from "./components/OtbrSection";
import { MdnsTrelSection } from "./components/TrelSection";
import {
  MatterServerSection,
  MqttSectionView,
  NetworksSection,
} from "./components/InfraSections";
import { Reports } from "./components/Reports";
import { Diagnostics } from "./components/Diagnostics";
import { ErrorState, LoadingState, StaleBanner } from "./components/StateViews";

export default function App() {
  const { data, error, loading, hasLoaded, lastUpdated, refresh } = useDashboard();
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  const connected = Boolean(data?.threadlens?.api_connected);
  const version = data?.threadlens?.version ?? null;

  const selectedNode: MatterNode | null =
    (selectedNodeId && data?.matter?.nodes?.find((n) => n.subject_id === selectedNodeId)) || null;

  return (
    <div className="tl-app">
      <Header
        version={version}
        connected={connected}
        lastUpdated={lastUpdated}
        loading={loading}
        onRefresh={refresh}
      />

      <main className="tl-main">
        {!data && !hasLoaded && <LoadingState />}

        {!data && hasLoaded && (
          <ErrorState message={error || "Cannot reach the ThreadLens API"} onRetry={refresh} />
        )}

        {data && !connected && (
          <ErrorState
            message={error || data.error || "The dashboard payload reported the API as disconnected."}
            onRetry={refresh}
          />
        )}

        {data && connected && (
          <>
            {error && <StaleBanner message={error} onRetry={refresh} />}

            <IncidentSummary incident={data.incident} />

            <MatterNodeHealth
              matter={data.matter}
              onSelect={(node) => setSelectedNodeId(node.subject_id)}
            />

            <div className="tl-infra-grid">
              <OtbrSection otbrs={data.otbrs} />
              <MatterServerSection matter={data.matter} />
              <NetworksSection networks={data.networks} />
              <MdnsTrelSection mdns={data.mdns} trel={data.trel} />
              <MqttSectionView mqtt={data.mqtt} />
            </div>

            <Reports report={data.report} />
            <Diagnostics data={data} />
          </>
        )}
      </main>

      {selectedNode && data && (
        <NodeDrilldown node={selectedNode} data={data} onClose={() => setSelectedNodeId(null)} />
      )}

      <footer className="tl-footer tl-muted">
        ThreadLens Core dashboard · read-only · does not mutate Thread, Matter, OTBR, or MQTT state
      </footer>
    </div>
  );
}
