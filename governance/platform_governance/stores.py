"""Deletion-pipeline store adapters (Table 5.7). The in-memory ones run the labs; the
production adapters implement the same two methods against S3, OpenSearch, ElastiCache
and the log store — delete by subject, then hunt for residue with an independent query."""
from __future__ import annotations

from . import Store


class IndexStore(Store):
    name = "vector-index"

    def __init__(self, idx):
        self.idx = idx

    def delete_subject(self, tenant, subject):
        return self.idx.delete_where(tenant, lambda text: subject in text)

    def hunt(self, tenant, subject):
        return sum(subject in h.text for h in self.idx.search(subject, 50, tenant))


class DictStore(Store):
    """Key-value stores keyed by (tenant, key): caches, prompt/response logs, eval stores."""

    def __init__(self, name, data):
        self.name, self.data = name, data

    def delete_subject(self, tenant, subject):
        keys = [k for k, v in self.data.items() if k[0] == tenant and subject in v]
        for k in keys:
            del self.data[k]
        return len(keys)

    def hunt(self, tenant, subject):
        return sum(1 for k, v in self.data.items() if k[0] == tenant and subject in v)
