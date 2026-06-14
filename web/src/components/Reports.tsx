import { useState } from "react";
import type { ReportSection } from "../api/types";
import { REPORT_JSON_PATH, REPORT_YAML_PATH, resolveUrl } from "../api/paths";
import { fmtTime } from "../utils/format";
import { Card, KeyValue } from "./primitives";

export function Reports({ report }: { report: ReportSection }) {
  const [copied, setCopied] = useState(false);
  const yamlPath = report.report_url || REPORT_YAML_PATH;
  const jsonPath = report.report_url_json || REPORT_JSON_PATH;

  const copyPath = async () => {
    try {
      await navigator.clipboard?.writeText(resolveUrl(yamlPath));
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1500);
    } catch {
      setCopied(false);
    }
  };

  return (
    <Card title="Reports" className="tl-card-compact">
      <KeyValue
        rows={[
          {
            label: "Last generated",
            value: report.last_generated_at ? fmtTime(report.last_generated_at) : "never",
          },
        ]}
      />
      <div className="tl-btn-row tl-btn-row-compact">
        <a className="tl-btn tl-btn-small" href={resolveUrl(yamlPath)} target="_blank" rel="noopener">
          YAML
        </a>
        <a
          className="tl-btn tl-btn-small tl-btn-secondary"
          href={resolveUrl(jsonPath)}
          target="_blank"
          rel="noopener"
        >
          JSON
        </a>
        <button type="button" className="tl-btn tl-btn-small tl-btn-secondary" onClick={copyPath}>
          {copied ? "Copied" : "Copy link"}
        </button>
      </div>
    </Card>
  );
}
