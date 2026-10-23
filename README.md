# AI Platform Engineering — Reference Repository

**Companion repository for the book**
> *AI Platform Engineering* — Miguel Brito

[![CI](https://github.com/miguelcpsbrito/ai-platform-engineering/actions/workflows/ci.yml/badge.svg)](https://github.com/miguelcpsbrito/ai-platform-engineering/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

This is the deployable half of the book: the Terraform modules behind the reference
architecture of Chapter 3, the gateway of Chapter 4, the tenancy, FinOps, observability,
governance and agent controls of Chapters 5–12, the blueprints of Chapter 7, and a lab
per chapter. Every claim the book makes falsifiable is a test here.

> **Read [STATUS.md](STATUS.md) first.** It says, module by module, what is implemented,
> what is tested offline in CI, and what has been applied to a real AWS account. The
> book describes the target; this file describes the truth today.

---

## Two ways to run it

**Local (no AWS account, no cost).** Every lab from Chapter 4 on has a local track that
runs the reference gateway with simulated models, DuckDB for the FinOps pipeline, and a
local Postgres for the row-level-security track. This is what CI runs.

```bash
python -m pip install -r requirements-dev.txt
make test          # unit tests, leakage, conformance, restore — every module
make labs-local    # the local tracks of labs ch04, ch06, ch07, ch09, ch10, ch12
```

**AWS (a sandbox account in a lab OU).** The minimal platform of Section 3.6 — `org`,
`network`, `identity`, and the gateway stub — deploys with the commands in
[`labs/ch03`](labs/ch03/README.md), proves its five claims with `prove.sh`, and tears
down with `teardown`. Costs and regional prerequisites live in each lab's `CURRENT.md`,
which supersedes any number printed in the book.

---

## Structure

```
ai-platform-engineering/
  org/            network/        identity/       gateway/
  tenancy/        finops/         observability/  governance/
  blueprints/     agents/         portal/         sre/
  labs/ch03 … ch12    examples/    docs/    tests/    tools/
```

| Module | Implements | Book | Labs |
|---|---|---|---|
| [`org/`](org/) | OUs, the three AI SCPs, tag policy | 3.1 | ch03 |
| [`network/`](network/) | Hub VPC, private endpoints, DNS Firewall egress control, optional Network Firewall | 3.3 | ch03 |
| [`identity/`](identity/) | Gateway role, tenant permission boundary, model approver, break-glass, Identity Center | 3.4 | ch03 |
| [`gateway/`](gateway/) | Alias map, tenant records, reference custom gateway, LiteLLM renderer, fault layer, Terraform (profiles, stub, proxy on EKS) | 4, 5.2, 9.5 | ch03, ch04, ch09 |
| [`tenancy/`](tenancy/) | Tenant schema, retrieval library (in-memory, pgvector + RLS, OpenSearch), registry and baseline Terraform | 5 | ch05 |
| [`finops/`](finops/) | Athena schema, allocation SQL with rule versions, reconciliation, anomaly paging, weekly message, CUR 2.0 export and metering stream, model-plane TCO | 6 | ch06 |
| [`observability/`](observability/) | Platform SDK (OTel GenAI conventions), evaluation harness, regression detector, ADOT collector config | 8 | ch08, ch09 |
| [`governance/`](governance/) | Intake tiering, guardrail profiles, red-team corpus and runner, data-class matrix, deletion pipeline, audit record | 10 | ch10 |
| [`blueprints/`](blueprints/) | RAG, agent, chatbot and batch templates (Backstage scaffolder format) | 7.4 | ch07 |
| [`agents/`](agents/) | Tool registry, budgets, kill switches, approvals, task-scoped credentials | 12 | ch12 |
| [`portal/`](portal/) | The thin portal (template execution, catalog, update machinery) | 7.3 | ch07 |
| [`sre/runbooks/`](sre/runbooks/) | RB-1 to RB-5 | 9.5 | ch09 |
| [`tests/`](tests/) | Estate-level suites: leakage, conformance, restore, live SCP | A.3 | all |

## Labs

| Lab | Title | Local track | AWS track |
|---|---|---|---|
| [ch03](labs/ch03/) | Minimal platform | — | `prove.sh` + `teardown` |
| [ch04](labs/ch04/) | Prove the anatomy | `prove_local.py` | proxy on EKS |
| [ch05](labs/ch05/) | Build it, then try to break it | `pytest tests/leakage` | OpenSearch Serverless |
| [ch06](labs/ch06/) | Answer the CFO in one query | `run_local.py` | Data Exports + Athena |
| [ch07](labs/ch07/) | Walk it, time it, change it | `walk_local.py` | Backstage track |
| [ch08](labs/ch08/) | See one interaction all the way down | `pytest observability` + ch09 phase 1 | ADOT + CloudWatch |
| [ch09](labs/ch09/) | The scripted game day | `gameday_local.py` | on the ch04 estate |
| [ch10](labs/ch10/) | Attack it, then prove the paperwork | `run_local.py` | ApplyGuardrail |
| [ch12](labs/ch12/) | Agent readiness | `drill_local.py` | AgentCore |

## Requirements

Python 3.11+, Terraform 1.6+ (or OpenTofu 1.8+), AWS provider 6.x. Optional: Postgres 16
with pgvector for the RLS track (`PLATFORM_PG_DSN`), Docker for the CI service container.

## Contributing

Issues for defects and drift (a quota change that breaks a lab is a bug), pull requests
for fixes and new red-team cases, discussions for war stories. A module change ships with
its test; nothing merges that makes a chapter's claim untrue without an erratum. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE). Model prices and service quotas in this repository are
symbolic and dated; check the AWS pricing pages before you rely on them.
