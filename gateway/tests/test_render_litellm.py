"""The rendered LiteLLM config must load in a real LiteLLM Router and honour fallbacks."""
import pathlib
import sys

import pytest

GW = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GW))

from platform_gateway.config import Config  # noqa: E402
from platform_gateway.render_litellm import render  # noqa: E402

litellm = pytest.importorskip("litellm")


@pytest.fixture(scope="module")
def rendered():
    cfg = Config.load(GW, environment="prod")
    profiles = {}
    for t in cfg.tenants.values():
        for a in t.aliases:
            try:
                chain = cfg.resolve(a, t)
            except Exception:
                continue
            for target in chain:
                profiles[f"{t.tenant}|{target.model}|{target.region}"] = (
                    f"arn:aws:bedrock:{target.region}:111122223333:application-inference-profile/{t.tenant[:6]}x")
    return render(cfg, profiles, {"1": {"guardrailIdentifier": "gr-1", "guardrailVersion": 3}})


def test_every_deployment_uses_an_application_profile(rendered):
    config, _ = rendered
    for m in config["model_list"]:
        assert ":application-inference-profile/" in m["litellm_params"]["model_id"]
        assert m["litellm_params"]["model"].startswith("bedrock/converse/")


def test_teams_mirror_tenant_records(rendered):
    _, teams = rendered
    by = {t["team_alias"]: t for t in teams}
    assert by["support-chatbot"]["tpm_limit"] == 120000
    assert by["support-chatbot"]["max_budget"] == 9000
    assert by["support-chatbot"]["model_aliases"]["standard"] == "standard--support-chatbot"
    assert "premium" not in by["support-chatbot"]["model_aliases"]       # not entitled
    assert "premium" in by["tenant-b"]["model_aliases"]                  # tier 2


def test_router_accepts_config_and_falls_back(rendered):
    from litellm import Router
    config, _ = rendered
    router = Router(model_list=config["model_list"], fallbacks=config["router_settings"]["fallbacks"])
    # mock_testing_fallbacks fails the primary group offline; the router must use a fallback
    resp = router.completion(model="standard--tenant-a",
                             messages=[{"role": "user", "content": "hi"}],
                             mock_testing_fallbacks=True, mock_response="ok")
    assert resp.choices[0].message.content == "ok"
    attempted = resp._hidden_params.get("additional_headers", {}).get("x-litellm-attempted-fallbacks")
    assert attempted and int(attempted) >= 1
    names = {m["model_name"] for m in config["model_list"]}
    assert {"standard--tenant-a", "standard--tenant-a--fb1", "standard--tenant-a--fb2"} <= names
