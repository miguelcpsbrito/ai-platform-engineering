# observability/ — quality as an operational signal (Chapter 8)

- `platform_sdk/` — `Gateway.chat` opens the span with GenAI semantic conventions plus `platform.*` attributes and propagates trace context; content never goes on spans (Figure 8.3).
- `platform_eval/` — judges (mock for labs, a model judge through the gateway), deterministic sampling, the regression detector, calibration (agreement, Cohen's kappa), and the suite runner behind the `platform-eval` CLI used by blueprint pipelines.
- `collector/adot-collector.yaml` — ADOT config: content attributes dropped, traces to the CloudWatch OTLP endpoint with SigV4, metrics via EMF.

`pip install ./observability` installs `platform-eval` (and the SDK).
- `dashboards/*.yaml` — the five persona dashboards of Section 8.6 as panel specifications (title, source, query), all joined on the trace ID. Rendering them in CloudWatch or Grafana is deployment-specific and not in this release.
