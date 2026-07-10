# Gauge on Linux — Installation Guide (central Windows + remote Linux hosts)

Observability for webMethods **Integration Server** and **Universal Messaging**
running on a **Linux fleet — 2 ESB + 2 BPM IS hosts and 4 UM hosts (8 hosts)** —
monitored from a **central Windows box** that runs Prometheus + Grafana + Loki.

- **IS** → native `sag_is_*` on `:5555` (MSR) **or** `jvm_*` via the JMX agent on `:9099`
- **UM** → `sag_um_*` on `:9200` (native, ships with UM 10.15+)
- **System** → `node_*` via **node_exporter** on `:9100`
- **Logs** → **Grafana Alloy** on each host → **Loki** (on the Windows box)

---

## 1. Architecture & who talks to whom

```
   CENTRAL (Windows box):  Prometheus  +  Grafana :3000  +  Loki :3100
        │                       ▲
        └── metrics scrape ─┐    └─ logs push (Alloy → Loki :3100) ◀──┐
            (pull)          ▼                                          │
   LINUX FLEET — 8 hosts, each running  node_exporter :9100  +  Grafana Alloy:
     IS   esb1, esb2   (role=esb)   ─ IS /metrics :5555 (sag_is_*)  or :9099 (jvm_*)
     IS   bpm1, bpm2   (role=bpm)   ─ IS /metrics :5555 (sag_is_*)  or :9099 (jvm_*)
     UM   um1, um2, um3, um4         ─ UM /metrics :9200 (sag_um_*)
```

The dashboards carry a **Role** (esb/bpm) and **Host** filter so one IS dashboard
serves all four IS hosts, and one UM dashboard serves all four realms.

**Firewall — two directions:**
| Direction | Ports | Why |
|---|---|---|
| Windows Prometheus → each Linux host | 9100, (5555 **or** 9099), 9200 | metrics **pull** (scrape) |
| each Linux host → Windows box | 3100 | logs **push** (Alloy → Loki) |
| browsers → Windows box | 3000 | Grafana UI |

Open the Linux ports **only to the Windows box IP**, and Loki :3100 **only to the
Linux host IPs**.

## 2. What's in this package

```
linux-install/
├── INSTALL.md                       ← you are here
├── prometheus/
│   ├── prometheus.yml               ← CENTRAL config (remote Linux targets)
│   └── rules/gauge-linux.rules.yml  ← node_* host rules + IS/UM alerts
├── grafana/dashboards/              ← 6 dashboards (Overview, IS sag_is_*, IS JMX,
│   │                                   UM, Linux Host, Logs)
├── node_exporter/README.md          ← install on EACH Linux host
├── webmethods/
│   ├── is-custom_wrapper.conf        ← IS host: JMX agent line (Option B)
│   ├── um-custom_wrapper.conf        ← UM host: native sag_um_* line
│   ├── jmx_exporter_config.yaml      ← IS JMX rules
│   └── jmx_prometheus_javaagent.jar  ← bundled v1.2.0 (IS Option B only)
├── alloy/
│   ├── config-is.alloy               ← IS host log shipper
│   ├── config-um.alloy               ← UM host log shipper
│   └── README.md
└── tools/generate_dashboards.py      ← regenerate dashboards (optional)
```

The **v1.2.0 `jmx_prometheus_javaagent.jar`** is bundled in `webmethods/` (pure-Java,
runs on Linux). Only needed for IS **Option B** (native `sag_is_*` needs no jar; UM
uses its own jar shipped in `<UM>/lib/`).

---

## Part A — Central Windows box (Prometheus + Grafana + Loki)

Install the three services exactly as in **`windows-install/INSTALL.md`** (NSSM
services for Prometheus/Grafana/Loki; Grafana provisioning), **with these swaps**:

1. **Prometheus** — use **this** package's `prometheus/prometheus.yml` (remote Linux
   targets) and `prometheus/rules/` — *not* the windows-install ones (those are
   localhost + `windows_*`). Edit `prometheus.yml`: replace the `*.example.local`
   hostnames with your **8** real hosts (esb1/esb2/bpm1/bpm2 + um1–um4), keep the
   `host:` + `role:` labels, pick the IS path (Option A native or Option B JMX), and set
   the IS `basic_auth` password.
2. **Grafana** — reuse the windows-install datasource provisioning (Prometheus + Loki on
   `localhost`), but point the **dashboards** provider at **this** package's
   `grafana/dashboards/` (the host dashboard here is **Linux**, `node_*`).
3. **Loki** — install per windows-install `loki/` (it receives logs from the Linux
   Alloy agents). Make sure Windows firewall allows **:3100 inbound** from the Linux hosts.

## Part B — Each IS host (esb1, esb2, bpm1, bpm2)

Do this on **all four** IS hosts; set `host`/`role`/`is_instance` per host to match
`prometheus.yml` (ESB hosts `role=esb`, BPM hosts `role=bpm`).

1. **node_exporter** — follow `node_exporter/README.md` (systemd service on :9100).
2. **IS metrics — pick ONE:**
   - **Option A (recommended if MSR):** enable the native endpoint — set
     `SAG_IS_METRICS_ENDPOINT_ACL=Anonymous` (or add `wm.server.query:getPrometheusStats`
     to the :5555 port allow list). No agent, no restart-for-agent. Dashboard:
     **Gauge - Integration Server (native sag_is_*)**.
   - **Option B (any licence):** copy the bundled `webmethods/jmx_prometheus_javaagent.jar`
     + `webmethods/jmx_exporter_config.yaml` to `/opt/softwareag/jmx/`, add the line from
     `webmethods/is-custom_wrapper.conf` to the IS instance's `custom_wrapper.conf`, and
     **restart IS**. Dashboard: **Gauge - Integration Server (JVM)**.
     (Make sure the `is` job in `prometheus.yml` matches the option you chose.)
3. **Logs** — install Alloy (`alloy/README.md`), use **`config-is.alloy`**, set the Loki
   URL, the `host`/`role`/`is_instance` labels for THIS host, and the IS log paths;
   `systemctl enable --now alloy`.
4. Open :9100 + (:5555 **or** :9099) to the Windows box.

## Part C — Each UM host (um1, um2, um3, um4)

Do this on **all four** UM hosts; set `host=um1..um4` per host to match `prometheus.yml`.

1. **node_exporter** — same as Part B step 1.
2. **UM metrics** — add the line from `webmethods/um-custom_wrapper.conf` to the UM
   realm's `custom_wrapper.conf` (switches on the native `sag_um_*` exporter that ships
   with UM), then **restart the UM realm**. Verify `curl http://localhost:9200/metrics`.
3. **Logs** — install Alloy, use **`config-um.alloy`**, set the Loki URL, the `host=um<N>`
   label for THIS host, and the UM log paths; `systemctl enable --now alloy`.
4. Open :9100 + :9200 to the Windows box.

---

## 3. Dashboards

| Dashboard | UID | Shows |
|---|---|---|
| **Gauge - Overview** | `gauge-overview` | reachability of all targets + Linux host vitals (`node_*`) + IS/UM heap, UM connections & stuck channels |
| **Gauge - Integration Server (native sag_is_*)** | `gauge-is-sag` | Option A — service invocations/latency/errors, threads, memory, GC, sessions, HTTP, CPU/disk |
| **Gauge - Integration Server (JVM)** | `gauge-is-jvm` | Option B — heap/non-heap, threads, GC, classes, buffer pools |
| **Gauge - Universal Messaging** | `gauge-um` | heap/direct/disk, threads, throughput, channel/durable/connection health |
| **Gauge - Linux Host** | `gauge-linux-host` | `node_*`: CPU/mem/uptime, filesystem used%, disk & network IO, load — per host (Host variable) |
| **Gauge - Logs** | `gauge-logs` | IS/UM/wrapper logs via Loki: volume by level, error stream, per-source panels, search box |

Regenerate any time: `python3 tools/generate_dashboards.py` (Python 3, stdlib only).

## 4. Verify end-to-end

1. On each Linux host: `curl localhost:9100/metrics`, and `:5555`/`:9099` (IS) or
   `:9200` (UM).
2. On Windows: <http://localhost:9090/targets> — all **16** targets UP: `node` (8),
   `is` (4), `um` (4). If a target is DOWN, it's almost always the **Linux firewall**
   blocking the Windows box.
3. <http://localhost:9090/rules> shows the `gauge_*` groups.
4. Grafana **Gauge - Overview** — tiles populated; **Gauge - Linux Host** lists all 8
   hosts; the **IS** dashboards filter by **Role** (esb/bpm) + **Host**, **UM** by
   **Host** (realm); **Gauge - Logs** streams lines once Alloy is running.

## 5. Troubleshooting

| Symptom | Likely cause / fix |
|---|---|
| `node`/`is`/`um` target DOWN | Linux firewall not open to the Windows box IP; wrong hostname/port in `prometheus.yml`; exporter/service not running. |
| IS `is` target 404 | Option A on a **non-MSR** IS returns 404 — switch the `is` job to Option B (JMX), or add the `wm-is-exporter` add-on. |
| Host tiles empty on Overview/Linux Host | node_exporter not running, or the `host:` label not set on the scrape target. |
| No logs in **Gauge - Logs** | Alloy can't reach Windows Loki :3100 (Windows firewall inbound / Linux egress); wrong Loki URL; wrong log path globs; Alloy user can't read the log files. |
| Some hosts missing / merged | Every node_exporter target needs a **distinct** `host:` label in the `node` job (all 8); IS targets also need `role:` (esb/bpm). |
| IS/UM dashboard shows all hosts merged | Use the **Role**/**Host** (IS) or **Host** (UM) variable at the top to focus one host/realm. |

## 6. Out of scope / add-ons
- **Alertmanager** routing (uncomment `alerting:` in `prometheus.yml` + install it on Windows).
- **Service-level IS metrics on a non-MSR IS** — the `wm-is-exporter` (IS Admin API, any licence).
- **TLS** on the scrape + push paths (recommended if the network isn't trusted).
