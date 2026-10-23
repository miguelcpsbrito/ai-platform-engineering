"""labs/ch07 — walk it, time it, change it (Section 7.7), local mode.

Act one: create a RAG service from the blueprint with the thin portal and time it to the
first governed inference. Act two: show the road rules holding off the road (the SCP a
mis-scoped role meets). Act three: change the template, release a new version, generate
the update for the existing instance and re-certify it through the evaluation gate.
"""
import json
import os
import pathlib
import re
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

LAB = pathlib.Path(__file__).resolve().parent
ROOT = LAB.parents[1]
sys.path.insert(0, str(ROOT / "portal"))
sys.path.insert(0, str(ROOT / "tools"))
import thin_portal  # noqa: E402
from iam_eval import denied_by, load_policy  # noqa: E402


def start_gateway():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = dict(os.environ, PYTHONPATH=str(ROOT / "gateway"), PLATFORM_METERING_SINK="memory")
    p = subprocess.Popen([sys.executable, "-m", "platform_gateway.server", "--mock", "--env", "local", "--port",
                          str(port)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/healthz", timeout=1)
            return p, url
        except OSError:
            time.sleep(0.1)
    raise SystemExit("gateway did not start")


def eval_gate(service_dir, url):
    env = dict(os.environ, PLATFORM_URL=url, PLATFORM_KEY="lab-key-tenant-a",
               PYTHONPATH=os.pathsep.join([str(ROOT / "observability"), str(ROOT / "tenancy"), str(service_dir)]))
    r = subprocess.run([sys.executable, "-m", "platform_eval.cli", "evals/warranty/suite.yaml", "--service",
                        "src.service", "--mock-judge"], cwd=service_dir, env=env, capture_output=True, text=True)
    return r.returncode == 0, r.stdout.strip()


def main():
    work = pathlib.Path(tempfile.mkdtemp(prefix="ch07-"))
    gw, url = start_gateway()
    os.environ["HOME"] = str(work)           # keep the lab's catalog out of your real one
    thin_portal.CATALOG = work / ".ai-platform" / "catalog.json"
    try:
        # act one — walk and time it
        t0 = time.perf_counter()
        svc = thin_portal.main(["new", "rag-service", "--name", "warranty-assistant", "--tenant", "tenant-a",
                                "--alias", "standard", "--risk-tier", "1", "--out", str(work)])
        ok, out = eval_gate(svc, url)
        ttfi = time.perf_counter() - t0
        print(f"ACT 1  time to first governed inference: {ttfi:.1f}s (local; Table 7.4 measures the real one)")
        print(f"       evaluation gate: {'pass' if ok else 'FAIL'}\n       " + out.replace("\n", "\n       "))
        # act two — the road rules hold without the road
        scp = load_policy(ROOT / "org" / "scps" / "model-allowlist.json.tftpl", {
            "platform_principal_arns": ["arn:aws:iam::*:role/platform-*"],
            "invoke_exempt_principal_arns": ["arn:aws:iam::*:role/platform-kb-ingestion-*"]})
        sids = denied_by(scp, "bedrock:InvokeModel",
                         {"aws:PrincipalArn": "arn:aws:iam::444455556666:role/warranty-assistant-handmade"})
        print(f"ACT 2  hand-built service calling a model directly: denied by {sids} "
              f"(on AWS: AccessDenied from the org SCP — run labs/ch03 proof 1)")
        # act three — change the template, release, update the instance, re-certify
        bp = work / "blueprints"
        shutil.copytree(ROOT / "blueprints", bp)
        thin_portal.BLUEPRINTS = bp
        rp = bp / "rag-service" / "skeleton" / "retrieval.yaml"
        rp.write_text(rp.read_text().replace("profile: policy-v4, max_tokens: 512", "profile: policy-v5, max_tokens: 384"))
        tp = bp / "rag-service" / "template.yaml"
        tp.write_text(tp.read_text().replace('blueprint-version: "7.2.0"', 'blueprint-version: "7.3.0"'))
        patch = thin_portal.main(["update", str(svc)])
        diff = patch.read_text()
        subprocess.run(["patch", "-p1", "-s", "-i", str(patch)], cwd=svc, check=True)
        ok2, out2 = eval_gate(svc, url)
        changed = sorted(set(re.findall(r"^\+\+\+ b/(\S+)", diff, re.M)))
        print(f"ACT 3  generated update touches {changed}; gate after update: {'pass' if ok2 else 'FAIL'}")
        sys.exit(0 if ok and ok2 and sids else 1)
    finally:
        gw.terminate()


if __name__ == "__main__":
    main()
