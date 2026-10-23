# agents/ — the next layer (Chapter 12)

- `registry/tools.yaml` — the tool and MCP registry (Figure 12.2): owner, action class, reversibility, tenant and tier allow-lists, per-task limits, approval channel.
- `platform_agents/` — `Runtime.call_tool` applies, at every step boundary: kill switch → step and spend budget → registry policy → per-task tool limit → approval for consequential tools. Approvals are signed by the channel and bound to the exact arguments.
- `platform_agents/credentials.py` — task-scoped STS sessions with a session policy and delegation tags (Figure 12.3).
