# org/ — the organization as the first enforcement point (Section 3.1)

**Proves:** an unapproved model call fails with AccessDenied before any platform exists.

| File | What |
|---|---|
| `scps/model-allowlist.json.tftpl` | Every invocation through an application inference profile; only platform principals set `approved-model`; profiles need approval and cost tags; governance tags cannot be removed; batch only through the platform (Figure 3.1, full) |
| `scps/region-restriction.json.tftpl` | Approved regions, with the cross-region inference carve-out for geographic (`us.`, `eu.`) and home-region application profiles; `global.` profiles denied |
| `scps/mandatory-tags.json.tftpl` | `cost-center` and `tenant` on AI resources at creation |
| `tag-policies/ai-cost-tags.json` | The cost-allocation keys of Chapter 6 |
| `tests/test_scps.py` | 25 request-level tests with AWS missing-key semantics (`tools/iam_eval.py`) |

Inputs are documented in `inputs.tf` with the section that motivates each. Attach to the
SCP-Test OU first; widen `enforced_ou_ids` only after `tests/scp` passes there. SCPs are
minified on upload and tested against the 5,120-character limit.
