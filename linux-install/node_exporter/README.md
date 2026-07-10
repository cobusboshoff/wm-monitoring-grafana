# node_exporter (Linux host metrics -> `node_*` on :9100)

Runs on **each** Linux host (the IS host and the UM host). The central Windows
Prometheus scrapes `http://<host>:9100/metrics`.

## Install (systemd service)

1. Download + install the binary (match a current release):
   ```bash
   VER=1.8.2
   curl -sSL -o /tmp/node_exporter.tgz \
     https://github.com/prometheus/node_exporter/releases/download/v${VER}/node_exporter-${VER}.linux-amd64.tar.gz
   sudo tar -xzf /tmp/node_exporter.tgz -C /usr/local/bin --strip-components=1 \
     node_exporter-${VER}.linux-amd64/node_exporter
   sudo useradd -rs /bin/false node_exporter 2>/dev/null || true
   ```
2. Create `/etc/systemd/system/node_exporter.service`:
   ```ini
   [Unit]
   Description=Prometheus node_exporter
   After=network.target
   [Service]
   User=node_exporter
   ExecStart=/usr/local/bin/node_exporter
   Restart=on-failure
   [Install]
   WantedBy=multi-user.target
   ```
   The default collectors (cpu, meminfo, diskstats, netdev, filesystem, loadavg,
   filefd) cover every panel on the **Linux Host** dashboard - no flags needed.
3. Enable + start:
   ```bash
   sudo systemctl daemon-reload && sudo systemctl enable --now node_exporter
   ```
4. Open :9100 **to the Windows Prometheus host only**:
   ```bash
   # firewalld:
   sudo firewall-cmd --add-port=9100/tcp --permanent && sudo firewall-cmd --reload
   # or ufw (restrict to the Windows IP):
   sudo ufw allow from <WINDOWS_IP> to any port 9100 proto tcp
   ```
5. Verify from the Windows box: browse `http://<host>:9100/metrics` - you should
   see `node_cpu_seconds_total`, `node_memory_MemAvailable_bytes`, etc.

> The `host` label the dashboards group on is set by **Prometheus** (the `host:`
> label in each scrape target), not here - node_exporter itself doesn't need it.
