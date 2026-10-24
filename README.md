# AI Platform Engineering — Companion Repository

**Optional companion material for the book**
> *AI Platform Engineering* — Miguel Brito · Book 3 of the *Architecture for AI* series

[![CI](https://github.com/miguelcpsbrito/ai-platform-engineering/actions/workflows/ci.yml/badge.svg)](https://github.com/miguelcpsbrito/ai-platform-engineering/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)

The book stands on its own: every exercise is described in full in the text, and nothing
in it requires this repository. What you find here is one worked version of that
material — Terraform modules for the reference architecture of Chapter 3, the gateway of
Chapter 4, the tenancy, FinOps, observability, governance and agent controls of Chapters
5–12, the blueprints of Chapter 7, and ready-made versions of the chapter exercises.

Use it if you want to compare your own solution, skip some typing, or run the exercises
without building them from scratch. It is provided as-is, with no promise of maintenance.

> [STATUS.md](STATUS.md) says, module by module, what is implemented, what is tested
> offline, and what has been applied to a real AWS account.

---

## Two ways to run it

**Local (no AWS account, no cost).** Every exercise from Chapter 4 on has a local track
that runs the reference gateway with simulated models, DuckDB for the FinOps pipeline,
and a local Postgres for the row-level-security track. This is what CI runs.

```bash
python -m pip install -r requirements-dev.txt
make test          # unit tests, leakage, conformance, restore — every module
make labs-local    # the local tracks of the exercises for ch04, ch06, ch07, ch09, ch10, ch12
```

**AWS (a sandbox account in a lab OU).** The minimal platform of the Section 3.6
exercise — `org`, `network`, `identity`, and the gateway stub — deploys with the
commands in [`labs/ch03`](labs/ch03/README.md), proves its claims with `prove.sh`, and
tears down with `teardown`. Check the AWS pricing pages and service quotas before you
deploy; the numbers in this repository are symbolic and dated.

---

## Structure

```
ai-platform-engineering/
  org/            network/        identity/       gateway/
  tenancy/        finops/         observability/  governance/
  blueprints/     agents/         portal/         sre/
  labs/ch03 … ch12    examples/    docs/    tests/    tools/
```

| Module | Implements | Book |
|---|---|---|
| [`org/`](org/) | OUs, the three AI SCPs, tag policy | 3.1 |
| [`network/`](network/) | Hub VPC, private endpoints, DNS Firewall egress control, optional Network Firewall and Transit Gateway | 3.3 |
| [`identity/`](identity/) | Gateway role, tenant permission boundary, model approver, break-glass, Identity Center | 3.4 |
| [`gateway/`](gateway/) | Alias map, tenant records, reference custom gateway, LiteLLM renderer, fault layer, Terraform (profiles, stub, proxy on EKS) | 4, 5.2, 9.5 |
| [`tenancy/`](tenancy/) | Tenant schema, retrieval library (in-memory, pgvector + RLS, OpenSearch), registry and baseline Terraform | 5 |
| [`finops/`](finops/) | Athena schema, allocation SQL with rule versions, reconciliation, anomaly paging, weekly message, CUR 2.0 export and metering stream, model-plane TCO | 6 |
| [`observability/`](observability/) | Platform SDK (OTel GenAI conventions), evaluation harness, regression detector, ADOT collector config | 8 |
| [`governance/`](governance/) | Intake tiering, guardrail profiles, red-team corpus and runner, data-class matrix, deletion pipeline, audit record | 10 |
| [`blueprints/`](blueprints/) | RAG, agent, chatbot and batch templates (Backstage scaffolder format) | 7.4 |
| [`agents/`](agents/) | Tool registry, budgets, kill switches, approvals, task-scoped credentials | 12 |
| [`portal/`](portal/) | The thin portal (template execution, catalog, update machinery) | 7.3 |
| [`sre/runbooks/`](sre/runbooks/) | RB-1 to RB-5 | 9.5 |
| [`tests/`](tests/) | Estate-level suites: leakage, conformance, restore, live SCP | — |

## Exercises

Ready-made versions of the exercises the book describes. The `labs/` folder name is kept
for brevity.

| Folder | Book exercise | Local track | AWS track |
|---|---|---|---|
| [ch03](labs/ch03/) | 3.6 Minimal platform | — | `prove.sh` + `teardown` |
| [ch04](labs/ch04/) | 4.9 Prove the anatomy | `prove_local.py` | proxy on EKS |
| [ch05](labs/ch05/) | 5.7 Build it, then try to break it | `pytest tests/leakage` | OpenSearch Serverless |
| [ch06](labs/ch06/) | 6.8 Answer the CFO in one query | `run_local.py` | Data Exports + Athena |
| [ch07](labs/ch07/) | 7.7 Walk it, time it, change it | `walk_local.py` | Backstage track |
| [ch08](labs/ch08/) | 8.7 See one interaction all the way down | `pytest observability` + ch09 phase 1 | ADOT + CloudWatch |
| [ch09](labs/ch09/) | 9.7 The scripted game day | `gameday_local.py` | on the ch04 estate |
| [ch10](labs/ch10/) | 10.8 Attack it, then prove the paperwork | `run_local.py` | ApplyGuardrail |
| [ch12](labs/ch12/) | Agent readiness | `drill_local.py` | AgentCore |

## Requirements

Python 3.11+, Terraform 1.6+ (or OpenTofu 1.8+), AWS provider 6.x. Optional: Postgres 16
with pgvector for the RLS track (`PLATFORM_PG_DSN`), Docker for the CI service container.

## Issues

Issues and pull requests are welcome but not guaranteed a response. See
[CONTRIBUTING.md](CONTRIBUTING.md).

## License

MIT — see [LICENSE](LICENSE). Model prices and service quotas in this repository are
symbolic and dated; the AWS documentation is the authority on any number.
