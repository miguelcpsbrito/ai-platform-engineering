# Lab ch12 — Agent readiness (Section 12.4)

```bash
python labs/ch12/drill_local.py
```

The runaway of the Chapter 12 war story, stopped by a per-task budget; a consequential
tool blocked until a human approval the agent cannot forge; both kill switches pulled
mid-trajectory. Then fill [readiness.md](readiness.md) with the evidence.

AWS track: AgentCore Runtime and Gateway implement these primitives; this release has no
AgentCore module (STATUS.md). `agents/platform_agents/credentials.py` produces the
task-scoped STS sessions of Figure 12.3 for any runtime.
