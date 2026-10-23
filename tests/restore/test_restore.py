"""The restore drill (Section 9.6): snapshot, restore, and prove it by diffing retrieval
for probe queries per tenant. Quarterly per engine in production (Table A.3); here on
the in-memory engine so the procedure itself is under test."""
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tenancy"))
from platform_retrieval import InMemoryIndex, restore, retrieval_diff, snapshot  # noqa: E402

DOCS = {"t-a": ["water damage is covered with conditions", "drops are covered twice a year"],
        "t-b": ["pricing floor for 2027", "internal codes appendix"]}
PROBES = [("t-a", "is water damage covered"), ("t-a", "drops"), ("t-b", "pricing"), ("t-b", "codes")]


def build():
    idx = InMemoryIndex()
    for t, docs in DOCS.items():
        for i, d in enumerate(docs):
            idx.add(t, f"d{i}", d)
    return idx


def test_restore_preserves_retrieval():
    a = build()
    b = restore(snapshot(a))
    assert retrieval_diff(a, b, PROBES)["mismatches"] == []


def test_diff_catches_a_partial_restore():
    a = build()
    rows = snapshot(a)[:-1]                       # one document lost in the restore
    report = retrieval_diff(a, restore(rows), PROBES)
    assert report["mismatches"], "a lossy restore must fail the drill"
