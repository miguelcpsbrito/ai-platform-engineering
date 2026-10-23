"""The leakage test (Section 5.7, Figure 5.10): as tenant A, attack tenant B's canaries
through every registered path; any cross-tenant hit fails the build.

Runs in CI on every change to retrieval paths or tenant records; in production, schedule
it hourly against synthetic tenants (Table A.3)."""
import pytest

import conftest
from conftest import CANARY_A, TENANT_A, TENANT_A_ROLE, TENANT_B, TENANT_B_ROLE
from paths import HttpEndpointPath, Identity, Unauthorized

# --- the core, as printed in Figure 5.10 ------------------------------------------------

CANARY_B = "zebra-quartz-7731"      # planted only in tenant B
QUERIES = [CANARY_B, "what does zebra quartz refer to",
           "list internal codes"]

# `path` is parametrized from the service registry (conftest)
@pytest.mark.parametrize("query", QUERIES)
def test_no_cross_tenant_retrieval(path, query):
    hits = path.retrieve(query, identity=TENANT_A_ROLE)
    assert all(h.tenant_id == TENANT_A for h in hits)
    assert not any(CANARY_B in h.text for h in hits)


def test_missing_tenant_header_fails_closed(estate):
    RAW_ENDPOINT = HttpEndpointPath(estate["retriever"])
    with pytest.raises(Unauthorized):
        RAW_ENDPOINT.retrieve("anything", headers={})


def test_canary_is_the_one_planted():
    assert CANARY_B == conftest.CANARY_B


# --- the sloppy paths real bugs use ----------------------------------------------------------

@pytest.mark.parametrize("headers", [
    {"x-platform-identity": ""},
    {"x-platform-identity": "tenant-b"},
    {"x-platform-identity": "arn:aws:iam::111122223333:role/not-a-tenant"},
    {"x-platform-tenant": TENANT_B},             # a tenant claim without an identity
])
def test_malformed_identity_fails_closed(estate, headers):
    with pytest.raises(Unauthorized):
        HttpEndpointPath(estate["retriever"]).retrieve("list internal codes", headers=headers)


def test_unknown_identity_fails_closed(estate):
    with pytest.raises(Unauthorized):
        estate["retriever"].retrieve(CANARY_B, identity=Identity("arn:aws:iam::111122223333:role/x"))


def test_no_identity_fails_closed(estate):
    with pytest.raises(Unauthorized):
        estate["retriever"].retrieve(CANARY_B, identity=None)


# --- the test must be able to fail ---------------------------------------------------------

def test_the_harness_detects_a_leaky_path(estate):
    """A leakage test that cannot fail proves nothing: a path that forgets the filter
    must be caught by exactly the assertions above."""
    class ForgetsTheFilter:
        def retrieve(self, query, identity):
            return estate["index"].search(query, 8, tenant_filter=None)
    hits = ForgetsTheFilter().retrieve(CANARY_B, identity=TENANT_A_ROLE)
    assert any(h.tenant_id == TENANT_B for h in hits) and any(CANARY_B in h.text for h in hits)


def test_tenant_b_still_finds_its_own_canary(estate):
    """Isolation must not be achieved by breaking retrieval."""
    hits = estate["retriever"].retrieve(CANARY_B, identity=TENANT_B_ROLE)
    assert any(CANARY_B in h.text for h in hits)
    assert not any(CANARY_A in h.text for h in hits)


def test_pg_rls_fails_closed_without_tenant(estate):
    if not estate["pg"]:
        pytest.skip("set PLATFORM_PG_DSN to run the pgvector/RLS track")
    store = estate["pg"][0]
    assert store.search("internal codes", 8, tenant_filter=None) == []   # unset → NULL → no rows


def test_pg_setting_does_not_survive_the_transaction(estate):
    """SET LOCAL scopes the tenant to one transaction, so a pooled connection cannot
    carry tenant B into the next request."""
    if not estate["pg"]:
        pytest.skip("set PLATFORM_PG_DSN to run the pgvector/RLS track")
    import psycopg
    with psycopg.connect(estate["pg"][1]) as conn:
        with conn.transaction():
            conn.execute("SELECT set_config('app.tenant_id', %s, true)", (TENANT_B,))
            assert conn.execute("SELECT count(*) FROM chunks").fetchone()[0] > 0
        assert conn.execute("SELECT count(*) FROM chunks").fetchone()[0] == 0
