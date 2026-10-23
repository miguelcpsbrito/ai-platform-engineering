# portal/ — the thin portal (Section 7.3)

`thin_portal.py new <blueprint> ...` renders a blueprint (honouring
`copyWithoutTemplating`), registers the service in a catalog file, and `update <dir>`
produces the blueprint-update patch for an existing instance — the generated pull
request of Section 7.4. Same templates as Backstage; no portal server to operate.
