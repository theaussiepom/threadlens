import type { Otbr } from "../api/types";
import { boolText, orDash } from "../utils/format";
import { Card, Collapsible, EmptyHint, HealthBadge, KeyValue } from "./primitives";

function OtbrCard({ otbr }: { otbr: Otbr }) {
  const displayHealth = otbr.display_health || otbr.health;
  const effectiveState = otbr.effective_state || otbr.role || otbr.thread_state || "—";
  const sourceLabel = otbr.state_source_label || otbr.thread_state_source || "—";

  // A real, unreconciled mismatch is prominent; a reconciled one is info-only.
  const realProblem = otbr.rest_endpoint_mismatch && !otbr.mismatch_reconciled;

  return (
    <div className="tl-subcard">
      <div className="tl-subcard-head">
        <strong>{otbr.name || otbr.id || "OTBR"}</strong>
        <HealthBadge state={displayHealth} />
      </div>

      <KeyValue
        rows={[
          { label: "Reachable", value: boolText(otbr.reachable, "Yes", "No") },
          { label: "Effective state", value: orDash(effectiveState) },
          { label: "Role", value: orDash(otbr.role) },
          { label: "Source", value: orDash(sourceLabel) },
          { label: "Network", value: orDash(otbr.network_name) },
          { label: "Extended PAN ID", value: orDash(otbr.extended_pan_id) },
          { label: "RLOC16", value: orDash(otbr.rloc16) },
        ]}
      />

      {realProblem && (
        <div className="tl-inline-warn">
          OTBR REST endpoints disagree and ThreadLens could not reconcile an active state. Review
          this OTBR.
        </div>
      )}

      {otbr.rest_endpoint_mismatch && otbr.mismatch_reconciled && otbr.mismatch_detail && (
        <Collapsible summary="Endpoint reconciliation details" className="tl-info-details">
          <p className="tl-info-text">{otbr.mismatch_detail}</p>
          <KeyValue
            rows={[
              { label: "JSON:API state", value: orDash(otbr.json_api_thread_state) },
              { label: "/node state", value: orDash(otbr.legacy_node_thread_state) },
            ]}
          />
        </Collapsible>
      )}
    </div>
  );
}

export function OtbrSection({ otbrs }: { otbrs: Otbr[] }) {
  if (!otbrs.length) {
    return (
      <Card title="OTBRs">
        <EmptyHint>No OTBRs configured or reported.</EmptyHint>
      </Card>
    );
  }
  return (
    <Card title="OTBRs">
      {otbrs.map((otbr) => (
        <OtbrCard key={otbr.id ?? otbr.name ?? Math.random()} otbr={otbr} />
      ))}
    </Card>
  );
}
