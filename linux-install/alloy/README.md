# Grafana Alloy on Linux (log shipper -> Loki on Windows)

Runs on **each** Linux host. The IS host uses `config-is.alloy`; the UM host uses
`config-um.alloy`. Both push logs to the **Loki on the central Windows box**.

## Install (systemd service, Grafana APT/RPM repo)

Debian/Ubuntu:
```bash
sudo mkdir -p /etc/apt/keyrings
wget -q -O - https://apt.grafana.com/gpg.key | gpg --dearmor | sudo tee /etc/apt/keyrings/grafana.gpg > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/grafana.gpg] https://apt.grafana.com stable main" | sudo tee /etc/apt/sources.list.d/grafana.list
sudo apt-get update && sudo apt-get install -y alloy
```
RHEL/rpm:
```bash
sudo tee /etc/yum.repos.d/grafana.repo >/dev/null <<'EOF'
[grafana]
name=grafana
baseurl=https://rpm.grafana.com
repo_gpgcheck=1
enabled=1
gpgcheck=1
gpgkey=https://rpm.grafana.com/gpg.key
EOF
sudo dnf install -y alloy
```

## Configure + run

1. Put the right config for this host at `/etc/alloy/config.alloy`:
   - IS host:  copy `config-is.alloy`
   - UM host:  copy `config-um.alloy`
2. **Edit it**: set the `loki.write` **url** to your Windows box
   (`http://<WINDOWS-HOST>:3100/loki/api/v1/push`), and adjust the log **path globs**
   + IS instance / UM realm names to your install.
3. Make sure Alloy can read the logs (add its user to the `sag`/webMethods group, or
   loosen log dir perms) and can **reach the Windows Loki :3100** (Linux egress +
   Windows firewall inbound).
4. Enable + start:
   ```bash
   sudo systemctl enable --now alloy
   sudo systemctl restart alloy   # after any config edit
   ```
5. Verify: Alloy UI at `http://<host>:12345` (components healthy); in Grafana open
   **Explore -> Loki** and run `{host="is-host"}` (or `um-host`), or open **Gauge - Logs**.

## Notes

- `level` is extracted per line and promoted to a Loki **label** (filter
  `{component="integration-server", level="ERROR"}`, chart error rates). Keep labels
  low-cardinality - use LogQL line filters (`|=`, `|~`) for request ids / threads.
- Logs carry `host` (`is-host` / `um-host`) matching the Prometheus `host` label, so
  you can pivot metric <-> log by host.
