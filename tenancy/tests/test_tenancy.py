"""Tenant records validate against the schema; the OpenSearch query is built from identity."""
import json
import pathlib
import sys

import jsonschema
import pytest
import yaml

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tenancy"))
from platform_retrieval import Identity, TenantDirectory, Unauthorized, embed, opensearch_query  # noqa: E402

SCHEMA = json.loads((ROOT / "tenancy" / "schema" / "tenant.schema.json").read_text())
RECORDS = sorted((ROOT / "gateway" / "tenants").glob("*.yaml")) + sorted((ROOT / "tenancy" / "examples").glob("*.yaml"))


@pytest.mark.parametrize("path", RECORDS, ids=lambda p: p.name)
def test_tenant_records_are_valid(path):
    record = json.loads(json.dumps(yaml.safe_load(path.read_text()), default=str))  # YAML dates → ISO strings
    jsonschema.validate(record, SCHEMA)


def test_regulated_data_requires_level_three():
    rec = {"tenant": "claims", "class": "critical", "aliases": ["standard"],
           "quota": {"tokens_per_minute": 1000}, "data_classes": ["regulated"], "isolation_level": 1}
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(rec, SCHEMA)


def test_opensearch_filter_sits_inside_knn_and_comes_from_identity():
    d = TenantDirectory({"arn:aws:iam::1:role/a": "tenant-a-uuid"})
    body = opensearch_query(embed("water damage"), Identity("arn:aws:iam::1:role/a"), d, k=8)
    knn = body["query"]["knn"]["embedding"]
    assert knn["filter"] == {"term": {"tenant_id": "tenant-a-uuid"}} and knn["k"] == 8
    with pytest.raises(Unauthorized):
        opensearch_query(embed("x"), Identity("arn:aws:iam::1:role/zzz"), d)


def test_opensearch_store_sends_the_filtered_knn_body():
    from platform_retrieval import OpenSearchStore, Retriever
    sent = {}

    class FakeClient:
        def search(self, index, body):
            sent.update(index=index, body=body)
            return {"hits": {"hits": [{"_source": {"tenant_id": "t-a", "doc_id": "d1", "content": "x"}, "_score": 1.0}]}}

    d = TenantDirectory({"arn:aws:iam::1:role/a": "t-a"})
    hits = Retriever(OpenSearchStore(FakeClient(), "chunks", d), d).retrieve("q", identity=Identity("arn:aws:iam::1:role/a"))
    assert hits[0].tenant_id == "t-a"
    assert sent["body"]["query"]["knn"]["embedding"]["filter"] == {"term": {"tenant_id": "t-a"}}
    with pytest.raises(Unauthorized):
        OpenSearchStore(FakeClient(), "chunks", d).search("q", 8, tenant_filter=None)
