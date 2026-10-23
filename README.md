# wm-monitoring-grafana/Users/cobusboshoff/dev/wm-monitoring-grafana/windows-install/INSTALL.md

These are the exporter.resource_attributes lines for the 8 staging and prod ESB/BPM Integration Server JVMs. They use the same key set as before, and each one goes in that host’s <install_root>/E2EMonitoring/agent/config/agent.config.

Staging

pvbjhbvlwmesba3

exporter.resource_attributes=${SW_AGENT_OTEL_RESOURCE_ATTRIBUTES:webmethods.product#is,webmethods.cluster#esb,webmethods.site#jhb,webmethods.instance#jhb-esb-a,deployment.environment.name#staging,instrumentation.source#webmethods-e2em,trace.layer#business}

pvbmapvlwmesba3

exporter.resource_attributes=${SW_AGENT_OTEL_RESOURCE_ATTRIBUTES:webmethods.product#is,webmethods.cluster#esb,webmethods.site#map,webmethods.instance#map-esb-a,deployment.environment.name#staging,instrumentation.source#webmethods-e2em,trace.layer#business}

pvbjhbvlwmbpma3

exporter.resource_attributes=${SW_AGENT_OTEL_RESOURCE_ATTRIBUTES:webmethods.product#is,webmethods.cluster#bpm,webmethods.site#jhb,webmethods.instance#jhb-bpm-a,deployment.environment.name#staging,instrumentation.source#webmethods-e2em,trace.layer#business}

pvbmapvlwmbpma3

exporter.resource_attributes=${SW_AGENT_OTEL_RESOURCE_ATTRIBUTES:webmethods.product#is,webmethods.cluster#bpm,webmethods.site#map,webmethods.instance#map-bpm-a,deployment.environment.name#staging,instrumentation.source#webmethods-e2em,trace.layer#business}

Prod

pvbjhbvlwmesba4

exporter.resource_attributes=${SW_AGENT_OTEL_RESOURCE_ATTRIBUTES:webmethods.product#is,webmethods.cluster#esb,webmethods.site#jhb,webmethods.instance#jhb-esb-a,deployment.environment.name#prod,instrumentation.source#webmethods-e2em,trace.layer#business}

pvbmapvlwmesba4

exporter.resource_attributes=${SW_AGENT_OTEL_RESOURCE_ATTRIBUTES:webmethods.product#is,webmethods.cluster#esb,webmethods.site#map,webmethods.instance#map-esb-a,deployment.environment.name#prod,instrumentation.source#webmethods-e2em,trace.layer#business}

pvbjhbvlwmbpma4

exporter.resource_attributes=${SW_AGENT_OTEL_RESOURCE_ATTRIBUTES:webmethods.product#is,webmethods.cluster#bpm,webmethods.site#jhb,webmethods.instance#jhb-bpm-a,deployment.environment.name#prod,instrumentation.source#webmethods-e2em,trace.layer#business}

pvbmapvlwmbpma4

exporter.resource_attributes=${SW_AGENT_OTEL_RESOURCE_ATTRIBUTES:webmethods.product#is,webmethods.cluster#bpm,webmethods.site#map,webmethods.instance#map-bpm-a,deployment.environment.name#prod,instrumentation.source#webmethods-e2em,trace.layer#business}

Before you paste these in:

No service.name: don’t add it. The agent sets it for each flow while it runs.
prod vs production: I used prod. If your Dynatrace metric configs or saved queries already say production, use that instead. Traces and metrics only join up when both sides carry exactly the same value.
Old keys still in use on staging: staging traces carry the older keys (webmethods.component.type, webmethods.instance.node) today. Any existing staging filters built on those keys will stop matching once these lines take effect. Add webmethods.component.type#integration-server back temporarily if you need a transition period.
Restart needed: the agent only reads agent.config when the JVM starts, so each Integration Server needs a restart to pick up the change.
Same line on every host: the 8 lines differ only in cluster, site, instance and environment. If you’d rather keep agent.config the same everywhere, put the per-host value in the SW_AGENT_OTEL_RESOURCE_ATTRIBUTES environment variable; it overrides the default inside ${…}. I haven’t tested setting it through custom_wrapper.conf on these hosts.
