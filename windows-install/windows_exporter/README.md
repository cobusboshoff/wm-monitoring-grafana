# windows_exporter (host metrics -> `windows_*` on :9182)

Provides the Windows host metrics (CPU, memory, disk, network, services, and the
Java process CPU/memory) that the **Windows Host** and **Overview** dashboards use.

> **Pin version `v0.31.7`.** The 0.30 -> 0.31 line removed the `cs` collector and
> trimmed `os`. The dashboards in this package use v0.31.x metric names
> (`windows_memory_physical_total_bytes`, `time() - windows_system_boot_time_timestamp`,
> etc.). A different version will silently show "No data" on some panels.

## Install (MSI installs + starts a Windows service automatically)

Download `windows_exporter-0.31.7-amd64.msi` from
<https://github.com/prometheus-community/windows_exporter/releases/tag/v0.31.7>.

The cleanest install uses a **config file** (avoids PowerShell quote-escaping):

```powershell
msiexec /i windows_exporter-0.31.7-amd64.msi --% CONFIG_FILE="C:\ProgramData\windows_exporter\config.yaml" ADDLOCAL=FirewallException
```

Put this at `C:\ProgramData\windows_exporter\config.yaml` (a ready copy is in
this folder as `config.yaml`):

```yaml
collectors:
  enabled: cpu,logical_disk,memory,net,os,system,service,process,tcp,time
collector:
  process:
    include: "(java|jvm).*"                         # only JVMs - process is high-cardinality
  service:
    include: "(?i).*(Integration Server|Universal Messaging).*"   # only webMethods services
web:
  listen-address: ":9182"
```

Or one-line with flags instead of a config file:

```powershell
msiexec /i windows_exporter-0.31.7-amd64.msi --% ENABLED_COLLECTORS=cpu,logical_disk,memory,net,os,system,service,process,tcp,time LISTEN_PORT=9182 ADDLOCAL=FirewallException EXTRA_FLAGS="--collector.process.include=""(java|jvm).*"" --collector.service.include=""(?i).*(Integration Server|Universal Messaging).*"""
```

## Why the filters matter

- **`process`** is not on by default and is **expensive** (~16 series *per process*).
  The `include: "(java|jvm).*"` limit keeps it to the IS/UM JVMs. The `process`
  label is the exe base name (`java`); multiple JVMs are told apart by `process_id`.
- **`service`** can be heavy on hosts with hundreds of services. The include limits
  it to the webMethods services so the "services running" panel/alert stays clean.
  Edit the regex to match your exact Windows service display names.

## Verify

```powershell
curl http://localhost:9182/metrics | Select-String "windows_cpu_time_total|windows_memory_physical_total_bytes|windows_process_working_set_bytes"
```

You should see data. If `windows_process_*` or `windows_service_*` are missing, the
`process` / `service` collectors aren't enabled - check the config above.
