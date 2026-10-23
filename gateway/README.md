# gateway/ — one point of passage (Chapter 4, Sections 5.2 and 9.5)

| Path | What |
|---|---|
| `aliases.yaml` | The alias map of Figure 4.3, resolved per environment, with the fallback chain |
| `env/<env>.yaml` | Per-environment overlays (`local` = simulated models for labs) |
| `contracts/*.yaml` | Alias contracts (Figure 4.4), including `data_classes_allowed` for the matrix |
| `tenants/*.yaml` | Tenant records (Figure 5.3), validated by `tenancy/schema` |
| `prices.yaml` | The price table metering uses; a model without a price is rejected at load |
| `platform_gateway/` | The reference custom gateway: identity, entitlement and approval, quotas with two-phase accounting and the 429 contract, fallback, exact per-tenant cache, data-class matrix, metering, fault layer; local server and Lambda adapter |
| `platform_gateway/render_litellm.py` | Renders the LiteLLM proxy config and teams from the files above (Section 4.5) |
| `terraform/profiles` | One application inference profile per tenant × model × region (Figure 4.5) |
| `terraform/stub` | The minimal platform's gateway: Lambda behind an IAM-authenticated function URL |
| `terraform/proxy/{cluster,app}` | LiteLLM on EKS Auto Mode with Aurora Serverless v2, Valkey and Pod Identity |

```bash
make -C gateway serve     # local platform API on :8080, simulated models
make -C gateway test
```

The custom gateway has no streaming and no cross-instance retry budgets — run the proxy
for production. `tests/conformance` proves whichever one serves the contract.
