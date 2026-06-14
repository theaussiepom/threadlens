# THREADLENS_IMPLEMENTATION_PLAN.md

# ThreadLens Implementation Plan

## 0. Purpose of this document

This document is the implementation source of truth for **ThreadLens**.

Cursor/Opus must read this document fully before writing code. The implementation must follow this architecture and must not improvise major product boundaries without stopping and asking for review.

ThreadLens is not a quick script. It is a complete v1 architecture for a read-only Thread and Matter-over-Thread observability suite, designed for Home Assistant environments but not hard-coupled to Home Assistant Core.

---

## 1. Product name and repositories

### Product name

**ThreadLens**

ThreadLens is a diagnostic and observability tool for Thread, OpenThread Border Routers, TREL, mDNS/DNS-SD, Matter Server, and Matter-over-Thread node health.

It helps users see what is happening in their Thread/Matter environment and export structured diagnostic reports for vendors, GitHub issues, human review, or AI-assisted investigation.

### Repositories

Create/use these repositories under `theaussiepom`:

* `theaussiepom/threadlens`
* `theaussiepom/threadlens-ha-addon`
* `theaussiepom/threadlens-ha-integration`

### Repository responsibilities

#### `theaussiepom/threadlens`

Core service and source of truth.

Contains:

* Python/FastAPI application
* ThreadLens server mode
* ThreadLens agent mode
* both mode
* OTBR REST collectors
* mDNS/DNS-SD observers
* Matter Server websocket observer
* event/state/aggregate storage
* health model
* MQTT Discovery publisher
* report API
* YAML/JSON report generation
* Dockerfile
* docker-compose examples
* docs
* tests

Container image:

* `ghcr.io/theaussiepom/threadlens`

#### `theaussiepom/threadlens-ha-addon`

Home Assistant OS add-on packaging.

Contains:

* add-on repository metadata
* add-on config
* add-on Docker wrapper if needed
* docs for HAOS users

The add-on must use the same core ThreadLens image/application.

The HAOS add-on should run ThreadLens in `both` mode by default where appropriate.

#### `theaussiepom/threadlens-ha-integration`

HACS dashboard/frontend integration.

This repo is for Home Assistant polish only.

Contains:

* `custom_components/threadlens`
* config flow for ThreadLens API URL
* frontend/dashboard helpers/cards where appropriate
* services/buttons for report generation
* diagnostics panel helpers

The HACS integration must not contain backend collector logic.

It talks to ThreadLens Core via API and/or reads the MQTT Discovery entities already published by ThreadLens.

---

## 2. Product intent

ThreadLens is a **read-only observability suite**.

It should help answer:

* What Thread networks are visible?
* What OTBRs are present and healthy?
* Are the OTBRs on the same Thread dataset?
* What Extended PAN IDs, PAN IDs, and channels are visible?
* Are other Thread networks visible on the same infrastructure network?
* Are TREL advertisements appearing/disappearing?
* Are Matter nodes flapping?
* Which Matter nodes are unhealthy?
* What data source supports each metric?
* What is not observable with the current setup?
* Can I export a structured report for support/vendor/AI analysis?

ThreadLens must be honest about uncertainty.

It must distinguish:

* observed zero events

from:

* metric is not observable from current data sources

Example:

```
subscription_flaps_24h: null
subscription_diagnostics_available: false
```

is not the same as:

```
subscription_flaps_24h: 0
subscription_diagnostics_available: true
```

---

## 3. Non-goals

ThreadLens v1 must not:

* control Thread devices
* commission Matter devices
* restart OTBRs
* modify Thread datasets
* modify Matter fabrics
* modify firewall rules
* scrape over SSH
* use Docker socket access
* require log parsing
* act as a Matter controller
* replace Home Assistant Matter Server
* make AI-style causal claims
* expose Thread network keys, PSKc, Matter secrets, Wi-Fi secrets, HA tokens, or other credentials

ThreadLens may correlate events, but must not overclaim causation.

Good:

```
Matter node availability flap occurred within 60 seconds of TREL advertisement change.
```

Bad:

```
TREL change caused the blind failure.
```

---

## 4. Runtime modes

ThreadLens uses **one image** with multiple modes.

```
threadlens --mode server
threadlens --mode agent
threadlens --mode both
```

Mode may also be set by config/env.

### Server mode

Central service.

Responsibilities:

* load configuration
* observe mDNS/DNS-SD
* collect OTBR REST data
* consume optional ThreadLens agent APIs
* connect to Matter Server websocket/API
* maintain current state
* store event history and aggregates in SQLite
* calculate health states
* publish MQTT Discovery devices/entities
* expose REST/report API
* generate YAML/JSON reports

### Agent mode

Optional co-located local diagnostics agent.

Responsibilities:

* run beside OTBR or Matter-related services
* expose a read-only HTTP API
* provide local host/service diagnostics when available
* no SSH
* no Docker socket
* no mutation

Agent is optional in v1. ThreadLens must work without agents, with reduced capability.

### Both mode

Runs server and local agent together.

Useful for:

* HAOS add-on
* single-host installs
* small Docker deployments

---

## 5. Default ports and names

Use these defaults:

* Product: `ThreadLens`
* Service name: `threadlens`
* Container name: `threadlens`
* Image: `ghcr.io/theaussiepom/threadlens`
* Server HTTP port: `8128`
* Agent HTTP port: `8129`
* MQTT discovery prefix: `homeassistant`
* MQTT topic prefix: `threadlens`

No authentication is required for v1.

ThreadLens must document that it is intended for trusted local networks only and must not be exposed publicly without a reverse proxy or network-level protection.

---

## 6. Core architecture

### High-level architecture

```
ThreadLens Server
├─ Config loader
├─ OTBR REST collector
├─ Optional ThreadLens agent client
├─ mDNS/DNS-SD observer
├─ Matter Server websocket observer
├─ Event normaliser
├─ Current state store
├─ Event store
├─ Aggregate store
├─ Health engine
├─ MQTT Discovery publisher
├─ Report generator
└─ REST API
```

### Data flow

```
OTBR REST / Agent / mDNS / Matter websocket
  ↓
raw observation
  ↓
normalised state/event
  ↓
SQLite current state + events + aggregates
  ↓
health model
  ↓
MQTT Discovery + API + report export
```

---

## 7. Data source philosophy

ThreadLens must prefer structured/stateful data over log scraping.

### Primary data sources

* OTBR REST JSON:API
* mDNS/DNS-SD observation
* Matter Server websocket/API
* ThreadLens agent HTTP API, where configured

### Optional future/enrichment sources

* mounted log files as redacted evidence only
* future OTBR REST enhancements for TREL peer/counter data
* future Matter Server structured diagnostics events
* future RF sniffer module

Logs are not required for v1.

Do not implement SSH.

Do not implement Docker socket support.

---

## 8. OTBR data collection

### Primary source: OTBR REST

OTBR REST is the primary Thread diagnostics source.

Configuration example:

```
otbrs:
  - id: study
    name: Study OTBR
    rest_url: "http://192.168.100.4:8081"

  - id: lounge
    name: Lounge OTBR
    rest_url: "http://192.168.100.7:8081"
```

ThreadLens should collect what OTBR REST exposes, including where available:

* OTBR reachability
* Thread network name
* PAN ID
* Extended PAN ID
* channel
* node role
* RLOC16
* leader data
* device inventory
* Thread device roles
* Thread device extended addresses
* topology/diagnostic data
* child/router/neighbour information if available
* Thread network diagnostic TLVs if available
* MAC counters / MLE counters if available

### OTBR REST action policy (v1)

For v1, prefer GET endpoints first.

**Allowed GET endpoints:**

* `GET /api/node`
* `GET /api/devices`
* safe dataset/read-only diagnostic GET endpoints exposed by OTBR REST (e.g. `GET /node/dataset/active`)

**Allowed POST actions only if clearly read-only and implemented carefully:**

* `POST /api/actions` for read-only diagnostic collection tasks such as `getNetworkDiagnosticTask` or `updateDeviceCollectionTask`, if required by the current OTBR REST API

**Forbidden:**

* dataset changes (`PUT`/`POST` on `/node/dataset/*`)
* joiner/commissioner actions
* reset operations
* counter reset tasks (e.g. `resetNetworkDiagCounterTask`)
* any action that mutates Thread network state

ThreadLens must implement an explicit allowlist/blocklist in code. Unknown OTBR actions must be treated as unsupported.

### Capability-based design

OTBR REST coverage may vary by version/configuration.

ThreadLens must track capabilities per OTBR.

Example:

```
capabilities:
  otbr_rest: true
  thread_dataset: true
  network_diagnostics: true
  topology: true
  trel_internal_peer_table: false
  trel_internal_counters: false
```

Missing capability must be reported as unavailable, not zero.

---

## 9. TREL observation

ThreadLens v1 supports TREL at two levels.

### Level 1: mDNS/DNS-SD TREL advertisement observation

This is v1 core functionality.

ThreadLens Server must observe `_trel._udp` services on the infrastructure network using mDNS/DNS-SD.

It should track:

* TREL service instance name
* hostname
* IP address
* port
* TXT records
* Extended PAN ID if advertised
* first seen
* last seen
* currently visible
* add/remove/change events
* service flap counts
* foreign Extended PAN IDs

This does not require OTBR internal access.

This metric should be named carefully:

* TREL mDNS visibility
* TREL service flapping
* Foreign TREL advertisements

Do not call this "OTBR internal TREL peer flapping".

### Level 2: OTBR internal TREL peer/counter state

Current OTBR REST may not expose internal TREL peer tables/counters.

ThreadLens must not assume this is available.

Fields should exist but be capability-aware:

```
trel:
  mdns_observation:
    available: true
    services_seen: 4
    service_flaps_24h: 7

  otbr_internal:
    peer_table_available: false
    counters_available: false
    reason: "OTBR source does not expose internal TREL peers/counters"
```

Future support may come from:

* OTBR REST enhancement
* ThreadLens agent enhancement

---

## 10. mDNS/DNS-SD observation

ThreadLens Server must observe relevant services:

* `_trel._udp.local.`
* `_meshcop._udp.local.`
* `_matter._tcp.local.`
* `_matterc._udp.local.` where visible/relevant

It should track:

* service type
* service instance
* hostname
* addresses
* port
* TXT records
* first seen
* last seen
* currently visible
* add/remove/change counts
* flap counts

mDNS observations indicate services visible on the infrastructure network.

They do not prove that a Matter/Thread device is using a specific border router.

Reports must use careful wording.

Good:

```
Foreign Thread/TREL service visible on the infrastructure network.
```

Bad:

```
HomePod is parenting this blind.
```

### mDNS networking requirements

mDNS/DNS-SD observation requires multicast visibility on the infrastructure network.

* Docker bridge networking may provide degraded or no mDNS visibility.
* For reliable `_trel._udp`, `_meshcop._udp`, and Matter service observation, recommend host networking, macvlan, ipvlan, or equivalent multicast-capable networking.
* The HAOS add-on should use host networking where possible.
* ThreadLens must expose `mdns_observation_degraded: true` when it cannot confirm multicast visibility.

---

## 11. Matter Server observation

### Primary source: Matter Server websocket/API

Matter Servers are configured.

Example:

```
matter_servers:
  - id: study_matter
    name: Study Matter Server
    websocket_url: "ws://192.168.100.4:5580/ws"
    variant: python
```

**Matter Server variant (v1):**

* v1 target is `python-matter-server`.
* Allowed `variant` values initially: `python`, `unknown`.
* Matter.js support is future/experimental unless its websocket event model is validated.
* Do not claim full matter.js compatibility in v1.

ThreadLens must connect as a read-only observer (passive websocket client; only `start_listening`, `get_nodes`, and similar non-mutating commands).

It should collect where available:

* server connected/disconnected
* Matter nodes
* node IDs
* node availability
* node metadata
* vendor/product
* serial number
* software version / firmware version
* endpoint/cluster metadata where available
* attribute update events where available
* node added/removed/updated events
* commissioning lifecycle where available

### Current limitation: subscription diagnostics

Current public Matter Server websocket events may not expose true subscription lifecycle diagnostics.

ThreadLens must support the data model for subscription diagnostics, but mark these fields unavailable unless structured events exist.

Example:

```
matter_node:
  node_id: 24
  friendly_name: Living Blind 3
  availability_flaps_24h: 4
  subscription_flaps_24h: null
  subscription_diagnostics_available: false
```

Do not infer subscription flaps from availability flaps.

Availability flapping and subscription flapping are related but distinct.

---

## 12. Future Matter Server diagnostics enhancement

ThreadLens should include a vision/design note for a future Matter Server diagnostics enhancement.

Do not implement a PR in v1.

Do not block ThreadLens on this.

ThreadLens should be ready to consume future structured diagnostic events over the Matter Server websocket.

Desired future event families:

* `diagnostic.subscription.*`
* `diagnostic.session.*`
* `diagnostic.command.*`
* `diagnostic.commissioning.*`
* `diagnostic.node.*`
* `diagnostic.fabric.*`
* `diagnostic.attribute.*`

Desired subscription events:

* `diagnostic.subscription.established`
* `diagnostic.subscription.lost`
* `diagnostic.subscription.resubscribe_attempted`
* `diagnostic.subscription.resubscribe_succeeded`
* `diagnostic.subscription.failed`
* `diagnostic.subscription.abandoned`

Desired CASE/session events:

* `diagnostic.session.case_established`
* `diagnostic.session.case_failed`
* `diagnostic.session.case_expired`

Desired command events:

* `diagnostic.command.started`
* `diagnostic.command.succeeded`
* `diagnostic.command.failed`
* `diagnostic.command.timed_out`

Example future event payload:

```
{
  "event_type": "diagnostic.subscription.failed",
  "schema_version": 1,
  "timestamp": "2026-06-12T10:41:22Z",
  "node_id": 24,
  "endpoint_id": 1,
  "cluster_id": 258,
  "cluster_name": "WindowCovering",
  "attempt": 3,
  "error_code": "CHIP_ERROR_TIMEOUT",
  "retryable": true,
  "next_retry_ms": 30000,
  "marked_node_unavailable": false
}
```

ThreadLens must be architected so it can consume these events later without redesigning the data model.

---

## 13. Matter node health

ThreadLens should dynamically create/track Matter node records.

For each node:

* node ID
* friendly name
* server ID
* vendor
* product
* serial
* firmware/software version
* availability
* last seen
* last unavailable
* availability flaps
* command failure metrics if observable
* subscription metrics if observable
* CASE/session metrics if observable
* health state
* capabilities

### Friendly name mapping

Priority order:

1. Home Assistant entity/device friendly name if available later
2. Matter node label/name
3. serial number
4. node ID

Do not require Home Assistant API for v1.

Matter Server metadata is enough to create nodes.

### Health states

Use simple states:

* healthy
* warning
* degraded
* critical
* unknown

Health must be explainable via attributes/report fields.

Example:

```
health: degraded
health_reasons:
  - availability_flaps_24h_above_threshold
```

No AI diagnosis.

---

## 14. Event model

ThreadLens stores meaningful events, not every polling snapshot.

### Event principles

Store:

* state transitions
* service add/remove/change
* health state changes
* capability changes
* node availability changes
* OTBR reachability changes
* OTBR role changes
* Thread network appeared/disappeared
* TREL service appeared/disappeared
* Matter Server connected/disconnected

Do not store:

* every unchanged poll result
* raw full snapshots every interval
* every Matter attribute update

**Matter event filtering (v1):**

Persist only:

* node added
* node removed
* availability changed
* health changed
* server connected/disconnected
* meaningful capability/state changes

Attribute-only updates may update current state where useful but must not become high-volume event history by default.

### Required event fields

```
event:
  id: string
  timestamp: datetime
  source_type: otbr | matter_server | mdns | threadlens | agent
  source_id: string
  event_type: string
  severity: info | warning | error | critical
  subject_type: thread_network | otbr | matter_server | matter_node | trel_service | mdns_service
  subject_id: string
  message: string
  data: object
```

### Event type examples

* `otbr.reachable`
* `otbr.unreachable`
* `otbr.role_changed`
* `otbr.dataset_changed`
* `thread_network.seen`
* `thread_network.lost`
* `mdns.service_added`
* `mdns.service_removed`
* `mdns.service_changed`
* `trel.service_added`
* `trel.service_removed`
* `trel.service_changed`
* `matter_server.connected`
* `matter_server.disconnected`
* `matter_node.available`
* `matter_node.unavailable`
* `matter_node.recovered`
* `matter_node.health_changed`
* `threadlens.capability_changed`

---

## 15. Storage

Use SQLite with `aiosqlite` and repository-style modules for v1.

Do not introduce SQLAlchemy unless there is a strong reason later.

Store:

* current state
* event history
* aggregate counters
* report metadata

### Retention

Default event retention:

* 30 days

### Aggregation

Aggregate where possible.

Store meaningful event records for the retention window.

Use hourly/daily aggregates for counts:

* availability flaps per node per hour/day
* mDNS service flaps per service per hour/day
* TREL service flaps per service per hour/day
* OTBR role changes per OTBR per hour/day
* Matter server disconnects per server per hour/day

Avoid storing large raw snapshots unless required for current state/report.

### SQLite paths

Default:

* `/config/config.yaml`
* `/data/threadlens.db`

Docker volumes:

* `/config`
* `/data`

---

## 16. Health model

ThreadLens is not AI.

It calculates factual status from thresholds and capabilities.

### Primary Thread network classification

* If configured OTBRs report the same active Extended PAN ID, that network is classified as `primary`.
* If multiple configured OTBRs disagree, primary is `unknown` and environment health should be `warning` or `degraded` depending on severity.
* Any other observed Extended PAN ID from mDNS/TREL/MeshCoP is classified as `observed_other`.
* Do not call other networks "competing" in API/report output. Use `observed_other` or `foreign` where technically appropriate.

### Flap semantics

A flap is a visibility/availability state transition after debounce.

**Defaults:**

* Debounce window: 30 seconds
* Availability flap: `available -> unavailable -> available`, or the reverse, after debounce
* mDNS/TREL service flap: service add/remove/change after debounce
* Rolling windows: 1h and 24h
* Store meaningful transition events, not every poll

**Default thresholds (constants or config-ready; hardcoded defaults acceptable for v1):**

Matter node availability flaps:

* warning: 3 in 24h
* degraded: 6 in 24h
* critical: unavailable for more than 30 minutes

OTBR role changes:

* warning: 2 in 1h
* degraded: 5 in 1h

TREL/mDNS service flaps:

* warning: 5 in 1h
* degraded: 15 in 1h

### Environment health

Inputs:

* primary Thread network known
* OTBR reachability
* number of observed Thread networks
* foreign TREL services visible
* mDNS flapping
* Matter Server availability
* Matter node availability counts

### OTBR health

Inputs:

* REST reachable
* dataset known
* role known
* role changes
* diagnostic capabilities

### Matter Server health

Inputs:

* websocket connected
* node count
* unavailable node count
* connection flaps

### Matter Node health

Inputs:

* availability
* availability flaps
* last seen
* observable command/session/subscription diagnostics
* capabilities

### No causal claims

ThreadLens may expose nearby/correlated events but must not claim root cause.

Reports may include:

```
nearby_events:
  - event_type: trel.service_removed
    seconds_before: 42
```

But not:

```
cause: trel.service_removed
```

---

## 17. Capabilities model

Capabilities must be first-class.

Every source and report must show what is observable.

Example:

```
capabilities:
  otbr:
    rest_available: true
    network_dataset_available: true
    topology_available: true
    trel_mdns_available: true
    trel_internal_peer_table_available: false
    trel_internal_counters_available: false

  matter_server:
    websocket_available: true
    node_availability_available: true
    subscription_diagnostics_available: false
    case_diagnostics_available: false
    command_diagnostics_available: false

  mdns:
    mdns_observation_degraded: false
```

ThreadLens must set `mdns_observation_degraded: true` when it cannot confirm multicast visibility.

Metrics that are not observable must be `null` or marked unavailable, not `0`.

---

## 18. Configuration schema

Use YAML config.

Environment variables may override key values.

Default config path:

* `/config/config.yaml`

Example full config:

```
site:
  name: "Home"

mode: server

server:
  host: "0.0.0.0"
  port: 8128

agent:
  host: "0.0.0.0"
  port: 8129

storage:
  sqlite_path: "/data/threadlens.db"
  event_retention_days: 30

mqtt:
  enabled: true
  host: "mqtt"
  port: 1883
  username: null
  password: null
  discovery_prefix: "homeassistant"
  topic_prefix: "threadlens"
  retain_discovery: true
  retain_state: true
  entities:
    environment: true
    otbr: true
    matter_server: true
    matter_node: true
    trel_service: false

mdns:
  enabled: true
  services:
    - "_trel._udp.local."
    - "_meshcop._udp.local."
    - "_matter._tcp.local."
    - "_matterc._udp.local."

otbrs:
  - id: "study"
    name: "Study OTBR"
    rest_url: "http://192.168.100.4:8081"
    agent_url: null

  - id: "lounge"
    name: "Lounge OTBR"
    rest_url: "http://192.168.100.7:8081"
    agent_url: null

matter_servers:
  - id: "study_matter"
    name: "Study Matter Server"
    websocket_url: "ws://192.168.100.4:5580/ws"
    variant: python

reports:
  redact_secrets: true
```

### Mode-specific behaviour

#### server

Runs:

* server API
* collectors
* observers
* MQTT publisher
* report generator

#### agent

Runs:

* agent API only

#### both

Runs:

* server API
* agent API
* collectors
* observers
* MQTT publisher
* report generator

---

## 19. REST API

Server API base:

* `http://<host>:8128/api/v1`

No auth in v1.

### Required endpoints

* `GET /api/v1/health`
* `GET /api/v1/status`
* `GET /api/v1/capabilities`
* `GET /api/v1/state`
* `GET /api/v1/events`
* `GET /api/v1/networks`
* `GET /api/v1/otbrs`
* `GET /api/v1/matter-servers`
* `GET /api/v1/matter-nodes`
* `GET /api/v1/mdns/services`
* `GET /api/v1/trel/services`
* `GET /api/v1/report`
* `GET /api/v1/report.yaml`
* `GET /api/v1/report.json`

### Report content negotiation

These should all work:

```
GET /api/v1/report
Accept: application/yaml

GET /api/v1/report
Accept: application/json

GET /api/v1/report.yaml

GET /api/v1/report.json
```

### Report query params

Support:

* `window=24h`
* `window=7d`
* `focus_node=<node_id>`
* `focus_device=<friendly_name>`

Report always includes everything relevant, no profiles.

### Minimal landing page

Add a tiny root page:

* `GET /`

It should show:

* ThreadLens is running.
* Links:

  * `/api/v1/health`
  * `/api/v1/report.yaml`
  * `/api/v1/report.json`

No full dashboard in core v1.

The HACS repo owns the dashboard.

---

## 20. Agent API

Agent API base:

* `http://<host>:8129/api/v1/agent`

The agent is optional.

Agent v1 may be minimal.

Required endpoints:

* `GET /api/v1/agent/health`
* `GET /api/v1/agent/status`
* `GET /api/v1/agent/capabilities`

Optional/future endpoints:

* `GET /api/v1/agent/otbr`
* `GET /api/v1/agent/otbr/topology`
* `GET /api/v1/agent/otbr/trel`
* `GET /api/v1/agent/logs/evidence`

In v1, do not implement SSH or Docker socket.

If local deep diagnostics are not implemented, capabilities must say unavailable.

---

## 21. MQTT Discovery

MQTT Discovery is the baseline Home Assistant integration.

ThreadLens must dynamically create Home Assistant devices/entities.

### Entity defaults (v1)

* environment entities: enabled
* OTBR entities: enabled
* Matter Server entities: enabled
* Matter Node entities: enabled
* per-TREL-service entities: disabled by default
* detailed/raw information should be attributes or API/report data, not hundreds of HA entities

### Devices to create

#### ThreadLens Diagnostics

Overall product status.

Entities:

* `sensor.threadlens_health`
* `sensor.threadlens_report_url`
* `sensor.threadlens_last_report_generated_at`
* `sensor.threadlens_event_count_24h`
* `sensor.threadlens_warning_count_24h`

#### Thread Environment Health

Entities:

* `sensor.threadlens_environment_health`
* `sensor.threadlens_thread_network_count`
* `sensor.threadlens_foreign_network_count`
* `sensor.threadlens_trel_service_count`
* `sensor.threadlens_foreign_trel_service_count`
* `sensor.threadlens_matter_node_count`
* `sensor.threadlens_unavailable_matter_node_count`

Use attributes heavily for detail.

#### Thread Network - per observed Extended PAN ID

Example device:

* `Thread Network - d6f401f0227e1ec0`

Entities:

* `sensor.threadlens_network_<id>_name`
* `sensor.threadlens_network_<id>_channel`
* `sensor.threadlens_network_<id>_border_router_count`
* `sensor.threadlens_network_<id>_last_seen`
* `binary_sensor.threadlens_network_<id>_visible`
* `binary_sensor.threadlens_network_<id>_foreign`

#### OTBR - per configured OTBR

Entities:

* `sensor.threadlens_otbr_<id>_health`
* `sensor.threadlens_otbr_<id>_role`
* `sensor.threadlens_otbr_<id>_network_name`
* `sensor.threadlens_otbr_<id>_channel`
* `sensor.threadlens_otbr_<id>_ext_pan_id`
* `binary_sensor.threadlens_otbr_<id>_reachable`

Detailed data should be attributes.

#### Matter Server - per configured server

Entities:

* `sensor.threadlens_matter_server_<id>_health`
* `sensor.threadlens_matter_server_<id>_node_count`
* `sensor.threadlens_matter_server_<id>_unavailable_node_count`
* `binary_sensor.threadlens_matter_server_<id>_connected`

#### Matter Node - per discovered node

Entities:

* `sensor.threadlens_matter_node_<id>_health`
* `binary_sensor.threadlens_matter_node_<id>_available`
* `binary_sensor.threadlens_matter_node_<id>_flapping`
* `sensor.threadlens_matter_node_<id>_availability_flaps_24h`
* `sensor.threadlens_matter_node_<id>_last_seen`

Attributes:

```
node_id: 24
vendor: Dendo
product: SCM Matter Blind
serial: SCM-MT-...
firmware: ...
subscription_diagnostics_available: false
subscription_flaps_24h: null
case_diagnostics_available: false
case_failures_24h: null
```

#### TREL service - optional per service

Create only if useful and not too noisy.

Prefer aggregate environment sensors first.

Per-service devices can be disabled by default or represented as attributes.

### Attribute strategy

Use attributes to avoid entity spam.

A small number of headline entities is better than hundreds of tiny sensors.

Raw JSON blobs should be available through API/report, not as HA sensors by default.

---

## 22. Report generation

ThreadLens reports are structured, redacted, and designed for ingestion.

No report profiles in v1.

One comprehensive report.

Formats:

* YAML
* JSON

Same report model, different serialization.

### Report principles

Report must include:

* generated timestamp
* ThreadLens version
* site name
* data source capabilities
* current state
* observed Thread networks
* configured OTBRs
* observed mDNS/TREL services
* Matter servers
* Matter nodes
* health summary
* event aggregates
* recent relevant events
* redaction summary

Report must not include:

* Thread network key
* PSKc
* Matter fabric secrets
* Wi-Fi credentials
* Home Assistant tokens
* API tokens

### Example report shape

```
report:
  generated_at: "2026-06-12T10:15:00+10:00"
  tool: "ThreadLens"
  version: "0.1.0"
  window: "24h"

site:
  name: "Home"

summary:
  health: "warning"
  thread_networks_seen: 2
  foreign_thread_networks_seen: 1
  otbrs_configured: 2
  matter_servers_configured: 1
  matter_nodes_seen: 12
  unavailable_matter_nodes: 1

capabilities:
  trel_mdns_observation: true
  otbr_internal_trel_peer_table: false
  otbr_internal_trel_counters: false
  matter_node_availability: true
  matter_subscription_diagnostics: false
  matter_case_diagnostics: false

thread_networks:
  - ext_pan_id: "d6f401f0227e1ec0"
    name: "ha-thread-7fba"
    channel: 15
    classification: "primary"
    currently_visible: true

  - ext_pan_id: "db80676015db4b6e"
    name: "MyHome22"
    channel: 25
    classification: "observed_other"
    currently_visible: true

otbrs:
  - id: "study"
    name: "Study OTBR"
    reachable: true
    role: "router"
    ext_pan_id: "d6f401f0227e1ec0"
    channel: 15
    health: "healthy"
    capabilities:
      rest: true
      internal_trel_peers: false

matter_servers:
  - id: "study_matter"
    name: "Study Matter Server"
    connected: true
    node_count: 12
    health: "warning"

matter_nodes:
  - node_id: 24
    friendly_name: "Living Blind 3"
    available: true
    health: "degraded"
    availability_flaps_24h: 4
    subscription_flaps_24h: null
    subscription_diagnostics_available: false

trel_mdns:
  services_seen: 4
  foreign_services_seen: 2
  service_flaps_24h: 7

events:
  recent:
    - timestamp: "2026-06-12T09:30:00+10:00"
      event_type: "matter_node.unavailable"
      subject_id: "matter_node:24"
      severity: "warning"
      message: "Matter node 24 became unavailable"

redaction:
  secrets_removed:
    - "Thread network key"
    - "PSKc"
    - "Matter fabric secrets"
    - "Wi-Fi credentials"
```

---

## 23. Docker packaging

Core repo must include:

* Dockerfile
* `docker-compose.example.yml`
* `.env.example`
* README.md

### Docker image

Use Python 3.12 slim base unless a better image is justified.

Container must run as non-root where practical.

Expose:

* `8128` server
* `8129` agent

Volumes:

* `/config`
* `/data`

Example compose:

```
services:
  threadlens:
    image: ghcr.io/theaussiepom/threadlens:latest
    container_name: threadlens
    restart: unless-stopped
    ports:
      - "8128:8128"
    volumes:
      - ./config:/config
      - ./data:/data
    environment:
      TZ: Australia/Brisbane
```

Docs must explain that mDNS/DNS-SD may require host networking, macvlan, or otherwise multicast-capable networking.

---

## 24. HAOS add-on

Repo:

* `theaussiepom/threadlens-ha-addon`

The add-on should wrap/use the same ThreadLens core image/application.

Default mode for HAOS:

* `both`

Add-on config should expose:

* mode
* MQTT config or use HA MQTT where possible
* OTBR REST URLs
* Matter Server websocket URLs
* site name
* retention days

No complex dashboard in add-on.

Use add-on ingress only for basic API/report page if useful.

The add-on must not fork the core logic.

---

## 25. HACS integration/dashboard

Repo:

* `theaussiepom/threadlens-ha-integration`

This is frontend/dashboard polish only.

It should not be required for ThreadLens to work.

Core ThreadLens already publishes MQTT Discovery entities.

HACS integration responsibilities:

* config flow for ThreadLens API URL
* optional detection of ThreadLens MQTT entities
* dashboard/cards
* service to generate/open report URL
* repair/dashboard hints

The HACS integration may provide:

* ThreadLens Overview
* Thread Networks
* OTBRs
* Matter Servers
* Matter Nodes
* TREL/mDNS
* Reports

No backend collectors in HACS.

---

## 26. Implementation stack

Use Python unless there is a strong reason not to.

Recommended stack:

* Python 3.12
* FastAPI
* Uvicorn
* Pydantic v2
* SQLite via aiosqlite (repository-style modules; no SQLAlchemy in v1)
* PyYAML
* zeroconf
* aiomqtt or paho-mqtt
* websockets / aiohttp
* Jinja2 only if Markdown reports are later added
* pytest
* ruff
* mypy optional

No Node.js for the backend.

---

## 27. Project structure

Suggested structure for `threadlens` repo:

```
threadlens/
├─ threadlens/
│  ├─ __init__.py
│  ├─ main.py
│  ├─ config.py
│  ├─ models/
│  │  ├─ state.py
│  │  ├─ events.py
│  │  ├─ reports.py
│  │  ├─ capabilities.py
│  │  └─ health.py
│  ├─ server/
│  │  ├─ app.py
│  │  ├─ routes.py
│  │  └─ lifecycle.py
│  ├─ agent/
│  │  ├─ app.py
│  │  └─ routes.py
│  ├─ collectors/
│  │  ├─ otbr_rest.py
│  │  ├─ matter_server.py
│  │  ├─ mdns.py
│  │  └─ agent_client.py
│  ├─ storage/
│  │  ├─ db.py
│  │  ├─ repositories.py
│  │  └─ migrations.py
│  ├─ mqtt/
│  │  ├─ client.py
│  │  ├─ discovery.py
│  │  └─ entities.py
│  ├─ health/
│  │  └─ engine.py
│  ├─ reports/
│  │  ├─ generator.py
│  │  ├─ redaction.py
│  │  └─ serializers.py
│  └─ utils/
│     ├─ time.py
│     └─ ids.py
├─ tests/
├─ docs/
├─ examples/
├─ Dockerfile
├─ docker-compose.example.yml
├─ pyproject.toml
└─ README.md
```

---

## 28. Implementation passes

Cursor/Opus must implement in controlled passes.

Do not skip passes.

After each pass, stop and summarise:

* files changed
* what works
* what is incomplete
* how to run/test
* risks/questions

### Pass 0 — Design confirmation only

Do not code.

Tasks:

* read this document
* summarise intended architecture
* identify contradictions/ambiguities
* identify external dependencies
* propose any corrections
* wait for approval

Acceptance:

* no code changes
* clear implementation summary

### Pass 1 — Repository scaffold

Implement:

* Python project scaffold
* `pyproject.toml`
* package structure
* FastAPI skeleton
* CLI entrypoint with `--mode server|agent|both`
* config loader
* Dockerfile
* docker-compose example
* README skeleton

Acceptance:

* `threadlens --mode server` starts API on 8128
* `threadlens --mode agent` starts API on 8129
* `threadlens --mode both` starts both
* `GET /api/v1/health` works
* Docker image builds

### Pass 2 — Config and models

Implement:

* Pydantic config models
* state models
* event models
* capability models
* report models
* health enums
* ID normalization helpers

Acceptance:

* config loads from `/config/config.yaml`
* env overrides basic config
* unit tests for config parsing

### Pass 3 — SQLite storage

Implement:

* SQLite DB setup
* current state storage
* event storage
* aggregate storage
* retention cleanup

Acceptance:

* events can be inserted/read
* current state can be upserted/read
* retention cleanup works
* tests included

### Pass 4 — mDNS/DNS-SD observer

Implement:

* observe configured mDNS services
* track service add/remove/change
* normalize service records
* extract useful TXT fields
* store current visible services
* emit events on add/remove/change
* calculate flap counts

Must support:

* `_trel._udp.local.`
* `_meshcop._udp.local.`
* `_matter._tcp.local.`
* `_matterc._udp.local.`

Acceptance:

* mDNS observer can run
* services appear in `/api/v1/mdns/services`
* TREL services appear in `/api/v1/trel/services`
* add/remove/change events stored

### Pass 5 — OTBR REST collector

Implement:

* collect from configured OTBR REST URLs
* fetch available endpoints safely
* normalize OTBR state
* normalize Thread network data
* normalize topology/device data where available
* detect reachability changes
* detect dataset/channel/role changes where available
* expose capabilities

Do not call mutating OTBR actions.

Diagnostic read-only actions are allowed only if explicitly safe.

Acceptance:

* configured OTBRs appear in `/api/v1/otbrs`
* capabilities are shown
* unreachable OTBRs produce warning state, not crash

### Pass 6 — Matter Server websocket observer

Implement:

* connect to configured Matter Server websocket URLs
* maintain connection state
* receive supported events
* normalize Matter node inventory
* normalize node availability
* emit node availability/recovery events
* track availability flaps
* expose Matter Server capabilities

Do not require subscription diagnostic events.

Mark subscription diagnostics unavailable unless actually received.

Acceptance:

* Matter servers appear in `/api/v1/matter-servers`
* Matter nodes appear in `/api/v1/matter-nodes`
* availability transitions create events
* connection loss/reconnect creates events

### Pass 7 — Health engine

Implement factual health rules.

Examples:

* OTBR unreachable => OTBR health critical
* Matter server disconnected => warning/critical
* Matter node unavailable => degraded/critical depending duration
* availability flaps above threshold => degraded
* foreign Thread/TREL services visible => warning, not critical
* missing capability => unknown/unavailable, not unhealthy

Acceptance:

* `/api/v1/health` returns environment/server/source/node summaries
* health reasons are included
* no causal claims

### Pass 8 — MQTT Discovery

Implement MQTT Discovery publishing.

Create devices/entities as described in this document.

Use attributes for detail.

Publish:

* ThreadLens Diagnostics
* Thread Environment Health
* Thread Networks
* OTBRs
* Matter Servers
* Matter Nodes

Acceptance:

* Home Assistant discovers entities via MQTT Discovery
* entities update when state changes
* attributes include relevant structured data
* entity count remains reasonable

### Pass 9 — Report API

Implement report generation.

Endpoints:

* `GET /api/v1/report`
* `GET /api/v1/report.yaml`
* `GET /api/v1/report.json`

Support:

* `Accept: application/yaml`
* `Accept: application/json`
* `window` query param
* `focus_node` query param

Report must include:

* summary
* capabilities
* current state
* networks
* OTBRs
* mDNS/TREL services
* Matter servers
* Matter nodes
* event aggregates
* recent events
* redaction summary

Acceptance:

* YAML report returns valid YAML
* JSON report returns valid JSON
* secrets are redacted
* unavailable metrics are null/unavailable, not zero

### Pass 10 — Agent mode

Implement minimal agent mode.

Required:

* `GET /api/v1/agent/health`
* `GET /api/v1/agent/status`
* `GET /api/v1/agent/capabilities`

Agent may initially report no deep local capabilities.

No SSH.

No Docker socket.

Acceptance:

* agent starts
* server can query configured `agent_url`
* agent capabilities are included in report

### Pass 11 — Docker hardening and docs

Implement:

* production Dockerfile
* healthcheck
* example config
* example compose
* README
* configuration docs
* report docs
* MQTT docs
* Docker networking/mDNS notes

Acceptance:

* fresh user can run container from docs

### Pass 12 — HAOS add-on repo

In `threadlens-ha-addon`, implement:

* add-on repository structure
* `config.yaml`
* Docker wrapper or image reference
* docs
* default mode `both`

Acceptance:

* add-on repo is structurally valid
* docs explain how to install and configure

### Pass 13 — HACS dashboard repo

In `threadlens-ha-integration`, implement frontend/dashboard-focused skeleton.

Required:

* `custom_components/threadlens`
* config flow for API URL
* service or button helper for report URL
* basic dashboard/card approach documented

Do not duplicate backend logic.

Acceptance:

* integration skeleton installs via HACS-style `custom_components`
* can configure ThreadLens API URL
* docs explain relationship to MQTT entities

### Pass 14 — Tests and quality

Implement tests:

* config parsing
* event generation
* retention cleanup
* report serialization/redaction
* MQTT discovery payload generation
* health engine
* mDNS normalization
* Matter event normalization with fixtures
* OTBR REST normalization with fixtures

Quality:

* ruff passes
* pytest passes
* Docker build passes

---

## 29. Acceptance criteria for complete v1

Complete v1 is accepted when:

* ThreadLens container runs in server mode
* ThreadLens container runs in agent mode
* ThreadLens container runs in both mode
* OTBR REST sources can be configured
* Matter Server websocket source can be configured
* mDNS observation works
* TREL mDNS visibility/flapping works
* Matter node availability flapping works
* MQTT Discovery creates HA devices/entities
* YAML/JSON reports are generated
* reports are redacted
* capabilities are explicit
* missing metrics are not misreported as zero
* SQLite retention works
* Docker Compose example works
* HAOS add-on repo scaffold exists
* HACS dashboard repo scaffold exists
* no SSH
* no Docker socket
* no mutating Thread/Matter operations

---

## 30. Important implementation notes

### Do not overfit to one home

ThreadLens was inspired by a Home Assistant environment with:

* multiple OTBRs
* Matter-over-Thread blinds
* separate Apple Thread network nearby
* TREL visibility issues

But the implementation must remain generic.

Do not hardcode:

* HomePods
* Apple
* Dendo
* blinds
* ZBT-2
* specific IPs
* specific entity names

Use generic concepts:

* foreign Thread network
* observed Thread network
* TREL service
* Matter node
* OTBR

### Naming

Use:

* `ThreadLens`
* `threadlens`

Avoid old names:

* `ThreadScope`
* `ThreadWatch`

### Reports are for ingestion

The report should be structured and clean.

It does not need to teach non-network people.

The user/vendor can feed the YAML/JSON into AI or tooling.

### No auth in v1

No auth.

Trusted LAN only.

Document this clearly.

### Redaction still required

Even without auth, reports must redact secrets.

Do not expose:

* Thread network key
* PSKc
* Matter secrets
* HA tokens
* Wi-Fi credentials

### Logs

Do not implement log parsing as a core dependency.

Optional log evidence may be designed later.

### Subscription flapping

Do not claim true subscription flapping unless structured Matter Server diagnostic events are available.

Until then:

* report Matter availability flapping
* report subscription diagnostics unavailable

### TREL flapping

ThreadLens v1 can report TREL mDNS/service flapping.

Do not claim OTBR internal TREL peer/counter flapping unless that data source exists.

---

## 31. Example final report statement

A good ThreadLens report might allow an external reader or AI to conclude:

```
The Home Assistant Matter Server is connected and sees 12 Matter nodes.
11 nodes are healthy.
Node 24 has 7 availability flaps in 24 hours.
OTBR REST sources are reachable and show the configured Thread network.
A second Thread network is visible via mDNS/TREL on the infrastructure network.
TREL mDNS services from that other network were visible, but OTBR internal TREL peer/counter diagnostics are not available from the configured sources.
Matter subscription diagnostics are not available from the current Matter Server websocket.
```

That is useful, honest, and vendor-friendly.

---

## 32. First Cursor instruction

When starting implementation, use this prompt:

```
Read THREADLENS_IMPLEMENTATION_PLAN.md in full. You'll need git access, so request that now cos I want to go to sleep while you do this. Ensure you create repos first so that I can solve any issues before looking away.

Do not write code yet.

First:
1. Summarise the intended architecture.
2. Identify ambiguities or contradictions.
3. Identify implementation risks.
4. Identify external API assumptions that need validation.
5. Propose any corrections to the plan.
6. Wait for approval before coding.
```

After approval, proceed pass-by-pass.

Do not skip passes.
