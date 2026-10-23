# Lab ch10 — Attack it, then prove the paperwork (Section 10.8)

```bash
python labs/ch10/run_local.py
```

Part one: the three guardrail layers against `governance/redteam/corpus.yaml`, with the
per-family scorecard and the cases layer 1 misses on its own. Part two: a regulated
request against `standard` is blocked by the gateway's data-class matrix; reclassified,
it flows. Part three: plant–delete–hunt a synthetic subject with a completion report,
then the audit drill, timed.

AWS track: apply `governance/guardrails`, pass its `guardrails` output to the gateway as
`PLATFORM_GUARDRAILS`, and run the red team with
`platform_governance.BedrockLayer1(<id>, <version>)` as layer 1.
