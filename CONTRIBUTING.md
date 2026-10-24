# Contributing

This is optional companion material for the book; the book does not depend on it.
It is provided as-is, and issues and pull requests are welcome but not guaranteed a
response.

- **Issues** for defects and drift — a quota or API change that breaks an exercise.
- **Pull requests** for fixes and for new attack cases in the red-team corpus
  (`governance/redteam/corpus.yaml`).

The bar a change must clear:

1. A module change ships with its test, and `make test tf-offline` passes.
2. An exercise change keeps its `CURRENT.md` cost note up to date.
3. Terraform is formatted (`terraform fmt`) and validates; prices and quotas carry a date.
