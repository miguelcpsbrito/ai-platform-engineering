# labs/ch04 — CURRENT (release 0.1.0, October 2026)

Local track: no cost. AWS track, on top of ch03 (symbolic, us-east-1):

| Item | Per day |
|---|---|
| EKS cluster control plane ($0.10/hour) | ≈ $2.40 |
| EKS Auto Mode nodes (3 small general-purpose nodes) + Auto Mode fee | ≈ $3–5 |
| Aurora Serverless v2, auto-pause enabled (0 ACU floor) | ≈ $0–2 |
| ElastiCache Serverless (Valkey) minimum | ≈ $2 |
| Internal ALB | ≈ $0.60 |
| **Total with ch03** | **≈ $13–17/day** |

Pinned versions: LiteLLM chart 1.1.3, image v1.85.1 (`gateway/terraform/proxy/app`);
the rendered config is tested against LiteLLM 1.85.1 in CI.

Last verified on AWS: **not yet** — see STATUS.md.
