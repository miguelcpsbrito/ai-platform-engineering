"""Task-scoped credentials (Section 12.3, Figure 12.3): the agent runtime assumes a task
role with a session policy built from the task's tools. Effective permissions are the
intersection of the role and the session policy; the role's trust policy must allow
sts:TagSession for the delegation tags to be accepted."""
from __future__ import annotations

import json

import boto3

from . import Registry

MAX_PACKED_POLICY = 2048   # STS limit on the session policy (plain text, before packing)


def session_policy_for(tools: list[str], registry: Registry | None = None) -> dict:
    """Allow only the AWS actions the task's registered tools declare (spec.iam)."""
    registry = registry or Registry()
    statements = []
    for name in tools:
        iam = registry.tools[name].spec.get("iam")
        if iam:
            statements.append({"Sid": name.replace(".", "").replace("-", "")[:64], "Effect": "Allow",
                               "Action": iam["actions"], "Resource": iam["resources"]})
    if not statements:      # a task with no AWS-touching tools gets no AWS permissions
        statements.append({"Sid": "NoAwsActions", "Effect": "Deny", "Action": "*", "Resource": "*"})
    policy = {"Version": "2012-10-17", "Statement": statements}
    if len(json.dumps(policy, separators=(",", ":"))) > MAX_PACKED_POLICY:
        raise ValueError("session policy too large: split the task or narrow its tools")
    return policy


def task_credentials(task_role_arn: str, agent_id: str, task_id: str, user_id: str, tools: list[str],
                     sts=None, registry: Registry | None = None) -> dict:
    sts = sts or boto3.client("sts")
    creds = sts.assume_role(
        RoleArn=task_role_arn,
        RoleSessionName=f"agent-{agent_id}-{task_id}"[:64],
        # matched to the task budget
        DurationSeconds=900,
        Policy=json.dumps(session_policy_for(tools, registry)),
        Tags=[{"Key": "delegated-user", "Value": user_id},
              {"Key": "task-id", "Value": task_id},
              {"Key": "agent", "Value": agent_id}],
    )["Credentials"]
    return creds
