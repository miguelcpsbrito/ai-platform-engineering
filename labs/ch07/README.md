# Lab ch07 — Walk it, time it, change it (Section 7.7)

```bash
python labs/ch07/walk_local.py
```

**Act one — walk.** The thin portal (`portal/thin_portal.py`) runs the RAG blueprint
end to end and registers the service; the generated service passes its evaluation gate
through the local gateway. Your first time-to-first-inference data point.

**Act two — govern.** A hand-built service calling a model directly meets the org SCP
(locally through the policy oracle; on AWS, `labs/ch03` proof 1).

**Act three — evolve.** Change the template's chunking profile, release 7.3.0, generate
the update patch for the existing instance, apply it, and watch the gate re-certify.

**Backstage track.** `blueprints/*/template.yaml` are Backstage scaffolder templates
(`scaffolder.backstage.io/v1beta3`). Register them in a Backstage instance; the custom
field extensions `OwnedTenantPicker` and `IntakeClassifier` are yours to implement
against `gateway/tenants` and `governance/intake`. Budget a week for a first Backstage
install; the thin portal is the honest alternative below roughly 30 services.
