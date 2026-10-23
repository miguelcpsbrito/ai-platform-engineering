# Contributing

The repository is maintained so that it does not age the way paper does (Appendix A.5).

- **Branches.** `main` tracks the current edition. Each edition of the book gets a frozen
  branch (`edition-1`, …); tagged releases mark printings. Security fixes backport one
  edition.
- **Issues** for defects and drift: a quota change that breaks a lab is a bug — report
  it with the drift template.
- **Pull requests** for fixes and for new attack cases in the red-team corpus
  (`governance/redteam/corpus.yaml`) — readers are the corpus's best growth channel.
- **Discussions** for war stories; the next edition anonymizes the best ones.

The bar a change must clear:

1. A module change ships with its test, and `make test tf-offline` passes.
2. A lab change ships with its `CURRENT.md` update.
3. Nothing merges that makes a chapter's claim untrue without a matching erratum for
   the book.
4. Terraform is formatted (`terraform fmt`) and validates; prices and quotas carry a date.
