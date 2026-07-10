# Gauge on Windows — Installation Guide (metrics: Prometheus + Grafana)

A **native-Windows** (no Docker) observability stack for webMethods **Integration
Server** and **Universal Messaging**, plus the **Windows host**. Metrics only —
no tracing, no API Gateway, no LLM.

- **IS** → **choose one path:** native `sag_is_*` on `:5555` (richer/service-level, lighter touch — needs an **MSR** licence) **or** `jvm_*` via the JMX exporter javaagent (JVM-level, any licence)
- **UM** → `sag_um_*` via UM's native exporter (ships with UM 10.15+)
- **Host** → `windows_*` via windows_exporter

---

## 1. Architecture & ports

Everything runs on the **same Windows box** and talks over `localhost`.

```
  Integration Server (JVM) ──[JMX agent]──▶ :9099  ┐
  Universal Messaging      ──[UM exporter]─▶ :9200  ├─▶ Prometheus :9090 ─▶ Grafana :3000
  Windows host             ──[windows_exp]─▶ :9182  ┘        (scrape+store+alerts)   (dashboards)
```

| Component | Port | Metric family | Runs as |
|---|---|---|---|
| Prometheus | 9090 | — | Windows service |
| Grafana | 3000 | — | Windows service |
| windows_exporter | 9182 | `windows_*` | Windows service (MSI) |
| IS — native (Option A) | 5555 (per instance) | `sag_is_*` | the IS itself (enable `/metrics`) |
| IS — JMX (Option B) | 9099 (per instance) | `jvm_*` | inside the IS JVM (javaagent) |
| UM exporter | 9200 | `sag_um_*` | inside the UM JVM (javaagent) |

> **Firewall:** these ports only need to be reachable **from Prometheus on the same
> host**, i.e. localhost — you do **not** need to open them externally. Only Grafana
> :3000 needs to be reachable from the browsers of whoever views dashboards.

## 2. What's in this package

```
windows-install/
├── INSTALL.md                     ← you are here
├── prometheus/
│   ├── prometheus.yml             ← scrape config (localhost targets)
│   └── rules/gauge.rules.yml      ← recording rules + alerts
├── grafana/
│   ├── provisioning/
│   │   ├── datasources/prometheus.yml
│   │   └── dashboards/gauge.yml   ← dashboard provider (set the path!)
│   └── dashboards/                ← the 4 dashboard JSON files
│       ├── gauge-overview.json
│       ├── gauge-is-jvm.json
│       ├── gauge-um.json
│       └── gauge-windows.json
├── webmethods/
│   ├── is-custom_wrapper.conf     ← snippet to add to the IS wrapper
│   ├── um-custom_wrapper.conf     ← snippet to add to the UM wrapper
│   └── jmx_exporter_config.yaml   ← IS JMX exporter rules
├── windows_exporter/
│   ├── README.md                  ← MSI install command + collector filters
│   └── config.yaml                ← windows_exporter config
└── tools/generate_dashboards.py   ← regenerate the dashboard JSON (optional)
```

Suggested install root on the Windows box: **`C:\gauge\`** (used throughout below).

## 3. Prerequisites

- Windows Server (or Windows 10/11) with the webMethods IS + UM already installed.
- A **JRE/JDK** is already present (webMethods ships one) — nothing extra to install.
- Admin PowerShell for installing services.
- Downloads (grab these first):
  - Prometheus (Windows): `prometheus-*.windows-amd64.zip` — <https://prometheus.io/download/>
  - Grafana (Windows): the OSS `.zip` (or `.msi`) — <https://grafana.com/grafana/download?platform=windows>
  - windows_exporter **v0.31.7** MSI — <https://github.com/prometheus-community/windows_exporter/releases/tag/v0.31.7>
  - **NSSM** (to run Prometheus/Grafana as services) — <https://nssm.cc/download>
  - `jmx_prometheus_javaagent-*.jar` (for IS) — either copy the one that ships with UM
    (`<UM>\lib\jmx_prometheus_javaagent.jar`) or download from
    <https://github.com/prometheus/jmx_exporter/releases> (use the **javaagent** jar, 0.20.0+).

---

## 4. Step-by-step

### Step 1 — windows_exporter (host metrics)

Follow **`windows_exporter\README.md`**. In short: copy `windows_exporter\config.yaml`
to `C:\ProgramData\windows_exporter\config.yaml`, then:

```powershell
msiexec /i windows_exporter-0.31.7-amd64.msi --% CONFIG_FILE="C:\ProgramData\windows_exporter\config.yaml" ADDLOCAL=FirewallException
```

Verify: `curl http://localhost:9182/metrics` returns text. The MSI already created
and started the `windows_exporter` service.

### Step 2 — Integration Server (pick ONE path)

Both produce a different metric family and a matching dashboard. **Option A is
recommended when it's available** (lighter to install, much richer data).

#### Option A — native `sag_is_*` on :5555 (needs an MSR-licensed IS)

No javaagent, no wrapper edit, no forced JVM restart — just switch on the endpoint.

1. Enable the metrics endpoint (one of):
   - set the environment variable `SAG_IS_METRICS_ENDPOINT_ACL=Anonymous` (then you
     can drop the `basic_auth` block in `prometheus.yml`), **or**
   - add the service `wm.server.query:getPrometheusStats` to the allow list of the
     port you scrape (5555 by default).
2. In `prometheus.yml` the `is` job already points at `localhost:5555` with
   `basic_auth` — set the `password` to your IS **Administrator** password (or remove
   `basic_auth` if you used the Anonymous ACL). One target per instance (own port),
   each with its own `is_instance` label.
3. Verify: `curl -u Administrator:<pw> http://localhost:5555/metrics` shows
   `sag_is_server_threads`, `sag_is_service_requests_total`, etc.
   → Dashboard: **Gauge - Integration Server (native sag_is_*)**.

> A **standard (non-MSR) IS returns HTTP 404** on `/metrics`. If that's you, use
> Option B, or the `wm-is-exporter` add-on (§8) which needs no licence.

#### Option B — JMX exporter `jvm_*` on :9099 (any licence, JVM-level only)

1. Copy `jmx_prometheus_javaagent.jar` and `webmethods\jmx_exporter_config.yaml`
   to `C:\gauge\`.
2. Open the IS instance's wrapper override:
   `<IntegrationServer>\profiles\IS_<instance>\configuration\custom_wrapper.conf`
3. Add the line from **`webmethods\is-custom_wrapper.conf`** (adjust the paths):
   ```
   wrapper.java.additional.401=-javaagent:C:\gauge\jmx_prometheus_javaagent.jar=9099:C:\gauge\jmx_exporter_config.yaml
   ```
   - Set the index (`401`) to the **next free** `wrapper.java.additional.N`. If the
     wrapper reports a sequence gap, add `wrapper.ignore_sequence_gaps=TRUE`.
   - **Multiple IS instances:** one per instance, each on its **own port** (9099, 9100, …).
4. In `prometheus.yml`, comment out the Option A `is` job and uncomment the Option B
   block (targets `:9099`).
5. **Restart the Integration Server** (the javaagent loads at JVM start).
6. Verify: `curl http://localhost:9099/metrics` shows `jvm_memory_used_bytes`, etc.
   → Dashboard: **Gauge - Integration Server (JVM)**.

### Step 3 — UM native exporter (`sag_um_*` on :9200)

UM 10.15+ **already ships** the jar and the SAG metrics config — you only switch it on.

1. Open the UM realm wrapper override:
   `<UniversalMessaging>\server\<realmName>\bin\custom_wrapper.conf`
2. Add the line from **`webmethods\um-custom_wrapper.conf`** (adjust paths/realm name):
   ```
   wrapper.java.additional.401=-javaagent:C:\SoftwareAG\UniversalMessaging\lib\jmx_prometheus_javaagent.jar=9200:C:\SoftwareAG\UniversalMessaging\server\umserver\bin\jmx_sag_um_exporter.yaml
   ```
3. **Restart the UM realm server.**
4. Verify: `curl http://localhost:9200/metrics` shows `sag_um_server_*`, `sag_um_topic_*`.

### Step 4 — Prometheus

1. Unzip Prometheus to `C:\gauge\prometheus\`.
2. Replace its `prometheus.yml` with **`prometheus\prometheus.yml`** from this package,
   and copy the **`prometheus\rules\`** folder alongside it
   (`C:\gauge\prometheus\rules\gauge.rules.yml`).
3. If you have more than one IS instance, add a target per instance under the `is`
   job (see the commented example in `prometheus.yml`), each with its own port and a
   distinct `is_instance` label.
4. Install as a service with NSSM (run in an **admin** PowerShell):
   ```powershell
   C:\gauge\nssm\nssm.exe install Prometheus C:\gauge\prometheus\prometheus.exe "--config.file=C:\gauge\prometheus\prometheus.yml --storage.tsdb.path=C:\gauge\prometheus\data --web.enable-lifecycle"
   C:\gauge\nssm\nssm.exe start Prometheus
   ```
5. Verify: open <http://localhost:9090/targets> — the `is`, `um`, `windows`,
   `prometheus` targets should all be **UP**. (After a config edit later you can
   reload without restart: `curl -Method POST http://localhost:9090/-/reload`.)

### Step 5 — Grafana

1. Unzip/install Grafana to `C:\gauge\grafana\`.
2. Wire provisioning (auto-loads the datasource + dashboards on start):
   - Copy `grafana\provisioning\datasources\prometheus.yml` →
     `C:\gauge\grafana\conf\provisioning\datasources\prometheus.yml`
   - Copy `grafana\provisioning\dashboards\gauge.yml` →
     `C:\gauge\grafana\conf\provisioning\dashboards\gauge.yml`
   - Copy the four JSON files from `grafana\dashboards\` →
     `C:\gauge\dashboards\`
   - **Edit** `...\provisioning\dashboards\gauge.yml` so `path:` is
     `C:\gauge\dashboards` (must match where you put the JSON).
3. Install as a service with NSSM:
   ```powershell
   C:\gauge\nssm\nssm.exe install Grafana C:\gauge\grafana\bin\grafana-server.exe
   C:\gauge\nssm\nssm.exe set Grafana AppDirectory C:\gauge\grafana
   C:\gauge\nssm\nssm.exe start Grafana
   ```
   (Grafana resolves `conf\` and `data\` relative to its home, hence `AppDirectory`.)
4. Open <http://localhost:3000> (default login `admin` / `admin`, it prompts to change).
   Under **Dashboards → Gauge** you'll find the four dashboards; the **Prometheus**
   datasource is already wired.

---

## 5. Dashboards

| Dashboard | UID | Shows |
|---|---|---|
| **Gauge - Overview** | `gauge-overview` | Reachability + host CPU/mem/disk/uptime + IS/UM heap, UM connections & stuck channels |
| **Gauge - Integration Server (native sag_is_*)** | `gauge-is-sag` | **Option A** — service invocations/latency/errors, threads, memory, GC, sessions, HTTP, CPU/disk (service-level; per instance) |
| **Gauge - Integration Server (JVM)** | `gauge-is-jvm` | **Option B** — heap/non-heap, threads, GC, classes, buffer pools, JVM uptime (JVM-level; per instance) |
| **Gauge - Universal Messaging** | `gauge-um` | Heap/direct/disk, threads, throughput, **channel/durable/connection health** (stuck-channel + subscriber tables) |
| **Gauge - Windows Host** | `gauge-windows` | CPU/mem/uptime, disk used% + IO, network, **Java process** CPU/mem/threads, **Windows service** running-state |

Regenerate the JSON any time (after editing a builder) with:
`python3 tools\generate_dashboards.py` (needs Python 3; stdlib only).

## 6. Verify end-to-end

1. Each exporter: `curl http://localhost:9099/metrics`, `:9200/metrics`, `:9182/metrics`.
2. Prometheus targets all UP: <http://localhost:9090/targets>.
3. Rules loaded: <http://localhost:9090/rules> shows the `gauge_*` groups.
4. Grafana: open **Gauge - Overview** — tiles should be green and populated.

## 7. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `is` target DOWN / no `jvm_*` | IS not restarted after the wrapper edit; wrong port; or a `wrapper.java.additional.N` collision — check the IS wrapper log. |
| IS "JVM uptime" panel empty | The `java.lang Runtime Uptime` rule didn't match your JVM — harmless; every other IS panel is unaffected. |
| `um` target DOWN | UM not restarted; wrong realm path in the wrapper line; or the shipped `jmx_sag_um_exporter.yaml` is at a different path — confirm under `<UM>\server\<realm>\bin\`. |
| Windows panels show "No data" | windows_exporter version mismatch — **must be v0.31.x** (0.30 used different names). Check `windows_exporter_build_info`. |
| No `windows_process_*` / `windows_service_*` | The `process` / `service` collectors aren't enabled — see `windows_exporter\config.yaml`. |
| Grafana shows no dashboards | Provisioning `path:` doesn't match where you copied the JSON; check `grafana\data\log\grafana.log` for provisioning errors. |
| Alerts don't route anywhere | Expected — Alertmanager is optional (see below). Prometheus still **evaluates** them (Status → Alerts). |

## 8. Optional add-ons (beyond "the basics")

- **Alertmanager** — to actually route/notify on the alerts: install `alertmanager.exe`
  (NSSM service, port 9093) and uncomment the `alerting:` block in `prometheus.yml`.
- **Service-level IS metrics on standard IS** — `jvm_*` is JVM-level only. For
  per-service invocation counts/latency, JDBC pool saturation, scheduler health
  **without** an MSR licence, add the `wm-is-exporter` (polls the IS Admin API →
  `webmethods_is_*`). Ask and we'll package it.
- **SQL Server** — add `prometheus-mssql-exporter` (or the `mssql` collector) + a
  scrape job + a DB dashboard.
- **MSR-licensed IS** — if your IS *is* MSR-licensed, enable the native `/metrics`
  endpoint (`SAG_IS_METRICS_ENDPOINT_ACL=Anonymous` + the `getPrometheusStats`
  service on the port's allow list) for the richer `sag_is_*` service-level metrics.
