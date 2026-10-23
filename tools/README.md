# tools/

- `iam_eval.py` — a strict oracle for Deny statements with AWS missing-key semantics; the SCP and boundary unit tests use it. Not a replacement for the IAM policy simulator or the live suite.
- `tfcheck.py`, `tfschema.py` — offline Terraform checks: HCL syntax, argument names and required arguments against the AWS provider schema (extracted from the cdktf bindings of provider 6.x), undeclared `var.`/`local.`/`module.` references. `make tf-offline`.
- `hclfmt/` — `terraform fmt`-equivalent formatting from `hashicorp/hcl`'s `hclwrite`, for machines without a Terraform binary.
