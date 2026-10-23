# blueprints/ — golden paths as templates (Section 7.4)

Backstage scaffolder templates (`scaffolder.backstage.io/v1beta3`), also executed by the
thin portal. `rag-service` carries the full anatomy of Figure 7.6: catalog entry, release
manifest, infrastructure under the tenant boundary, service code on the platform SDK and
retrieval library, versioned prompts, retrieval profile, evaluation suite with
`must_cite`, pipeline with the evaluation gate, runbook. `agent`, `chatbot` and `batch`
carry the catalog entry, SDK wiring and an evaluation seed, and grow with their users.
