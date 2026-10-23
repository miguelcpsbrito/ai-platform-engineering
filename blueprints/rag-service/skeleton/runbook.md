# Runbook — ${{ values.name }}

Owner: ${{ values.tenant }} · Platform escalation: #ai-platform-oncall

| Alert | First check | Platform runbook |
|---|---|---|
| Quality regression (level 3) | Trace IDs in the alert; did the alias change? | RB-2 (alias pin) |
| Fallback rate high | Gateway status page; region health | RB-1 |
| Spend anomaly | Feature and conversation in the page; retry loop? | RB-3 |
| Tenant 429s | Quota dashboard; raise request link in the 429 body | RB-5 |
