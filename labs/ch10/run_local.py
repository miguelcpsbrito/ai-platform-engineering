"""labs/ch10 — attack it, then prove the paperwork (Section 10.8), local mode.

Part 1: three guardrail layers against the red-team corpus, with the per-layer scorecard.
Part 2: a regulated-class request against an alias whose contract excludes it — blocked
by the gateway's data-class matrix. Part 3: delete a planted synthetic subject from
index, cache and logs with a completion report; then the audit drill, timed.
Layer 1 here is a local stand-in; on AWS the same runner uses ApplyGuardrail.
"""
import json
import pathlib
import sys
import time

LAB = pathlib.Path(__file__).resolve().parent
ROOT = LAB.parents[1]
for p in ("governance", "tenancy", "gateway"):
    sys.path.insert(0, str(ROOT / p))
import platform_governance as g  # noqa: E402
from platform_gateway.backends import MockBackend  # noqa: E402
from platform_gateway.config import Config  # noqa: E402
from platform_gateway.faults import FaultLayer  # noqa: E402
from platform_gateway.handler import Gateway  # noqa: E402
from platform_gateway.metering import MemorySink  # noqa: E402
from platform_retrieval import InMemoryIndex  # noqa: E402
from platform_governance.stores import DictStore, IndexStore  # noqa: E402


def main():
    print("PART 1  red-team scorecard (layer 1 = local stand-in, 2 = company rules, 3 = output contract)")
    sc = g.run_redteam([g.LocalLayer1(), g.CompanyRules(), g.OutputContract()])
    for fam, f in sc.by_family().items():
        print(f"        {fam:<34} {f['blocked']}/{f['cases']} blocked  missed={f['missed']}  fp={f['false_positive']}")
    l1 = g.run_redteam([g.LocalLayer1()])
    print(f"        layer 1 alone misses: {[r['id'] for r in l1.rows if r['expect_block_at'] != 'none' and not r['blocked_at']]}")

    cfg = Config.load(ROOT / "gateway", environment="local")
    sink = MemorySink()
    gw = Gateway(cfg, FaultLayer(MockBackend(sleep=False)), sink=sink)
    key = {"kind": "api_key", "value": "lab-key-tenant-b"}
    msg = [{"role": "user", "content": "Summarize claim 88 for the adjuster."}]
    s1, _, b1 = gw.chat(key, {"x-platform-data-class": "regulated"}, {"model": "standard", "messages": msg})
    print(f"PART 2  regulated on 'standard' → {s1} {b1.get('error')}: {b1.get('message')}")
    s2, _, _ = gw.chat(key, {"x-platform-data-class": "confidential"}, {"model": "standard", "messages": msg})
    print(f"        after reclassifying the request as confidential → {s2}")

    subject = "Synthetic Subject 0042"
    idx = InMemoryIndex()
    idx.add("tenant-b", "t1", f"Claim note: {subject} reported water damage")
    idx.add("tenant-b", "t2", "Unrelated note")
    cache = DictStore("exact-cache", {("tenant-b", "k"): f"cached answer mentioning {subject}"})
    logs = DictStore("prompt-logs", {("tenant-b", "p"): f"prompt from {subject}"})
    rep = g.delete_subject([IndexStore(idx), cache, logs], "tenant-b", subject, "DSR-LAB-0001")
    print("PART 3  deletion receipt:\n        " + rep.to_json().replace("\n", "\n        "))
    for i in range(500):
        gw.chat(key, {"x-platform-feature": "claims-summary"}, {"model": "fast", "messages": [{"role": "user", "content": f"q{i}"}]})
    day = sink.events[-1]["ts"][:10]
    t0 = time.perf_counter()
    records, _ = g.audit_drill(sink.events, "tenant-b", day)
    full = [g.audit_record(e, cfg.tenants["tenant-b"].raw, "internal", {"profile": "tier2@local", "input": "pass",
                                                                         "output": "pass"}) for e in records if e.get("model")]
    secs = time.perf_counter() - t0
    print(f"        audit drill: {len(full)} interaction records for tenant-b on {day} in {secs * 1000:.0f} ms")
    print("        first record: " + json.dumps(full[0])[:240] + "…")
    ok = rep.complete and s1 == 403 and s2 == 200 and full
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
