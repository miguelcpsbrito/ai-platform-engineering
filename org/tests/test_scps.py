"""Unit tests for the three AI SCPs (Section 3.1, Figure 3.1).

Each test is a request the book makes a claim about. The oracle in tools/iam_eval.py
implements AWS missing-key semantics; the scheduled suite in tests/scp/ repeats the
important cases as real API calls in the SCP-Test OU.
"""
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
from iam_eval import denied_by, load_policy  # noqa: E402

SCPS = ROOT / "org" / "scps"
PLATFORM = "arn:aws:iam::111122223333:role/platform-gateway"
TENANT = "arn:aws:iam::444455556666:role/support-chatbot-prod"
VARS = {
    "platform_principal_arns": ["arn:aws:iam::*:role/platform-*"],
    "invoke_exempt_principal_arns": ["arn:aws:iam::*:role/platform-kb-ingestion-*"],
    "approved_regions": ["us-east-1", "us-west-2"],
    "approved_profile_arn_patterns": [
        "arn:aws:bedrock:*:*:inference-profile/us.*",
        "arn:aws:bedrock:us-east-1:*:application-inference-profile/*",
        "arn:aws:bedrock:us-west-2:*:application-inference-profile/*",
    ],
    "break_glass_principal_arns": ["arn:aws:iam::*:role/break-glass-*"],
}
APP_PROFILE = "arn:aws:bedrock:us-east-1:444455556666:application-inference-profile/a1b2c3d4e5f6"
SYSTEM_PROFILE = "arn:aws:bedrock:us-east-1:444455556666:inference-profile/us.anthropic.claude-sonnet-4-6"
GLOBAL_PROFILE = "arn:aws:bedrock:us-east-1:444455556666:inference-profile/global.anthropic.claude-sonnet-4-6"


@pytest.fixture(scope="module")
def allowlist():
    return load_policy(SCPS / "model-allowlist.json.tftpl", VARS)


@pytest.fixture(scope="module")
def region():
    return load_policy(SCPS / "region-restriction.json.tftpl", VARS)


@pytest.fixture(scope="module")
def tags():
    return load_policy(SCPS / "mandatory-tags.json.tftpl", VARS)


def ctx(**kw):
    base = {"aws:PrincipalArn": TENANT, "aws:RequestedRegion": "us-east-1"}
    base.update(kw)
    return base


# --- SCP 1: model allowlist ---------------------------------------------------------

def test_direct_foundation_model_call_is_denied(allowlist):
    """Table 3.5 step 1: an unapproved model call fails with AccessDenied."""
    assert "DenyInvokeWithoutApplicationProfile" in denied_by(allowlist, "bedrock:InvokeModel", ctx())


def test_converse_stream_is_covered(allowlist):
    """ConverseStream authorizes as InvokeModelWithResponseStream (Figure 3.1 caption)."""
    assert denied_by(allowlist, "bedrock:InvokeModelWithResponseStream", ctx())


def test_system_profile_without_application_profile_is_denied(allowlist):
    c = ctx(**{"bedrock:InferenceProfileArn": SYSTEM_PROFILE})
    assert denied_by(allowlist, "bedrock:InvokeModel", c) == ["DenyNonApplicationProfiles"]


def test_application_profile_call_is_allowed(allowlist):
    c = ctx(**{"bedrock:InferenceProfileArn": APP_PROFILE})
    assert denied_by(allowlist, "bedrock:InvokeModel", c) == []


def test_exempt_ingestion_role_may_invoke_embeddings(allowlist):
    c = ctx(**{"aws:PrincipalArn": "arn:aws:iam::444455556666:role/platform-kb-ingestion-warranty"})
    assert denied_by(allowlist, "bedrock:InvokeModel", c) == []


@pytest.mark.parametrize("missing", ["approved-model", "cost-center"])
def test_profile_creation_requires_each_tag(allowlist, missing):
    """Each tag is required on its own — a single Null block with two keys would AND them."""
    tags_ = {"approved-model": "true", "cost-center": "cx"}
    tags_.pop(missing)
    c = ctx(**{"aws:PrincipalArn": PLATFORM, "aws:TagKeys": list(tags_)},
            **{f"aws:RequestTag/{k}": v for k, v in tags_.items()})
    assert denied_by(allowlist, "bedrock:CreateInferenceProfile", c)


def test_platform_can_create_tagged_profile(allowlist):
    c = ctx(**{"aws:PrincipalArn": PLATFORM, "aws:TagKeys": ["approved-model", "cost-center"],
               "aws:RequestTag/approved-model": "true", "aws:RequestTag/cost-center": "cx"})
    assert denied_by(allowlist, "bedrock:CreateInferenceProfile", c) == []


def test_tenant_cannot_self_approve_a_profile(allowlist):
    c = ctx(**{"aws:TagKeys": ["approved-model", "cost-center"],
               "aws:RequestTag/approved-model": "true", "aws:RequestTag/cost-center": "cx"})
    assert denied_by(allowlist, "bedrock:CreateInferenceProfile", c) == ["OnlyPlatformSetsApproval"]
    assert denied_by(allowlist, "bedrock:TagResource", c) == ["OnlyPlatformSetsApproval"]


def test_untagging_governance_tags_is_denied(allowlist):
    c = ctx(**{"aws:TagKeys": ["cost-center"]})
    assert denied_by(allowlist, "bedrock:UntagResource", c) == ["DenyRemovingGovernanceTags"]


def test_batch_jobs_only_through_platform(allowlist):
    """CreateModelInvocationJob has no bedrock:InferenceProfileArn key, so a Null test on
    that key would deny every batch job. Batch is gated by principal instead."""
    assert denied_by(allowlist, "bedrock:CreateModelInvocationJob", ctx()) == ["BatchOnlyThroughPlatform"]
    assert denied_by(allowlist, "bedrock:CreateModelInvocationJob",
                     ctx(**{"aws:PrincipalArn": PLATFORM})) == []


# --- SCP 2: region restriction with the cross-region carve-out -----------------------

def test_non_ai_service_outside_region_is_denied(region):
    assert denied_by(region, "ec2:RunInstances", ctx(**{"aws:RequestedRegion": "sa-east-1"}))


def test_global_services_are_not_region_restricted(region):
    assert denied_by(region, "iam:CreateRole", ctx(**{"aws:RequestedRegion": "us-east-1"})) == []
    assert denied_by(region, "sts:AssumeRole", ctx(**{"aws:RequestedRegion": "eu-west-1"})) == []


def test_bedrock_outside_region_without_profile_is_denied(region):
    c = ctx(**{"aws:RequestedRegion": "us-east-2"})
    assert denied_by(region, "bedrock:InvokeModel", c)


def test_cross_region_leg_of_geographic_profile_is_allowed(region):
    """A us.* profile homed in us-east-1 may serve from us-east-2 (same geography)."""
    for arn in (APP_PROFILE, SYSTEM_PROFILE):
        c = ctx(**{"aws:RequestedRegion": "us-east-2", "bedrock:InferenceProfileArn": arn})
        assert denied_by(region, "bedrock:InvokeModel", c) == []


def test_global_profiles_are_denied(region):
    c = ctx(**{"aws:RequestedRegion": "unspecified", "bedrock:InferenceProfileArn": GLOBAL_PROFILE})
    assert "DenyGlobalCrossRegionInference" in denied_by(region, "bedrock:InvokeModel", c)


def test_application_profile_homed_outside_approved_regions_is_denied(region):
    arn = "arn:aws:bedrock:eu-west-1:444455556666:application-inference-profile/zz"
    c = ctx(**{"aws:RequestedRegion": "eu-west-1", "bedrock:InferenceProfileArn": arn})
    assert denied_by(region, "bedrock:InvokeModel", c)


def test_break_glass_is_exempt_from_service_region_rule(region):
    c = ctx(**{"aws:RequestedRegion": "sa-east-1",
               "aws:PrincipalArn": "arn:aws:iam::111122223333:role/break-glass-admin"})
    assert denied_by(region, "ec2:DescribeInstances", c) == []


# --- SCP 3: mandatory tags -----------------------------------------------------------

@pytest.mark.parametrize("action", ["bedrock:CreateKnowledgeBase", "sagemaker:CreateEndpoint",
                                    "bedrock:CreateProvisionedModelThroughput"])
def test_ai_resources_need_cost_center_and_tenant(tags, action):
    assert denied_by(tags, action, ctx())
    ok = ctx(**{"aws:RequestTag/cost-center": "cx", "aws:RequestTag/tenant": "support-chatbot"})
    assert denied_by(tags, action, ok) == []


# --- structural checks -----------------------------------------------------------------

@pytest.mark.parametrize("name", ["model-allowlist", "region-restriction", "mandatory-tags"])
def test_scp_fits_the_size_limit(name):
    doc = load_policy(SCPS / f"{name}.json.tftpl", VARS)
    minified = json.dumps(doc, separators=(",", ":"))
    assert len(minified) <= 5120, f"{name} is {len(minified)} characters"


def test_tag_policy_is_valid_json():
    doc = json.loads((ROOT / "org" / "tag-policies" / "ai-cost-tags.json").read_text())
    assert set(doc["tags"]) >= {"cost-center", "tenant", "approved-model"}
