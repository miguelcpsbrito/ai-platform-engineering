# Lab ch09 — The scripted game day (Section 9.7)

```bash
python labs/ch09/gameday_local.py               # scripted responder
python labs/ch09/gameday_local.py --interactive # you decide at each step
```

Phase 1 degrades `standard` in the primary region (latency plus a silent swap to a
weaker model); the level-3 detector separates "slower" from "worse"; you execute RB-2
step 4 (`sre/runbooks/RB-2-model-got-worse.md`). Phase 2 saturates the pool; the
degradation ladder moves opted-in tenants to `fast` and sheds the rest. Scores:
detection→classification, classification→mitigation, comms latency. The run ends with a
postmortem draft from `docs/templates/postmortem.md`, timeline included.
