"""Call the platform API as a tenant: assume the tenant role, SigV4-sign the request to
the function URL (service "lambda"), print status, headers and body.

    python labs/ch03/call_gateway.py --url $URL --role $ROLE_ARN --feature hello
"""
import argparse
import json
import sys
import urllib.error
import urllib.request

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials


def call(url, role_arn, alias="standard", text="Say hello in five words.", feature="lab",
         region="us-east-1", max_tokens=64):
    creds = boto3.client("sts").assume_role(RoleArn=role_arn, RoleSessionName="lab-call")["Credentials"]
    c = Credentials(creds["AccessKeyId"], creds["SecretAccessKey"], creds["SessionToken"])
    body = json.dumps({"model": alias, "max_tokens": max_tokens,
                       "messages": [{"role": "user", "content": text}]})
    endpoint = url.rstrip("/") + "/v1/chat/completions"
    req = AWSRequest("POST", endpoint, data=body,
                     headers={"content-type": "application/json", "x-platform-feature": feature})
    SigV4Auth(c, "lambda", region).add_auth(req)
    r = urllib.request.Request(endpoint, data=body.encode(), headers=dict(req.headers), method="POST")
    try:
        with urllib.request.urlopen(r, timeout=130) as resp:
            return resp.status, dict(resp.headers), json.loads(resp.read())
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), json.loads(e.read() or b"{}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--role", required=True)
    ap.add_argument("--alias", default="standard")
    ap.add_argument("--feature", default="lab")
    ap.add_argument("--region", default="us-east-1")
    a = ap.parse_args()
    status, headers, body = call(a.url, a.role, a.alias, feature=a.feature, region=a.region)
    print(json.dumps({"status": status,
                      "trace_id": headers.get("x-platform-trace-id"),
                      "served_by": headers.get("x-platform-served-by"),
                      "body": body}, indent=2))
    sys.exit(0 if status == 200 else 1)
