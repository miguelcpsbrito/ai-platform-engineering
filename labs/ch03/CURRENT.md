# labs/ch03 — CURRENT (release 0.1.0, October 2026)

This file supersedes any number printed in the book. Symbolic list prices, us-east-1.

| Item | Unit price | Lab quantity | Per day |
|---|---|---|---|
| Interface VPC endpoints (bedrock-runtime, bedrock, sts, logs, secretsmanager, monitoring) | ≈ $0.01 per endpoint-hour per AZ | 6 × 2 AZ | ≈ $2.90 |
| NAT gateway | ≈ $0.045/hour + $0.045/GB | 2 | ≈ $2.20 |
| DNS Firewall | $0.60 per million queries | lab traffic | < $0.01 |
| Lambda (gateway stub, probe) | per request | proofs only | < $0.01 |
| Bedrock on-demand tokens | see `gateway/prices.yaml` | a few calls | < $0.05 |
| **Default track total** | | | **≈ $5/day** |
| Network Firewall track (optional) | ≈ $0.395/hour per AZ + $0.065/GB | 2 AZ | + ≈ $19/day |

Regional prerequisites: model access for `us.anthropic.claude-sonnet-4-6`,
`us.amazon.nova-pro-v1:0` and `us.amazon.nova-micro-v1:0` (geographic profiles; requests
may be served from any US region of the profile). Interface endpoint availability for
`bedrock-runtime` in both lab AZs.

Last verified on AWS: **not yet** — see STATUS.md.
