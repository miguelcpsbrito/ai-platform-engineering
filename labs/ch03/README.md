# Lab ch03 — The minimal platform (Section 3.6, Table 3.5)

The "hello world" every later lab extends: `org` (in a lab OU), `network`, `identity`,
and the gateway stub fronting two Bedrock models. Time: about 2 hours. Standing cost on
the default (DNS Firewall) track: see [CURRENT.md](CURRENT.md).

**Prerequisites.** An AWS Organization you may add an OU to (management-account or
delegated-administrator credentials for step 1); a sandbox member account; Bedrock model
access in us-east-1 and us-west-2 for Claude Sonnet 4.6 and Amazon Nova Pro/Micro;
Terraform ≥ 1.6, Python ≥ 3.11, AWS CLI v2.

## Step 1 — `org/` (management account)

```bash
cd labs/ch03/org
terraform init
terraform apply -var lab_account_id=<sandbox account> \
  -var 'platform_principal_arns=["arn:aws:iam::*:role/platform-*","<the role you deploy with in the sandbox>"]'
# then move the sandbox account into the lab OU (the command is printed as an output)
```

The SCPs attach to the lab OU only. The model-allowlist SCP lets only
`platform_principal_arns` set the `approved-model` tag, so the role you deploy step 2
with must be in that list — that is the point of the control.

## Steps 2–4 — the platform (sandbox account): three commands

```bash
make -C gateway package && (cd gateway && python -m platform_gateway.profiles --env prod) > labs/ch03/platform/profiles.json
terraform -chdir=labs/ch03/platform init && terraform -chdir=labs/ch03/platform apply
./labs/ch03/prove.sh
```

`prove.sh` runs the five proofs of Table 3.5 and prints PASS/FAIL with the evidence:

| # | Proves | How |
|---|---|---|
| 1 | An unapproved model call fails with AccessDenied | `aws bedrock-runtime converse` with your own role → SCP denial |
| 2 | Provider APIs are NXDOMAIN from a workload subnet; Bedrock resolves privately | the egress probe Lambda inside the VPC |
| 3 | Zero static keys; a tenant role cannot call models outside the gateway | IAM user key inventory; tenant role → direct call denied by its boundary |
| 4 | One governed inference, attributed to a tenant, with cost metadata in logs | SigV4 call to the function URL as `lab-tenant-a`; the metering event in CloudWatch Logs |
| 5 | The whole platform tears down from code | `./labs/ch03/teardown` checks nothing tagged `lab=ai-platform-ch03` remains |

## Step 5 — teardown

```bash
ORG_PROFILE=<management profile> ./labs/ch03/teardown     # or KEEP_ORG=1 to keep the lab OU
```

Run it. A lab you fear deleting is a lab you stop using.

## Running the lab from CI

`.github/workflows/aws-labs.yml` runs steps 2–5 through OIDC. Create a role in the
sandbox account trusted by `token.actions.githubusercontent.com` for this repository,
named so that it matches `platform-*`, store its ARN as the `AWS_LAB_ROLE_ARN` secret of
the `aws-sandbox` environment, and run the workflow by hand.
