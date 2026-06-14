/**
 * ThreadLens canonical dashboard (Core-served).
 *
 * Dependency-free vanilla JS. Fetches the pre-aggregated payload from the Core
 * REST API using path-safe relative URLs, so it works when served from `/`,
 * behind a reverse proxy, or under a Home Assistant Ingress path prefix. It
 * never talks to Home Assistant and never imports external scripts.
 */

const REFRESH_INTERVAL_MS = 30000;

/**
 * Resolve a relative API/asset path against the current document location.
 * Using `new URL(".", location.href)` keeps requests relative to wherever the
 * dashboard is hosted (root, reverse-proxy subpath, or HA Ingress prefix).
 */
function apiUrl(path) {
  const base = new URL(".", window.location.href).href;
  const normalized = path.startsWith("/") ? path.slice(1) : path;
  return new URL(normalized, base).href;
}

function esc(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function healthClass(state) {
  switch (state) {
    case "healthy":
      return "tl-ok";
    case "warning":
      return "tl-warn";
    case "degraded":
      return "tl-degraded";
    case "critical":
      return "tl-critical";
    default:
      return "tl-unknown";
  }
}

function badge(state) {
  const text = state || "unknown";
  return `<span class="tl-badge ${healthClass(text)}">${esc(text)}</span>`;
}

const NODE_CLASS_META = {
  unavailable: { label: "Unavailable", cls: "tl-critical" },
  recently_unstable: { label: "Recently unstable", cls: "tl-warn" },
  healthy: { label: "Healthy", cls: "tl-ok" },
  unknown: { label: "Unknown", cls: "tl-unknown" },
};

function nodeBadge(classification) {
  const meta = NODE_CLASS_META[classification] || NODE_CLASS_META.unknown;
  return `<span class="tl-badge ${meta.cls}">${esc(meta.label)}</span>`;
}

const INCIDENT_META = {
  ok: { label: "OK", cls: "tl-ok" },
  watch: { label: "Watch", cls: "tl-warn" },
  incident: { label: "Incident", cls: "tl-critical" },
  unknown: { label: "Unknown", cls: "tl-unknown" },
};

function boolText(value, onText, offText) {
  if (value === null || value === undefined) return "—";
  return value ? onText : offText;
}

function fmtTime(value) {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toLocaleString();
}

function fmtDuration(seconds) {
  if (seconds === null || seconds === undefined) return "—";
  const value = Number(seconds);
  if (Number.isNaN(value) || value < 0) return "—";
  if (value < 60) return `${Math.round(value)}s`;
  if (value < 3600) return `${Math.round(value / 60)}m`;
  return `${(value / 3600).toFixed(1)}h`;
}

class ThreadLensDashboard {
  constructor(root) {
    this._root = root;
    this._data = null;
    this._error = null;
    this._loading = false;
    this._lastFetch = null;
    this._timer = null;
    this._selectedNodeId = null;
  }

  start() {
    this._update();
    this._fetch();
    if (this._timer) clearInterval(this._timer);
    this._timer = setInterval(() => this._fetch(), REFRESH_INTERVAL_MS);
  }

  async _fetch() {
    this._loading = true;
    this._update();
    try {
      const response = await fetch(apiUrl("api/v1/dashboard"), {
        headers: { Accept: "application/json" },
        cache: "no-store",
      });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}`);
      }
      const result = await response.json();
      if (result && result.threadlens) {
        this._data = result;
        this._error = result.error || null;
      } else {
        this._data = null;
        this._error = (result && result.error) || "Invalid ThreadLens dashboard response";
      }
    } catch (err) {
      this._data = null;
      this._error = (err && (err.message || String(err))) || "Failed to load ThreadLens data";
    }
    this._loading = false;
    this._lastFetch = new Date();
    this._update();
  }

  _update() {
    if (!this._root) return;
    this._root.innerHTML = this._content();

    const refresh = this._root.querySelector("#tl-refresh");
    if (refresh) refresh.addEventListener("click", () => this._fetch());

    const copy = this._root.querySelector("#tl-copy-report");
    if (copy) {
      copy.addEventListener("click", () => {
        const url = copy.getAttribute("data-url");
        if (url && navigator.clipboard) navigator.clipboard.writeText(url);
      });
    }

    this._root.querySelectorAll("[data-node-id]").forEach((el) => {
      el.addEventListener("click", () => {
        this._selectedNodeId = el.getAttribute("data-node-id");
        this._update();
      });
      el.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          this._selectedNodeId = el.getAttribute("data-node-id");
          this._update();
        }
      });
    });

    const back = this._root.querySelector("#tl-node-back");
    if (back) {
      back.addEventListener("click", () => {
        this._selectedNodeId = null;
        this._update();
      });
    }
  }

  _content() {
    const d = this._data;
    const tl = (d && d.threadlens) || {};
    const connected = tl.api_connected;
    const lastFetch = this._lastFetch ? this._lastFetch.toLocaleTimeString() : "—";

    const header = `
      <div class="tl-header">
        <div class="tl-title">
          <span class="tl-logo" aria-hidden="true">◇</span>
          <h1>ThreadLens</h1>
        </div>
        <div class="tl-header-meta">
          <span class="tl-badge ${connected ? "tl-ok" : "tl-critical"}">
            ${connected ? "API connected" : "API disconnected"}
          </span>
          <span class="tl-muted">v${esc(tl.version || "?")}</span>
          <span class="tl-muted">Updated ${esc(lastFetch)}</span>
          <button id="tl-refresh" class="tl-btn" ${this._loading ? "disabled" : ""}>
            ${this._loading ? "Refreshing…" : "Refresh"}
          </button>
        </div>
      </div>`;

    if (!d) {
      if (this._error) {
        return (
          header +
          `<div class="tl-card tl-error">
            <h2>ThreadLens dashboard unavailable</h2>
            <p>${esc(this._error)}</p>
            <p class="tl-muted">Could not reach <code>api/v1/dashboard</code>. Check that ThreadLens Core is running and reachable, then refresh.</p>
          </div>`
        );
      }
      return header + `<div class="tl-card"><p class="tl-muted">Loading ThreadLens data…</p></div>`;
    }

    if (!connected) {
      const message = this._error || "Cannot reach the ThreadLens API";
      return (
        header +
        `<div class="tl-card tl-error">
          <h2>ThreadLens API unavailable</h2>
          <p>${esc(message)}</p>
          <p class="tl-muted">The dashboard payload reported the API as disconnected. Check ThreadLens Core logs, then refresh.</p>
        </div>`
      );
    }

    const matter = d.matter || {};
    if (this._selectedNodeId) {
      const node = (matter.nodes || []).find(
        (n) => String(n.node_id) === String(this._selectedNodeId)
      );
      if (node) {
        return header + this._nodeDetailView(node, d);
      }
      this._selectedNodeId = null;
    }

    return (
      header +
      this._incidentCard(d) +
      this._overallCard(tl) +
      this._summaryCards(d) +
      this._matterNodeHealth(matter) +
      this._otbrSection(d.otbrs || []) +
      this._networksSection(d.networks || []) +
      this._matterSection(matter) +
      this._mdnsTrelSection(d.mdns || {}, d.trel || {}) +
      this._mqttSection(d.mqtt) +
      this._reportSection(d.report || {}) +
      this._diagnosticsSection(d)
    );
  }

  _incidentCard(d) {
    const incident = d.incident || {};
    const meta = INCIDENT_META[incident.state] || INCIDENT_META.unknown;
    const affected = incident.affected_node_names || [];
    const affectedLine = affected.length
      ? `<p class="tl-info-text">Affected nodes: ${esc(affected.join(", "))}</p>`
      : "";
    const headline = incident.title || incident.headline || "";
    const detail = incident.summary || incident.detail || "";
    return `
      <div class="tl-card tl-incident tl-incident-${esc(incident.state || "unknown")}">
        <div class="tl-incident-head">
          <h2>Network incident summary</h2>
          <span class="tl-badge ${meta.cls}">${esc(meta.label)}</span>
        </div>
        <p class="tl-incident-headline">${esc(headline)}</p>
        <p class="tl-info-text">${esc(detail)}</p>
        ${affectedLine}
      </div>`;
  }

  _matterNodeHealth(matter) {
    const nodes = matter.nodes || [];
    if (!nodes.length) {
      return `<div class="tl-card"><h2>Matter node health</h2><p class="tl-muted">No Matter nodes reported.</p></div>`;
    }
    const groupsOrder = [
      ["unavailable", "Needs attention"],
      ["recently_unstable", "Recently unstable"],
      ["unknown", "Unknown"],
      ["healthy", "Healthy"],
    ];
    const grouped = {};
    nodes.forEach((n) => {
      (grouped[n.classification] = grouped[n.classification] || []).push(n);
    });
    const sections = groupsOrder
      .filter(([key]) => (grouped[key] || []).length)
      .map(([key, title]) => {
        const rows = grouped[key].map((n) => this._nodeRow(n)).join("");
        return `<div class="tl-node-group"><div class="tl-node-group-title">${esc(title)} (${grouped[key].length})</div>${rows}</div>`;
      })
      .join("");
    return `
      <div class="tl-card">
        <h2>Matter node health</h2>
        <div class="tl-node-counts">
          <span>${esc(matter.unavailable_count || 0)} unavailable</span>
          <span>${esc(matter.unstable_count || 0)} unstable</span>
          <span>${esc(matter.healthy_count || 0)} healthy</span>
          <span>${esc(matter.unknown_count || 0)} unknown</span>
        </div>
        ${sections}
        <p class="tl-muted tl-note">Select a node to inspect recent events and a conservative assessment.</p>
      </div>`;
  }

  _availabilityLine(n) {
    const down = n.unsubscribe_count_24h || 0;
    const up = n.resubscribe_count_24h || 0;
    const episodes = n.offline_episodes_24h || 0;
    const episodeLabel = episodes === 1 ? "episode" : "episodes";
    return `<span class="tl-muted">${esc(down)} down / ${esc(up)} up · ${esc(episodes)} ${episodeLabel} (24h)</span>`;
  }

  _nodeRow(n) {
    const sub = [n.vendor, n.product].filter(Boolean).join(" · ");
    const secondary = [];
    if (n.serial) secondary.push(n.serial);
    secondary.push(`#${n.node_id}`);
    if (sub) secondary.push(sub);
    const lastEvent = n.last_event_at ? `Last event ${fmtTime(n.last_event_at)}` : "";
    return `
      <div class="tl-node-row" data-node-id="${esc(n.node_id)}" role="button" tabindex="0" title="View node details">
        <div class="tl-node-row-main">
          <strong>${esc(n.name)}</strong>
          <span class="tl-muted">${esc(secondary.join(" · "))}</span>
          <div>${this._availabilityLine(n)}</div>
          ${lastEvent ? `<span class="tl-muted">${esc(lastEvent)}</span>` : ""}
        </div>
        <div class="tl-node-row-meta">
          <span class="tl-node-view">View</span>
          ${nodeBadge(n.classification)}
        </div>
      </div>`;
  }

  _nodeDetailView(node, d) {
    const events = (node.events && node.events.length ? node.events : null) ||
      ((d.events && d.events.items) || []).filter((e) => e.subject_id === node.subject_id);
    const assessment = this._nodeAssessment(node, d);
    const eventRows = events.length
      ? events
          .map(
            (e) => `
            <div class="tl-event-row">
              <span class="tl-muted">${esc(fmtTime(e.timestamp))}</span>
              <span>${esc(e.event_type)}</span>
              <span class="tl-muted">${esc(e.severity || "")}</span>
            </div>`
          )
          .join("")
      : `<p class="tl-muted">No recent events for this node in the current window.</p>`;
    const sub = [node.vendor, node.product].filter(Boolean).join(" · ");
    return `
      <div class="tl-card">
        <div class="tl-subcard-head">
          <button id="tl-node-back" class="tl-btn tl-btn-secondary">← Back</button>
          ${nodeBadge(node.classification)}
        </div>
        <h2>${esc(node.name)} <span class="tl-muted">#${esc(node.node_id)}</span></h2>
        ${sub ? `<p class="tl-muted">${esc(sub)}</p>` : ""}
        <div class="tl-kv">
          <span>Availability</span><span>${boolText(node.available, "Available", "Unavailable")}</span>
          <span>Health</span><span>${esc(node.health || "—")}</span>
          <span>Server</span><span>${esc(node.server_id || "—")}</span>
          <span>Firmware</span><span>${esc(node.firmware || "—")}</span>
          <span>Last seen</span><span>${esc(fmtTime(node.last_seen))}</span>
          <span>Last unavailable</span><span>${esc(node.last_unavailable ? fmtTime(node.last_unavailable) : "—")}</span>
          <span>Unavailable transitions (24h)</span><span>${esc(node.unsubscribe_count_24h || 0)}</span>
          <span>Recovered (24h)</span><span>${esc(node.resubscribe_count_24h || 0)}</span>
          <span>Median offline (24h)</span><span>${esc(fmtDuration(node.median_offline_seconds_24h))}</span>
          <span>Total offline (24h)</span><span>${esc(fmtDuration(node.total_offline_seconds_24h || 0))}</span>
          <span>Offline episodes (24h)</span><span>${esc(node.offline_episodes_24h || 0)}</span>
          <span>Availability flaps (24h)</span><span>${esc(node.availability_flaps_24h ?? "—")}</span>
          <span>Recent down / up (events)</span><span>${esc(node.recent_unavailable_count || 0)} / ${esc(node.recent_recovered_count || 0)}</span>
        </div>
      </div>
      <div class="tl-card">
        <h2>What this suggests</h2>
        <p class="tl-info-text">${esc(assessment)}</p>
        <p class="tl-muted tl-note">ThreadLens does not infer Thread parentage, routing, or root cause. This is a conservative read of observed events.</p>
      </div>
      <div class="tl-card">
        <h2>Recent events</h2>
        ${eventRows}
      </div>`;
  }

  _nodeAssessment(node, d) {
    const events = (d.events && d.events.items) || [];
    const matter = d.matter || {};
    const nodes = matter.nodes || [];
    const thisUnstable =
      (node.recent_unavailable_count || 0) || (node.recent_recovered_count || 0);
    const otherUnstable = nodes.filter(
      (n) =>
        n.subject_id !== node.subject_id &&
        ((n.recent_unavailable_count || 0) || (n.recent_recovered_count || 0))
    );
    const infraEvents = events.filter((e) =>
      ["matter_server.disconnected", "otbr.unreachable", "thread_network.lost"].includes(
        e.event_type
      )
    );
    const nodeEvents = events.filter((e) => e.subject_id === node.subject_id);
    if (!nodeEvents.length && !thisUnstable) {
      return "There is not enough recent event history to classify this as device-local or network-wide.";
    }
    if (otherUnstable.length) {
      return "Multiple Matter nodes changed state around the same time. This may indicate a wider Matter/Thread network issue.";
    }
    if (infraEvents.length) {
      return "Infrastructure events were observed near this node change. Review OTBR, Matter server, mDNS, and TREL sections.";
    }
    if (thisUnstable) {
      return "This looks isolated to this node. ThreadLens does not see a wider Matter/Thread infrastructure issue at the same time.";
    }
    return "There is not enough recent event history to classify this as device-local or network-wide.";
  }

  _overallCard(tl) {
    return `
      <div class="tl-card">
        <div class="tl-overall">
          <div>
            <div class="tl-label">Overall health</div>
            ${badge(tl.overall_health)}
          </div>
          <div>
            <div class="tl-label">Environment</div>
            ${badge(tl.environment_health)}
          </div>
        </div>
      </div>`;
  }

  _summaryCards(d) {
    const matter = d.matter || {};
    const mdns = d.mdns || {};
    const trel = d.trel || {};
    const mqtt = d.mqtt;
    const cards = [
      { label: "OTBRs", value: (d.otbrs || []).length, sub: "" },
      { label: "Thread networks", value: (d.networks || []).length, sub: "" },
      {
        label: "Matter nodes",
        value: matter.node_count || 0,
        sub: matter.unavailable_count ? `${matter.unavailable_count} unavailable` : "",
      },
      { label: "mDNS services", value: mdns.service_count || 0, sub: "" },
      {
        label: "TREL services",
        value: trel.service_count || 0,
        sub: trel.foreign_service_count ? `${trel.foreign_service_count} foreign` : "",
      },
      {
        label: "MQTT publishing",
        value: mqtt ? boolText(mqtt.connected, "On", "Off") : "—",
        sub: mqtt && mqtt.homeassistant_discovery_enabled ? "Discovery on" : "",
      },
    ];
    const inner = cards
      .map(
        (c) => `
        <div class="tl-summary">
          <div class="tl-summary-value">${esc(c.value)}</div>
          <div class="tl-summary-label">${esc(c.label)}</div>
          ${c.sub ? `<div class="tl-muted tl-summary-sub">${esc(c.sub)}</div>` : ""}
        </div>`
      )
      .join("");
    return `<div class="tl-summary-grid">${inner}</div>`;
  }

  _otbrSection(otbrs) {
    if (!otbrs.length) {
      return `<div class="tl-card"><h2>OTBRs</h2><p class="tl-muted">No OTBRs reported.</p></div>`;
    }
    const items = otbrs
      .map((o) => {
        const displayHealth = o.display_health || o.health;
        const effectiveState = o.effective_state || o.role || o.thread_state || "—";
        const sourceLabel = o.state_source_label || o.thread_state_source || "—";
        const mismatchDetails =
          o.rest_endpoint_mismatch && o.mismatch_detail
            ? `<details class="tl-details tl-advanced">
                <summary>Endpoint details</summary>
                <p class="tl-info-text">${esc(o.mismatch_detail)}</p>
                <div class="tl-kv tl-kv-compact">
                  <span>JSON:API state</span><span>${esc(o.json_api_thread_state || "—")}</span>
                  <span>/node state</span><span>${esc(o.legacy_node_thread_state || "—")}</span>
                </div>
              </details>`
            : "";
        const prominentWarn =
          o.rest_endpoint_mismatch && !o.mismatch_reconciled
            ? `<div class="tl-inline-warn">OTBR REST endpoints disagree and ThreadLens could not reconcile an active state.</div>`
            : "";
        return `
        <div class="tl-subcard">
          <div class="tl-subcard-head">
            <strong>${esc(o.name || o.id)}</strong>
            ${badge(displayHealth)}
          </div>
          <div class="tl-kv">
            <span>Reachable</span><span>${boolText(o.reachable, "Yes", "No")}</span>
            <span>Effective state</span><span>${esc(effectiveState)}</span>
            <span>Role</span><span>${esc(o.role || "—")}</span>
            <span>Source</span><span>${esc(sourceLabel)}</span>
            <span>Network</span><span>${esc(o.network_name || "—")}</span>
            <span>Extended PAN ID</span><span>${esc(o.extended_pan_id || "—")}</span>
            <span>RLOC16</span><span>${esc(o.rloc16 || "—")}</span>
          </div>
          ${prominentWarn}
          ${mismatchDetails}
        </div>`;
      })
      .join("");
    return `<div class="tl-card"><h2>OTBRs</h2>${items}</div>`;
  }

  _networksSection(networks) {
    if (!networks.length) {
      return `<div class="tl-card"><h2>Thread networks</h2><p class="tl-muted">No Thread networks reported.</p></div>`;
    }
    const items = networks
      .map(
        (n) => `
        <div class="tl-subcard">
          <div class="tl-subcard-head">
            <strong>${esc(n.name || n.extended_pan_id || "Thread network")}</strong>
            ${badge(n.health)}
          </div>
          <div class="tl-kv">
            <span>Extended PAN ID</span><span>${esc(n.extended_pan_id || "—")}</span>
            <span>Channel</span><span>${esc(n.channel ?? "—")}</span>
            <span>PAN ID</span><span>${esc(n.pan_id || "—")}</span>
            <span>Classification</span><span>${esc(n.classification || "—")}</span>
            <span>Border routers</span><span>${esc(n.border_router_count ?? "—")}</span>
          </div>
        </div>`
      )
      .join("");
    return `<div class="tl-card"><h2>Thread networks</h2>${items}</div>`;
  }

  _matterSection(matter) {
    return `
      <div class="tl-card">
        <h2>Matter servers ${badge(matter.health)}</h2>
        <div class="tl-kv">
          <span>Servers connected</span><span>${esc(matter.servers_connected || 0)} / ${esc(matter.servers || 0)}</span>
          <span>Total nodes</span><span>${esc(matter.node_count || 0)}</span>
          <span>Unavailable nodes</span><span>${esc(matter.unavailable_count || 0)}</span>
          <span>Recent down / up (24h)</span><span>${esc(matter.recent_unavailable_count || 0)} / ${esc(matter.recent_recovered_count || 0)}</span>
        </div>
      </div>`;
  }

  _mdnsTrelSection(mdns, trel) {
    const types = (mdns.top_service_types || [])
      .map((t) => `<span class="tl-chip">${esc(t.service_type)} (${esc(t.count)})</span>`)
      .join("");
    const trelInfo = trel.info || {};
    const foreignMessage =
      trelInfo.message ||
      "Other Thread/TREL services are visible on the LAN. This is common when HomePods, Apple TVs, Nest devices, or other Thread fabrics are present. ThreadLens does not treat this as a fault by itself.";
    const foreignNote =
      trel.foreign_service_count && trel.informational
        ? `<div class="tl-info-banner">
            <strong>Other Thread/TREL services visible: ${esc(trel.foreign_service_count)}</strong>
            <p class="tl-info-text">${esc(foreignMessage)}</p>
          </div>`
        : "";
    const rawHealthLine =
      trel.health_raw && trel.health_raw !== trel.health
        ? `<span>TREL raw health</span><span>${badge(trel.health_raw)}</span>`
        : "";
    return `
      <div class="tl-card">
        <h2>mDNS / TREL</h2>
        <div class="tl-kv">
          <span>mDNS health</span><span>${badge(mdns.health)}</span>
          <span>mDNS services</span><span>${esc(mdns.service_count || 0)}</span>
          <span>Observation degraded</span><span>${boolText(mdns.observation_degraded, "Yes", "No")}</span>
          <span>TREL health</span><span>${badge(trel.health)}</span>
          ${rawHealthLine}
          <span>TREL services</span><span>${esc(trel.service_count || 0)}</span>
          <span>Foreign TREL</span><span>${esc(trel.foreign_service_count || 0)}</span>
        </div>
        ${foreignNote}
        ${types ? `<div class="tl-chips">${types}</div>` : ""}
        <p class="tl-muted tl-note">TREL visibility is observation only and does not imply device parentage.</p>
      </div>`;
  }

  _mqttSection(mqtt) {
    if (!mqtt) {
      return `<div class="tl-card"><h2>MQTT</h2><p class="tl-muted">MQTT publishing is not configured.</p></div>`;
    }
    return `
      <div class="tl-card">
        <h2>MQTT</h2>
        <div class="tl-kv">
          <span>Enabled</span><span>${boolText(mqtt.enabled, "Yes", "No")}</span>
          <span>Connected</span><span>${boolText(mqtt.connected, "Yes", "No")}</span>
          <span>HA Discovery</span><span>${boolText(mqtt.homeassistant_discovery_enabled, "Enabled", "Disabled")}</span>
          <span>Last publish</span><span>${esc(fmtTime(mqtt.last_publish_at))}</span>
          <span>Last error</span><span>${esc(mqtt.last_error || "—")}</span>
        </div>
      </div>`;
  }

  _reportSection(report) {
    const yamlUrl = report.report_url || "api/v1/report.yaml";
    const jsonUrl = report.report_url_json || "api/v1/report.json";
    const generated = report.last_generated_at || "never";
    const yamlHref = esc(apiUrl(yamlUrl));
    const jsonHref = esc(apiUrl(jsonUrl));
    return `
      <div class="tl-card">
        <h2>Report</h2>
        <p class="tl-muted">Last generated: ${esc(generated)}</p>
        <div class="tl-btn-row">
          <a class="tl-btn" href="${yamlHref}" target="_blank" rel="noopener">Open report YAML</a>
          <a class="tl-btn tl-btn-secondary" href="${jsonHref}" target="_blank" rel="noopener">Open report JSON</a>
          <button id="tl-copy-report" class="tl-btn tl-btn-secondary" data-url="${esc(yamlUrl)}">Copy YAML path</button>
        </div>
        <p class="tl-muted tl-note">Opens the report in a new tab directly from ThreadLens Core. Reports redact secrets but include operational metadata.</p>
      </div>`;
  }

  _diagnosticsSection(d) {
    const blocks = [
      ["Overall", d.threadlens],
      ["Incident", d.incident],
      ["Matter", d.matter],
      ["mDNS", d.mdns],
      ["TREL", d.trel],
      ["OTBRs", d.otbrs],
      ["Networks", d.networks],
      ["Events", d.events],
      ["MQTT", d.mqtt],
    ]
      .map(
        ([label, value]) =>
          `<details class="tl-details"><summary>${esc(label)}</summary><pre>${esc(
            JSON.stringify(value, null, 2)
          )}</pre></details>`
      )
      .join("");
    return `<div class="tl-card"><h2>Diagnostics</h2>${blocks}</div>`;
  }
}

function bootstrap() {
  const root = document.getElementById("tl-app");
  if (!root) return;
  const dashboard = new ThreadLensDashboard(root);
  dashboard.start();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", bootstrap);
} else {
  bootstrap();
}
