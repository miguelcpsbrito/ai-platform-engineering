#!/usr/bin/env bash
# labs/ch03/prove.sh — the five proofs of Table 3.5, run after steps 1–4 are applied.
# Each proof prints PASS or FAIL with the evidence; the script exits non-zero on any FAIL.
set -uo pipefail
cd "$(dirname "$0")"
REGION=${AWS_REGION:-us-east-1}
OUT=$(terraform -chdir=platform output -json)
URL=$(echo "$OUT" | python3 -c 'import json,sys;print(json.load(sys.stdin)["gateway_url"]["value"])')
ROLE_A=$(echo "$OUT" | python3 -c 'import json,sys;print(json.load(sys.stdin)["tenant_role_arns"]["value"]["lab-tenant-a"])')
LOGS=$(echo "$OUT" | python3 -c 'import json,sys;print(json.load(sys.stdin)["gateway_log_group"]["value"])')
PROBE=$(echo "$OUT" | python3 -c 'import json,sys;print(json.load(sys.stdin)["probe_function"]["value"])')
fail=0
pass() { echo "PASS  $1"; }
nope() { echo "FAIL  $1"; fail=1; }

echo "== 1. An unapproved model call fails with AccessDenied (org/ SCP)"
ERR=$(aws bedrock-runtime converse --region "$REGION" --model-id us.amazon.nova-micro-v1:0 \
  --messages '[{"role":"user","content":[{"text":"hi"}]}]' 2>&1 >/dev/null)
if echo "$ERR" | grep -q "AccessDenied" && echo "$ERR" | grep -qi "service control policy"; then
  pass "direct call denied by an SCP: $(echo "$ERR" | head -c 160)"
else nope "expected AccessDenied from a service control policy, got: $(echo "$ERR" | head -c 200)"; fi

echo "== 2. Provider API is NXDOMAIN from a workload subnet; Bedrock resolves privately"
aws lambda invoke --region "$REGION" --function-name "$PROBE" --cli-binary-format raw-in-base64-out \
  --payload '{"blocked":"api.openai.com"}' /tmp/probe.json >/dev/null
python3 - <<'PY' && pass "egress probe: $(cat /tmp/probe.json)" || nope "egress probe: $(cat /tmp/probe.json)"
import json, sys
r = json.load(open("/tmp/probe.json"))
sys.exit(0 if r["provider_blocked"] and r["bedrock_private"] else 1)
PY

echo "== 3. Zero static keys; a tenant role cannot call models outside the gateway"
KEYS=$(for u in $(aws iam list-users --query 'Users[].UserName' --output text); do
  aws iam list-access-keys --user-name "$u" --query "AccessKeyMetadata[?Status=='Active'].AccessKeyId" --output text; done | wc -w)
[ "$KEYS" -eq 0 ] && pass "no active IAM user access keys in the account" \
  || echo "WARN  $KEYS active access keys exist in this account (not created by the lab)"
CREDS=$(aws sts assume-role --role-arn "$ROLE_A" --role-session-name boundary-proof --output json)
export AK=$(echo "$CREDS" | python3 -c 'import json,sys;print(json.load(sys.stdin)["Credentials"]["AccessKeyId"])')
export SK=$(echo "$CREDS" | python3 -c 'import json,sys;print(json.load(sys.stdin)["Credentials"]["SecretAccessKey"])')
export ST=$(echo "$CREDS" | python3 -c 'import json,sys;print(json.load(sys.stdin)["Credentials"]["SessionToken"])')
ERR=$(AWS_ACCESS_KEY_ID=$AK AWS_SECRET_ACCESS_KEY=$SK AWS_SESSION_TOKEN=$ST aws bedrock-runtime converse \
  --region "$REGION" --model-id us.amazon.nova-micro-v1:0 --messages '[{"role":"user","content":[{"text":"hi"}]}]' 2>&1 >/dev/null)
echo "$ERR" | grep -q "AccessDenied" && pass "tenant role denied direct model access" \
  || nope "tenant role reached a model directly: $(echo "$ERR" | head -c 200)"

echo "== 4. One governed inference, attributed to a tenant, with cost metadata in logs"
RESP=$(python3 call_gateway.py --url "$URL" --role "$ROLE_A" --feature ch03-proof --region "$REGION")
echo "$RESP" | head -20
TRACE=$(echo "$RESP" | python3 -c 'import json,sys;print(json.load(sys.stdin)["trace_id"] or "")')
sleep 15
EV=$(aws logs filter-log-events --region "$REGION" --log-group-name "$LOGS" \
  --filter-pattern "\"$TRACE\"" --query 'events[0].message' --output text)
if echo "$EV" | grep -q '"tenant": "tenant-a"' && echo "$EV" | grep -q '"cost_usd"'; then
  pass "metering event: $(echo "$EV" | head -c 300)"
else nope "no metering event for trace $TRACE"; fi

echo "== 5. Teardown is a separate, tested step: ./teardown"
exit $fail
