import { useState } from "react";
import type { ReportSection } from "../api/types";
import { REPORT_JSON_PATH, REPORT_YAML_PATH, resolveUrl } from "../api/paths";
import { fmtTime } from "../utils/format";
import { Card } from "./primitives";

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
    <Card title="Reports">
      <p className="tl-muted">
        Last generated: {report.last_generated_at ? fmtTime(report.last_generated_at) : "never"}
      </p>
      <div className="tl-btn-row">
        <a className="tl-btn" href={resolveUrl(yamlPath)} target="_blank" rel="noopener">
          Open YAML report
        </a>
        <a
          className="tl-btn tl-btn-secondary"
          href={resolveUrl(jsonPath)}
          target="_blank"
          rel="noopener"
        >
          Open JSON report
        </a>
        <button type="button" className="tl-btn tl-btn-secondary" onClick={copyPath}>
          {copied ? "Copied" : "Copy link"}
        </button>
      </div>
      <p className="tl-muted tl-note">
        Reports open directly from ThreadLens Core. They redact secrets but include operational
        metadata useful for support.
      </p>
    </Card>
  );
}
