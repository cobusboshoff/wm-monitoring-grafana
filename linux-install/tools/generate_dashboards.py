#!/usr/bin/env python3
"""
Gauge (webMethods observability) - Windows dashboard generator.

Self-contained: no third-party deps, stdlib only. Emits the Grafana dashboard
JSON for the native-Windows / standard-IS(JMX) / UM / windows_exporter stack
into ../grafana/dashboards/.

    python3 tools/generate_dashboards.py

Metric families (see windows-install/README / INSTALL.md):
    IS   -> jvm_*     (JMX exporter javaagent, job="is",     label is_instance)
    UM   -> sag_um_*  (native UM exporter,      job="um")
    host -> windows_* (windows_exporter,        job="windows")

Every panel targets the single Prometheus datasource (uid "prometheus").
Regenerate after editing a builder; JSON is picked up by Grafana within ~30s.
"""
import json
import os

DS = {"type": "prometheus", "uid": "prometheus"}
DS_LOKI = {"type": "loki", "uid": "loki"}
OUT = os.path.join(os.path.dirname(__file__), "..", "grafana", "dashboards")


# --------------------------------------------------------------------------- #
# Panel helpers (minimal Grafana v39 / Grafana 13 schema)                      #
# --------------------------------------------------------------------------- #
def _ids():
    n = [0]
    def nxt():
        n[0] += 1
        return n[0]
    return nxt


def _thresholds(steps):
    return {"mode": "absolute", "steps": steps}


def _fc(unit="short", thresholds=None, minv=None, maxv=None, decimals=None, color_mode="thresholds"):
    d = {"unit": unit, "color": {"mode": color_mode},
         "custom": {}, "mappings": []}
    if thresholds is not None:
        d["thresholds"] = thresholds
    else:
        d["thresholds"] = _thresholds([{"color": "green", "value": None}])
    if minv is not None:
        d["min"] = minv
    if maxv is not None:
        d["max"] = maxv
    if decimals is not None:
        d["decimals"] = decimals
    return {"defaults": d, "overrides": []}


def row(title, y):
    return {"type": "row", "title": title, "collapsed": False,
            "gridPos": {"h": 1, "w": 24, "x": 0, "y": y}, "panels": []}


def text(pid, content, x, y, w=24, h=4):
    return {"id": pid, "type": "text", "title": "",
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "options": {"mode": "markdown", "content": content},
            "datasource": DS}


def _targets(queries):
    out = []
    for i, (expr, legend) in enumerate(queries):
        out.append({"refId": chr(ord("A") + i), "datasource": DS,
                    "expr": expr, "legendFormat": legend})
    return out


def stat(pid, title, expr, x, y, w=6, h=4, unit="short", thresholds=None,
         color_mode="thresholds", graph_mode="area", decimals=None,
         display_name=None, legend=""):
    fc = _fc(unit=unit, thresholds=thresholds, decimals=decimals,
             color_mode=("thresholds" if thresholds else "fixed"))
    if display_name:
        fc["defaults"]["displayName"] = display_name
    t = _targets([(expr, legend)])
    for tg in t:
        tg["instant"] = True
    return {"id": pid, "type": "stat", "title": title,
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "datasource": DS, "targets": t, "fieldConfig": fc,
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "orientation": "auto", "textMode": "value_and_name",
                        "colorMode": color_mode, "graphMode": graph_mode,
                        "justifyMode": "auto"}}


def gauge(pid, title, expr, x, y, w=6, h=6, unit="percentunit", minv=0, maxv=1,
          thresholds=None, legend=""):
    thresholds = thresholds or _thresholds([
        {"color": "green", "value": None},
        {"color": "yellow", "value": 0.75},
        {"color": "red", "value": 0.9}])
    return {"id": pid, "type": "gauge", "title": title,
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "datasource": DS, "targets": _targets([(expr, legend)]),
            "fieldConfig": _fc(unit=unit, thresholds=thresholds, minv=minv, maxv=maxv),
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "orientation": "auto", "showThresholdLabels": False,
                        "showThresholdMarkers": True}}


def timeseries(pid, title, queries, x, y, w=12, h=7, unit="short", stack=False,
               fill=8, legend_place="bottom"):
    fc = _fc(unit=unit)
    fc["defaults"]["custom"] = {
        "drawStyle": "line", "lineInterpolation": "linear", "lineWidth": 1,
        "fillOpacity": fill, "gradientMode": "none", "showPoints": "never",
        "stacking": {"mode": "normal" if stack else "none", "group": "A"},
        "axisPlacement": "auto"}
    return {"id": pid, "type": "timeseries", "title": title,
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "datasource": DS, "targets": _targets(queries), "fieldConfig": fc,
            "options": {"legend": {"displayMode": "list", "placement": legend_place, "showLegend": True},
                        "tooltip": {"mode": "multi", "sort": "desc"}}}


def state_timeline(pid, title, queries, x, y, w=24, h=6, mappings=None):
    fc = _fc(unit="short")
    fc["defaults"]["custom"] = {"fillOpacity": 80, "lineWidth": 0}
    fc["defaults"]["mappings"] = mappings or [
        {"type": "value", "options": {"0": {"text": "DOWN", "color": "red", "index": 0},
                                       "1": {"text": "UP", "color": "green", "index": 1}}}]
    fc["defaults"]["thresholds"] = _thresholds([
        {"color": "red", "value": None}, {"color": "green", "value": 1}])
    return {"id": pid, "type": "state-timeline", "title": title,
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "datasource": DS, "targets": _targets(queries), "fieldConfig": fc,
            "options": {"mergeValues": True, "showValue": "never", "alignValue": "left",
                        "rowHeight": 0.9, "legend": {"displayMode": "list", "placement": "bottom", "showLegend": True}}}


def table(pid, title, exprs, x, y, w=12, h=8, unit="short",
          transformations=None, sort_by=None, sort_desc=True):
    tgs = []
    for i, e in enumerate(exprs):
        tgs.append({"refId": chr(ord("A") + i), "datasource": DS, "expr": e,
                    "format": "table", "instant": True})
    opts = {"showHeader": True, "cellHeight": "sm"}
    if sort_by:
        opts["sortBy"] = [{"displayName": sort_by, "desc": sort_desc}]
    return {"id": pid, "type": "table", "title": title,
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "datasource": DS, "targets": tgs,
            "fieldConfig": _fc(unit=unit),
            "transformations": transformations or [], "options": opts}


def dashboard(uid, title, panels, tags, templating=None, refresh="30s"):
    return {
        "uid": uid, "title": title, "tags": tags, "schemaVersion": 39,
        "version": 1, "editable": True, "style": "dark", "graphTooltip": 1,
        "time": {"from": "now-6h", "to": "now"}, "refresh": refresh,
        "timepicker": {}, "templating": {"list": templating or []},
        "annotations": {"list": [{"builtIn": 1, "type": "dashboard",
                                   "name": "Annotations & Alerts", "enable": True,
                                   "hide": True, "iconColor": "rgba(0, 211, 255, 1)"}]},
        "panels": panels}


def var_query(name, label, metric, label_name, current_all=True):
    return {"name": name, "type": "query", "label": label, "datasource": DS,
            "query": {"query": "label_values(%s, %s)" % (metric, label_name), "refId": "StandardVariableQuery"},
            "refresh": 2, "sort": 1, "multi": True, "includeAll": True,
            "current": {"text": "All", "value": "$__all"} if current_all else {},
            "options": [], "regex": ""}


def var_textbox(name, label, default=""):
    return {"name": name, "type": "textbox", "label": label, "query": default,
            "current": {"text": default, "value": default},
            "options": [{"text": default, "value": default, "selected": True}]}


# ---- Loki (logs) panel helpers ----
def logs_panel(pid, title, expr, x, y, w=24, h=10):
    return {"id": pid, "type": "logs", "title": title,
            "gridPos": {"h": h, "w": w, "x": x, "y": y}, "datasource": DS_LOKI,
            "targets": [{"refId": "A", "datasource": DS_LOKI, "expr": expr, "queryType": "range"}],
            "options": {"showTime": True, "showLabels": False, "showCommonLabels": False,
                        "wrapLogMessage": True, "prettifyLogMessage": False,
                        "enableLogDetails": True, "dedupStrategy": "none", "sortOrder": "Descending"}}


def loki_stat(pid, title, expr, x, y, w=6, h=4, thresholds=None, display_name=None):
    fc = _fc(unit="short", thresholds=thresholds, color_mode=("thresholds" if thresholds else "fixed"))
    if display_name:
        fc["defaults"]["displayName"] = display_name
    return {"id": pid, "type": "stat", "title": title,
            "gridPos": {"h": h, "w": w, "x": x, "y": y}, "datasource": DS_LOKI,
            "targets": [{"refId": "A", "datasource": DS_LOKI, "expr": expr, "queryType": "instant"}],
            "fieldConfig": fc,
            "options": {"reduceOptions": {"calcs": ["lastNotNull"], "fields": "", "values": False},
                        "orientation": "auto", "textMode": "value_and_name",
                        "colorMode": ("background" if thresholds else "value"),
                        "graphMode": "area", "justifyMode": "auto"}}


def loki_bars(pid, title, queries, x, y, w=12, h=7, unit="short", stack=True):
    fc = _fc(unit=unit)
    fc["defaults"]["custom"] = {"drawStyle": "bars", "fillOpacity": 70, "lineWidth": 1,
                                "stacking": {"mode": "normal" if stack else "none", "group": "A"}}
    tgs = [{"refId": chr(ord("A") + i), "datasource": DS_LOKI, "expr": e,
            "legendFormat": lf, "queryType": "range"} for i, (e, lf) in enumerate(queries)]
    return {"id": pid, "type": "timeseries", "title": title,
            "gridPos": {"h": h, "w": w, "x": x, "y": y}, "datasource": DS_LOKI,
            "targets": tgs, "fieldConfig": fc,
            "options": {"legend": {"displayMode": "list", "placement": "bottom", "showLegend": True},
                        "tooltip": {"mode": "multi", "sort": "desc"}}}


HEAP_TH = _thresholds([{"color": "green", "value": None},
                       {"color": "yellow", "value": 0.75},
                       {"color": "red", "value": 0.9}])


# --------------------------------------------------------------------------- #
# Dashboard: Integration Server (JVM via JMX exporter)                          #
# --------------------------------------------------------------------------- #
def build_is_jvm():
    nid = _ids()
    I = '{job="is", role=~"$role", is_instance=~"$is_instance"}'
    panels, y = [], 0
    panels.append(text(nid(),
        "# webMethods Integration Server - JVM\n"
        "JVM health of the Integration Server(s), from the **JMX exporter** "
        "(`jvm_*`, port 9099). Heap, threads, GC and class loading. "
        "Service-level `sag_is_*` metrics need an MSR licence and are not shown here; "
        "OS-level java.exe CPU/memory is on the **Windows Host** dashboard "
        "(windows_exporter `process` collector).", 0, y, 24, 4)); y += 4

    panels.append(row("Reachability & heap", y)); y += 1
    panels.append(stat(nid(), "IS instances up",
        'count(up{job="is"} == 1)', 0, y, 4, 5, unit="short",
        thresholds=_thresholds([{"color": "red", "value": None}, {"color": "green", "value": 1}]),
        display_name="up"))
    panels.append(stat(nid(), "JVM uptime",
        'max(jvm_runtime_uptime_millis%s) / 1000' % I, 4, y, 4, 5, unit="s",
        color_mode="value", display_name="uptime"))
    panels.append(gauge(nid(), "Heap used % (per instance)",
        'jvm_memory_used_bytes{job="is", area="heap", is_instance=~"$is_instance"} '
        '/ jvm_memory_max_bytes{job="is", area="heap", is_instance=~"$is_instance"}',
        8, y, 8, 5, thresholds=HEAP_TH, legend="{{is_instance}}"))
    panels.append(stat(nid(), "Live threads (total)",
        'sum(jvm_threads_current%s)' % I, 16, y, 4, 5, unit="short", color_mode="value",
        display_name="threads"))
    panels.append(stat(nid(), "GC time /min",
        'sum(rate(jvm_gc_collection_seconds_sum%s[5m])) * 60' % I, 20, y, 4, 5,
        unit="s", color_mode="value", display_name="gc s/min")); y += 5

    panels.append(row("Memory", y)); y += 1
    panels.append(timeseries(nid(), "Heap used vs max (bytes)", [
        ('jvm_memory_used_bytes{job="is", area="heap", is_instance=~"$is_instance"}', "{{is_instance}} used"),
        ('jvm_memory_max_bytes{job="is", area="heap", is_instance=~"$is_instance"}', "{{is_instance}} max")],
        0, y, 12, 7, unit="bytes"))
    panels.append(timeseries(nid(), "Non-heap used (bytes)", [
        ('jvm_memory_used_bytes{job="is", area="nonheap", is_instance=~"$is_instance"}', "{{is_instance}} nonheap")],
        12, y, 12, 7, unit="bytes")); y += 7

    panels.append(row("Threads & GC", y)); y += 1
    panels.append(timeseries(nid(), "Threads (live / daemon / peak)", [
        ('jvm_threads_current%s' % I, "{{is_instance}} live"),
        ('jvm_threads_daemon%s' % I, "{{is_instance}} daemon"),
        ('jvm_threads_peak%s' % I, "{{is_instance}} peak")], 0, y, 12, 7, unit="short"))
    panels.append(timeseries(nid(), "GC collections /s (by collector)", [
        ('rate(jvm_gc_collection_seconds_count{job="is", is_instance=~"$is_instance"}[5m])', "{{is_instance}} {{gc}}")],
        12, y, 12, 7, unit="short")); y += 7

    panels.append(row("Classes & buffers", y)); y += 1
    panels.append(timeseries(nid(), "Classes currently loaded", [
        ('jvm_classes_currently_loaded%s' % I, "{{is_instance}}")], 0, y, 12, 7, unit="short"))
    panels.append(timeseries(nid(), "NIO buffer pool used (bytes)", [
        ('jvm_buffer_pool_used_bytes{job="is", is_instance=~"$is_instance"}', "{{is_instance}} {{pool}}")],
        12, y, 12, 7, unit="bytes")); y += 7

    tmpl = [var_query("role", "Role", "jvm_threads_current", "role"),
            var_query("is_instance", "IS host", "jvm_threads_current", "is_instance")]
    return dashboard("gauge-is-jvm", "Gauge - Integration Server (JVM)", panels,
                     ["gauge", "webmethods", "integration-server", "jvm"], templating=tmpl)


# --------------------------------------------------------------------------- #
# Dashboard: Integration Server (native sag_is_* - MSR /metrics endpoint)       #
# --------------------------------------------------------------------------- #
def build_is_sag():
    nid = _ids()
    I = '{job="is", role=~"$role", is_instance=~"$is_instance"}'
    panels, y = [], 0
    panels.append(text(nid(),
        "# webMethods Integration Server - native (`sag_is_*`)\n"
        "Service-level IS metrics from the **native** `/metrics` endpoint on :5555 "
        "(no javaagent / wrapper edit - just enable the endpoint). Richer than the JMX "
        "view: service invocations, latency, errors, sessions, HTTP, threads, GC and "
        "system CPU/disk. **Requires an MSR-licensed IS** (a standard IS returns 404 "
        "on `/metrics` - use the JMX dashboard, or the wm-is-exporter, instead).",
        0, y, 24, 4)); y += 4

    panels.append(row("Reachability & vitals", y)); y += 1
    panels.append(stat(nid(), "IS instances up", 'count(up{job="is"} == 1)', 0, y, 4, 5,
        thresholds=_thresholds([{"color": "red", "value": None}, {"color": "green", "value": 1}]),
        display_name="up"))
    panels.append(stat(nid(), "Uptime", 'max(sag_is_uptime_seconds%s)' % I, 4, y, 4, 5,
        unit="s", color_mode="value", display_name="uptime"))
    panels.append(gauge(nid(), "Heap used % (per instance)",
        'sag_is_used_memory_bytes%s / sag_is_max_memory_bytes%s' % (I, I),
        8, y, 6, 5, thresholds=HEAP_TH, legend="{{is_instance}}"))
    panels.append(stat(nid(), "CPU %", 'max(sag_is_server_proc_cpu_percent%s)' % I, 14, y, 5, 5,
        unit="percent", color_mode="value", display_name="cpu",
        thresholds=PCT_TH))
    panels.append(stat(nid(), "Service errors /min",
        'sum(sag_is_number_service_errors_per_minute%s)' % I, 19, y, 5, 5, unit="short",
        color_mode="value", display_name="errors/min",
        thresholds=_thresholds([{"color": "green", "value": None}, {"color": "yellow", "value": 1}, {"color": "red", "value": 10}]))); y += 5

    panels.append(row("Threads", y)); y += 1
    panels.append(timeseries(nid(), "Request threads in use vs max", [
        ('sag_is_server_threads%s' % I, "{{is_instance}} in use"),
        ('sag_is_server_maxthreads%s' % I, "{{is_instance}} max")], 0, y, 12, 7, unit="short"))
    panels.append(timeseries(nid(), "System threads in use vs max", [
        ('sag_is_system_threads%s' % I, "{{is_instance}} in use"),
        ('sag_is_max_system_threads%s' % I, "{{is_instance}} max")], 12, y, 12, 7, unit="short")); y += 7

    panels.append(row("Memory & GC", y)); y += 1
    panels.append(timeseries(nid(), "JVM memory used vs max (bytes)", [
        ('sag_is_used_memory_bytes%s' % I, "{{is_instance}} used"),
        ('sag_is_max_memory_bytes%s' % I, "{{is_instance}} max")], 0, y, 12, 7, unit="bytes"))
    panels.append(timeseries(nid(), "GC time/s & heap (MB)", [
        ('rate(sag_is_jvm_gc_collection_millis%s[5m])' % I, "{{is_instance}} GC ms/s"),
        ('sag_is_jvm_memory_heap_used_mbytes%s' % I, "{{is_instance}} heap MB")], 12, y, 12, 7, unit="short")); y += 7

    panels.append(row("Services", y)); y += 1
    panels.append(timeseries(nid(), "Service invokes/s & errors/min", [
        ('rate(sag_is_number_service_invokes%s[5m])' % I, "{{is_instance}} invokes/s"),
        ('sag_is_number_service_errors_per_minute%s' % I, "{{is_instance}} errors/min")], 0, y, 12, 7, unit="short"))
    org = [{"id": "organize", "options": {
        "excludeByName": {"Time": True, "__name__": True, "instance": True, "execStat": True,
                          "wm_metric_source": True, "component": True, "host": True, "role": True,
                          "job": True, "is_instance": True, "apiCat": True, "code": True},
        "renameByName": {"service": "Service", "Value": "avg exec ms"}}}]
    panels.append(table(nid(), "Top services by avg exec time (ms)", [
        'topk(15, sag_is_service_requests_avg_exec_millis{job="is", execStat="Y", is_instance=~"$is_instance"})'],
        12, y, 12, 7, unit="ms", transformations=org, sort_by="avg exec ms")); y += 7

    panels.append(row("Sessions, HTTP & system", y)); y += 1
    panels.append(timeseries(nid(), "Sessions / connections", [
        ('sag_is_number_current_connections%s' % I, "{{is_instance}} connections"),
        ('sag_is_current_stateful_sessions%s' % I, "{{is_instance}} stateful sessions")], 0, y, 8, 7, unit="short"))
    panels.append(timeseries(nid(), "HTTP requests & avg time (ms)", [
        ('rate(sag_is_total_http_requests%s[5m])' % I, "{{is_instance}} req/s"),
        ('sag_is_avg_time_per_http_requests%s' % I, "{{is_instance}} avg ms")], 8, y, 8, 7, unit="short"))
    panels.append(timeseries(nid(), "System CPU % & disk used (MB)", [
        ('sag_is_server_proc_cpu_percent%s' % I, "{{is_instance}} JVM cpu%"),
        ('sag_is_server_proc_sys_percent%s' % I, "{{is_instance}} OS cpu%"),
        ('sag_is_server_used_disk_mbytes%s' % I, "{{is_instance}} disk MB")], 16, y, 8, 7, unit="short")); y += 7

    tmpl = [var_query("role", "Role", "sag_is_uptime_seconds", "role"),
            var_query("is_instance", "IS host", "sag_is_uptime_seconds", "is_instance")]
    return dashboard("gauge-is-sag", "Gauge - Integration Server (native sag_is_*)", panels,
                     ["gauge", "webmethods", "integration-server", "sag_is"], templating=tmpl)


# --------------------------------------------------------------------------- #
# Dashboard: Universal Messaging (native sag_um_*)                              #
# --------------------------------------------------------------------------- #
def build_um():
    nid = _ids()
    U = '{job="um", host=~"$host"}'
    panels, y = [], 0
    panels.append(text(nid(),
        "# Universal Messaging\n"
        "UM realm health from the **native** `sag_um_*` exporter (port 9200): "
        "memory, threads, throughput, and **channel / durable / connection health**. "
        "Pick a realm with the **UM host** variable (Realm / Memory / Throughput rows "
        "filter by it); the Client / Queue Health section is fleet-wide.",
        0, y, 24, 4)); y += 4

    panels.append(row("Realm health", y)); y += 1
    panels.append(stat(nid(), "Realm up", 'up{job="um"}', 0, y, 4, 5, unit="short",
        thresholds=_thresholds([{"color": "red", "value": None}, {"color": "green", "value": 1}]),
        display_name="up"))
    panels.append(gauge(nid(), "Heap used %",
        'sag_um_server_memory_heap_usage_bytes%s / sag_um_server_memory_heap_max_bytes%s' % (U, U),
        4, y, 5, 5, thresholds=HEAP_TH))
    panels.append(gauge(nid(), "Direct memory used %",
        'sag_um_server_memory_direct_usage_bytes%s / sag_um_server_memory_direct_max_bytes%s' % (U, U),
        9, y, 5, 5, thresholds=HEAP_TH))
    panels.append(stat(nid(), "Connections",
        'sag_um_server_currentconnections%s' % U, 14, y, 5, 5, unit="short",
        color_mode="value", display_name="connections"))
    panels.append(stat(nid(), "CPU",
        'sag_um_server_cpu_usage_ratio%s' % U, 19, y, 5, 5, unit="percentunit",
        color_mode="value", display_name="cpu")); y += 5

    panels.append(row("Memory & disk", y)); y += 1
    panels.append(timeseries(nid(), "Heap used vs max (bytes)", [
        ('sag_um_server_memory_heap_usage_bytes%s' % U, "used"),
        ('sag_um_server_memory_heap_max_bytes%s' % U, "max")], 0, y, 12, 7, unit="bytes"))
    panels.append(timeseries(nid(), "Disk used vs total (bytes)", [
        ('sag_um_server_disk_usage_bytes%s' % U, "used"),
        ('sag_um_server_disk_total_bytes%s' % U, "total")], 12, y, 12, 7, unit="bytes")); y += 7

    panels.append(row("Throughput & threads", y)); y += 1
    panels.append(timeseries(nid(), "Events published / consumed per sec", [
        ('rate(sag_um_server_publishedevents_total%s[5m])' % U, "published/s"),
        ('rate(sag_um_server_consumedevents_total%s[5m])' % U, "consumed/s")], 0, y, 12, 7, unit="ops"))
    panels.append(timeseries(nid(), "Thread pool", [
        ('sag_um_threadpool_allocated_threads%s' % U, "allocated"),
        ('sag_um_threadpool_idle_threads%s' % U, "idle"),
        ('sag_um_threadpool_queued_tasks%s' % U, "queued"),
        ('sag_um_threadpool_stalled_tasks%s' % U, "stalled")], 12, y, 12, 7, unit="short")); y += 7

    # --- Client / Queue Health (label_replace strips the destinationName= prefix) ---
    panels.append(row("Client / Queue Health - channels, durables, connections", y)); y += 1
    panels.append(stat(nid(), "Stuck channels (events queued, no consumer)",
        'count((sag_um_topic_noofevents{job="um"} > 0) and on(name) '
        '(sag_um_topic_currentconnections{job="um"} == 0)) or vector(0)',
        0, y, 6, 5, unit="short",
        thresholds=_thresholds([{"color": "green", "value": None}, {"color": "red", "value": 1}]),
        display_name="stuck"))
    panels.append(stat(nid(), "Durable backlog (outstanding)",
        'sum(sag_um_topic_durable_outstanding%s)' % U, 6, y, 6, 5, unit="short",
        color_mode="value", display_name="outstanding"))
    panels.append(stat(nid(), "Subscribed channels",
        'count(sag_um_topic_currentconnections{job="um"} > 0) or vector(0)',
        12, y, 6, 5, unit="short", color_mode="value", display_name="channels"))
    panels.append(stat(nid(), "Publish rate (evt/s)",
        'sum(rate(sag_um_server_publishedevents_total%s[5m]))' % U, 18, y, 6, 5,
        unit="ops", color_mode="value", display_name="pub/s")); y += 5

    org_ch = [{"id": "organize", "options": {
        "excludeByName": {"Time": True, "__name__": True, "name": True, "instance": True,
                          "component": True, "job": True},
        "renameByName": {"channel": "Channel", "Value": "events queued"}}}]
    panels.append(table(nid(), "Stuck channels - events queued, zero consumers", [
        'label_replace((sag_um_topic_noofevents{job="um"} > 0) and on(name) '
        '(sag_um_topic_currentconnections{job="um"} == 0), "channel", "$1", "name", "destinationName=(.*)")'],
        0, y, 12, 8, transformations=org_ch, sort_by="events queued"))
    org_sub = [{"id": "organize", "options": {
        "excludeByName": {"Time": True, "__name__": True, "name": True, "instance": True,
                          "component": True, "job": True},
        "renameByName": {"channel": "Channel", "Value": "consumers"}}}]
    panels.append(table(nid(), "Channel subscribers (0 = nobody draining)", [
        'label_replace(sag_um_topic_currentconnections{job="um"}, "channel", "$1", "name", "destinationName=(.*)")'],
        12, y, 12, 8, transformations=org_sub, sort_by="consumers")); y += 8

    return dashboard("gauge-um", "Gauge - Universal Messaging", panels,
                     ["gauge", "webmethods", "universal-messaging"],
                     templating=[var_query("host", "UM host", "sag_um_server_currentconnections", "host")])


PCT_TH = _thresholds([{"color": "green", "value": None},
                      {"color": "yellow", "value": 75},
                      {"color": "red", "value": 90}])


# --------------------------------------------------------------------------- #
# Dashboard: Linux host (node_exporter)                                         #
# --------------------------------------------------------------------------- #
def build_linux_host():
    nid = _ids()
    H = '{job="node", host=~"$host"}'
    panels, y = [], 0
    panels.append(text(nid(),
        "# Linux Host\n"
        "Host metrics from **node_exporter** (`node_*`, port 9100) for the IS / UM "
        "Linux hosts. Use the **Host** variable to focus one box. The `host` label is "
        "set per target in prometheus.yml (see INSTALL.md); filesystem panels use the "
        "default-on filesystem collector.",
        0, y, 24, 4)); y += 4

    panels.append(row("CPU / Memory / Uptime", y)); y += 1
    panels.append(gauge(nid(), "CPU busy % (worst host)",
        'max(100 * (1 - avg by (host) (rate(node_cpu_seconds_total{mode="idle", host=~"$host"}[5m]))))',
        0, y, 6, 6, unit="percent", minv=0, maxv=100, thresholds=PCT_TH))
    panels.append(gauge(nid(), "Memory used % (worst host)",
        'max(100 * (1 - node_memory_MemAvailable_bytes%s / node_memory_MemTotal_bytes%s))' % (H, H),
        6, y, 6, 6, unit="percent", minv=0, maxv=100, thresholds=PCT_TH))
    panels.append(stat(nid(), "Uptime (min across hosts)",
        'min(time() - node_boot_time_seconds%s)' % H, 12, y, 4, 6, unit="s",
        color_mode="value", display_name="uptime"))
    panels.append(stat(nid(), "Load1 (max)", 'max(node_load1%s)' % H, 16, y, 4, 6, unit="short",
        color_mode="value", display_name="load1"))
    panels.append(stat(nid(), "Open FDs (max)",
        'max(node_filefd_allocated%s)' % H, 20, y, 4, 6, unit="short", color_mode="value",
        display_name="fds")); y += 6

    panels.append(row("CPU & memory", y)); y += 1
    panels.append(timeseries(nid(), "CPU busy % per host", [
        ('100 * (1 - avg by (host) (rate(node_cpu_seconds_total{mode="idle", host=~"$host"}[5m])))', "{{host}}")],
        0, y, 12, 7, unit="percent"))
    panels.append(timeseries(nid(), "Memory total / available (bytes)", [
        ('node_memory_MemTotal_bytes%s' % H, "{{host}} total"),
        ('node_memory_MemAvailable_bytes%s' % H, "{{host}} available")], 12, y, 12, 7, unit="bytes")); y += 7

    panels.append(row("Disk & network", y)); y += 1
    panels.append(timeseries(nid(), "Filesystem used % per mount", [
        ('100 * (1 - node_filesystem_avail_bytes{job="node", host=~"$host", fstype!~"tmpfs|overlay|squashfs|devtmpfs"} '
         '/ node_filesystem_size_bytes{job="node", host=~"$host", fstype!~"tmpfs|overlay|squashfs|devtmpfs"})', "{{host}} {{mountpoint}}")],
        0, y, 12, 7, unit="percent"))
    panels.append(timeseries(nid(), "Disk IO (bytes/s)", [
        ('rate(node_disk_read_bytes_total{host=~"$host"}[5m])', "{{host}} {{device}} read"),
        ('rate(node_disk_written_bytes_total{host=~"$host"}[5m])', "{{host}} {{device}} write")],
        12, y, 12, 7, unit="Bps")); y += 7

    panels.append(row("Network & load", y)); y += 1
    panels.append(timeseries(nid(), "Network throughput (bytes/s, excl. lo)", [
        ('rate(node_network_receive_bytes_total{host=~"$host", device!="lo"}[5m])', "{{host}} {{device}} in"),
        ('rate(node_network_transmit_bytes_total{host=~"$host", device!="lo"}[5m])', "{{host}} {{device}} out")],
        0, y, 12, 7, unit="Bps"))
    panels.append(timeseries(nid(), "Load average (1 / 5 / 15m)", [
        ('node_load1%s' % H, "{{host}} 1m"),
        ('node_load5%s' % H, "{{host}} 5m"),
        ('node_load15%s' % H, "{{host}} 15m")], 12, y, 12, 7, unit="short")); y += 7

    tmpl = [var_query("host", "Host", "node_boot_time_seconds", "host")]
    return dashboard("gauge-linux-host", "Gauge - Linux Host", panels,
                     ["gauge", "linux", "host"], templating=tmpl)


# --------------------------------------------------------------------------- #
# Dashboard: Overview (all three sources)                                       #
# --------------------------------------------------------------------------- #
def build_overview():
    nid = _ids()
    panels, y = [], 0
    panels.append(text(nid(),
        "# Gauge - Overview\n"
        "Single pane for the webMethods estate: **Integration Server**, **Universal "
        "Messaging** (`sag_um_*`), and the **Linux host(s)** (`node_*`). Click through "
        "to each dashboard for detail.",
        0, y, 24, 4)); y += 4

    panels.append(row("Reachability", y)); y += 1
    panels.append(state_timeline(nid(), "Targets up/down", [
        ('up{job=~"is|um|node"}', "{{job}} {{host}}{{is_instance}}")], 0, y, 18, 6))
    panels.append(stat(nid(), "IS up", 'count(up{job="is"} == 1)', 18, y, 2, 6, unit="short",
        thresholds=_thresholds([{"color": "red", "value": None}, {"color": "green", "value": 1}]), display_name="IS"))
    panels.append(stat(nid(), "UM up", 'up{job="um"}', 20, y, 2, 6, unit="short",
        thresholds=_thresholds([{"color": "red", "value": None}, {"color": "green", "value": 1}]), display_name="UM"))
    panels.append(stat(nid(), "Hosts up", 'count(up{job="node"} == 1)', 22, y, 2, 6, unit="short",
        thresholds=_thresholds([{"color": "red", "value": None}, {"color": "green", "value": 1}]), display_name="hosts")); y += 6

    panels.append(row("Linux host vitals (worst across hosts)", y)); y += 1
    panels.append(gauge(nid(), "CPU busy %",
        'max(100 * (1 - avg by (host) (rate(node_cpu_seconds_total{mode="idle"}[5m]))))',
        0, y, 6, 6, unit="percent", minv=0, maxv=100, thresholds=PCT_TH))
    panels.append(gauge(nid(), "Memory used %",
        'max(100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes))',
        6, y, 6, 6, unit="percent", minv=0, maxv=100, thresholds=PCT_TH))
    panels.append(gauge(nid(), "Worst filesystem used %",
        'max(100 * (1 - node_filesystem_avail_bytes{fstype!~"tmpfs|overlay|squashfs|devtmpfs"} '
        '/ node_filesystem_size_bytes{fstype!~"tmpfs|overlay|squashfs|devtmpfs"}))',
        12, y, 6, 6, unit="percent", minv=0, maxv=100, thresholds=PCT_TH))
    panels.append(stat(nid(), "Host uptime (min)",
        'min(time() - node_boot_time_seconds)', 18, y, 6, 6, unit="s",
        color_mode="value", display_name="uptime")); y += 6

    panels.append(row("webMethods vitals", y)); y += 1
    panels.append(gauge(nid(), "IS heap used % (worst instance)",
        'max(jvm_memory_used_bytes{job="is", area="heap"} / jvm_memory_max_bytes{job="is", area="heap"})',
        0, y, 6, 6, thresholds=HEAP_TH))
    panels.append(gauge(nid(), "UM heap used %",
        'sag_um_server_memory_heap_usage_bytes{job="um"} / sag_um_server_memory_heap_max_bytes{job="um"}',
        6, y, 6, 6, thresholds=HEAP_TH))
    panels.append(stat(nid(), "UM connections",
        'sag_um_server_currentconnections{job="um"}', 12, y, 6, 6, unit="short",
        color_mode="value", display_name="connections"))
    panels.append(stat(nid(), "UM stuck channels",
        'count((sag_um_topic_noofevents{job="um"} > 0) and on(name) '
        '(sag_um_topic_currentconnections{job="um"} == 0)) or vector(0)',
        18, y, 6, 6, unit="short",
        thresholds=_thresholds([{"color": "green", "value": None}, {"color": "red", "value": 1}]),
        display_name="stuck")); y += 6

    return dashboard("gauge-overview", "Gauge - Overview", panels,
                     ["gauge", "overview"])


# --------------------------------------------------------------------------- #
# Dashboard: Logs (Loki - shipped by Grafana Alloy)                             #
# --------------------------------------------------------------------------- #
def build_logs():
    nid = _ids()
    # $search is a free-text (regex) line filter; empty matches everything.
    SRCH = '|~ "(?i)$search"'
    ALL = '{component=~"integration-server|universal-messaging"}'
    panels, y = [], 0
    panels.append(text(nid(),
        "# Logs\n"
        "webMethods logs shipped by **Grafana Alloy** into **Loki**: Integration "
        "Server, Universal Messaging and JVM wrapper logs. Use the **Search** box "
        "(top-right) for a case-insensitive regex line filter. `level` is a label, "
        "so you can chart error rates and filter to errors.",
        0, y, 24, 4)); y += 4

    panels.append(row("Volume & errors", y)); y += 1
    panels.append(loki_stat(nid(), "ERROR/FATAL lines (1h)",
        'sum(count_over_time(%s | level=~"ERROR|FATAL"[1h]))' % ALL, 0, y, 6, 5,
        thresholds=_thresholds([{"color": "green", "value": None}, {"color": "yellow", "value": 1}, {"color": "red", "value": 50}]),
        display_name="errors 1h"))
    panels.append(loki_stat(nid(), "WARN lines (1h)",
        'sum(count_over_time(%s | level=~"WARN|WARNING"[1h]))' % ALL, 6, y, 6, 5,
        display_name="warnings 1h"))
    panels.append(loki_bars(nid(), "Log volume by level (per interval)", [
        ('sum by (level) (count_over_time(%s[$__interval]))' % ALL, "{{level}}")],
        12, y, 12, 5, unit="short")); y += 5

    panels.append(row("Errors & warnings (all sources)", y)); y += 1
    panels.append(logs_panel(nid(), "ERROR / WARN / FATAL - IS + UM",
        '{component=~"integration-server|universal-messaging", level=~"ERROR|WARN|WARNING|FATAL"} %s' % SRCH,
        0, y, 24, 9)); y += 9

    panels.append(row("Integration Server logs", y)); y += 1
    panels.append(logs_panel(nid(), "IS logs (server / error / session / stats)",
        '{component="integration-server", logset="is"} %s' % SRCH, 0, y, 24, 10)); y += 10

    panels.append(row("Universal Messaging logs", y)); y += 1
    panels.append(logs_panel(nid(), "UM realm logs",
        '{component="universal-messaging", logset="um"} %s' % SRCH, 0, y, 24, 9)); y += 9

    panels.append(row("JVM wrapper logs (start / OOM / crash / restart)", y)); y += 1
    panels.append(logs_panel(nid(), "Wrapper logs - IS + UM",
        '{logset="wrapper"} %s' % SRCH, 0, y, 24, 8)); y += 8

    tmpl = [var_textbox("search", "Search")]
    return dashboard("gauge-logs", "Gauge - Logs", panels, ["gauge", "logs", "loki"],
                     templating=tmpl)


# --------------------------------------------------------------------------- #
# main                                                                          #
# --------------------------------------------------------------------------- #
BUILDERS = [
    ("gauge-overview.json", build_overview),
    ("gauge-is-sag.json", build_is_sag),   # native sag_is_* (MSR) - the richer IS view
    ("gauge-is-jvm.json", build_is_jvm),    # JMX jvm_* (any licence) - JVM-level
    ("gauge-um.json", build_um),
    ("gauge-linux-host.json", build_linux_host),
    ("gauge-logs.json", build_logs),        # Loki logs (needs Loki + Alloy)
]


def main():
    os.makedirs(OUT, exist_ok=True)
    for fn, fn_build in BUILDERS:
        d = fn_build()
        path = os.path.join(OUT, fn)
        with open(path, "w") as f:
            json.dump(d, f, indent=2)
        print("  wrote %s (%d panels)" % (fn, len(d["panels"])))


if __name__ == "__main__":
    main()
