"""SCP guardrails, live (Table A.3: weekly in the test OU). Real API calls from an
account in the SCP-Test OU; skipped unless SCP_LIVE=1 and credentials are present.

    SCP_LIVE=1 AWS_PROFILE=scp-test pytest tests/scp -q
"""
import os

import pytest

pytestmark = pytest.mark.skipif(os.environ.get("SCP_LIVE") != "1", reason="set SCP_LIVE=1 in a test-OU account")
REGION = os.environ.get("AWS_REGION", "us-east-1")


def _code(fn):
    from botocore.exceptions import ClientError
    try:
        fn()
        return "OK"
    except ClientError as e:
        return e.response["Error"]["Code"] + ":" + e.response["Error"].get("Message", "")


def test_direct_model_call_denied_by_scp():
    import boto3
    brt = boto3.client("bedrock-runtime", region_name=REGION)
    r = _code(lambda: brt.converse(modelId="us.amazon.nova-micro-v1:0",
                                   messages=[{"role": "user", "content": [{"text": "hi"}]}]))
    assert r.startswith("AccessDeniedException") and "service control policy" in r


def test_untagged_profile_creation_denied():
    import boto3
    b = boto3.client("bedrock", region_name=REGION)
    acct = boto3.client("sts").get_caller_identity()["Account"]
    r = _code(lambda: b.create_inference_profile(
        inferenceProfileName="scp-test-untagged",
        modelSource={"copyFrom": f"arn:aws:bedrock:{REGION}:{acct}:inference-profile/us.amazon.nova-micro-v1:0"}))
    assert r.startswith("AccessDeniedException")


def test_unapproved_region_denied():
    import boto3
    r = _code(lambda: boto3.client("ec2", region_name="sa-east-1").describe_vpcs())
    assert "UnauthorizedOperation" in r or "AccessDenied" in r


@pytest.mark.skipif(not os.environ.get("SCP_PROFILE_ARN"), reason="set SCP_PROFILE_ARN to an approved application profile")
def test_approved_application_profile_succeeds():
    import boto3
    brt = boto3.client("bedrock-runtime", region_name=REGION)
    r = _code(lambda: brt.converse(modelId=os.environ["SCP_PROFILE_ARN"], inferenceConfig={"maxTokens": 8},
                                   messages=[{"role": "user", "content": [{"text": "hi"}]}]))
    assert r == "OK", r
