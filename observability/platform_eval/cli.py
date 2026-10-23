"""platform-eval — the blueprint pipeline's evaluation gate (Figure 7.7).

    platform-eval evals/warranty/suite.yaml --service src.service --baseline evals/warranty/baseline.json

The service module must expose eval_answer(question) -> (answer_text, citations).
The judge calls the platform (PLATFORM_URL, PLATFORM_KEY) through the alias the suite
names, under the judge's own quota. Exit code 1 fails the build.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
import pathlib
import sys

import yaml

from . import GatewayJudge, MockJudge, run_suite


def main(argv=None):
    ap = argparse.ArgumentParser(prog="platform-eval")
    ap.add_argument("suite")
    ap.add_argument("--service", required=True, help="module with eval_answer(question)")
    ap.add_argument("--baseline", help="JSON with the last accepted scores")
    ap.add_argument("--max-drop", type=float, default=0.02, help="allowed regression vs baseline")
    ap.add_argument("--mock-judge", action="store_true", help="local labs only")
    a = ap.parse_args(argv)
    sys.path.insert(0, os.getcwd())
    svc = importlib.import_module(a.service)
    suite = yaml.safe_load(open(a.suite))
    if a.mock_judge:
        judge = MockJudge()
    else:
        from platform_sdk import Context, Gateway
        rubric_path = pathlib.Path(a.suite).parent / suite["judge"]["rubric"]
        judge = GatewayJudge(Gateway(ctx=Context(tenant=os.environ.get("PLATFORM_TENANT", "eval"),
                                                 feature="eval-judge")),
                             alias=suite["judge"]["alias"],
                             rubric=rubric_path.read_text() if rubric_path.exists() else "")
    result = run_suite(a.suite, svc.eval_answer, judge)
    if a.baseline and pathlib.Path(a.baseline).exists() and result["grounding"] is not None:
        base = json.loads(pathlib.Path(a.baseline).read_text())
        if result["grounding"] < base.get("grounding", 0) - a.max_drop:
            result["gate"] = "fail"
            result["regression"] = {"baseline": base["grounding"], "now": result["grounding"]}
    print(json.dumps({k: v for k, v in result.items() if k != "results"}, indent=2))
    sys.exit(0 if result["gate"] == "pass" else 1)


if __name__ == "__main__":
    main()
