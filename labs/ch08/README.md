# Lab ch08 — See one interaction all the way down (Section 8.7)

```bash
python labs/ch08/flip_local.py --sample-rate 0.05 --rpm 60
```

1. One interaction as a trace: the SDK span (GenAI conventions, cost, no content) joined
   to the gateway's metering event by trace ID.
2. Judge calibration on a twenty-case golden set (agreement and Cohen's kappa).
3. The planted incident: the alias flips to a weaker model with no deploy and no error;
   the regression detector alarms with trace IDs. Time is in simulated minutes at the
   given traffic rate; the mock models differ more than real ones do, so local detection
   is faster than Table 8.8's reference run.

AWS track: deploy the ADOT collector with `observability/collector/adot-collector.yaml`
(traces to the CloudWatch OTLP endpoint) and point the SDK's exporter at it. A
Terraform module for the collector and the LLM-observability layer is not in this
release (STATUS.md).
