# governance/ — policy that compiles to mechanism (Chapter 10)

- `intake/tiering.yaml` — Figure 10.2; `platform_governance.classify()` evaluates it, first match wins.
- `guardrails/` — the layer-1 profiles per risk tier in Terraform (Figure 10.4 is part of tier 2), versioned; output feeds the gateway's `PLATFORM_GUARDRAILS`.
- `redteam/corpus.yaml` — attack cases by family with the layer that should stop each; known layer-1 gaps are marked.
- `platform_governance/` — the three layers (local stand-in or Bedrock ApplyGuardrail, company rules, output contract), the scorecard, the data-class matrix, the deletion pipeline with its completion report, and the audit record of Figure 10.5.
