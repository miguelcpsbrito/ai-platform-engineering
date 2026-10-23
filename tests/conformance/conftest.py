"""Conformance suite fixtures (Section 4.7, Appendix A.3).

Point it at any gateway:   PLATFORM_URL=https://ai.platform.internal \
                           PLATFORM_KEY_A=... PLATFORM_KEY_B=... pytest tests/conformance
Without PLATFORM_URL it starts the reference gateway locally with simulated models.
"""
import os
import pathlib
import socket
import subprocess
import sys
import time
import urllib.request

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture(scope="session")
def gateway():
    url = os.environ.get("PLATFORM_URL")
    if url:
        yield {"url": url.rstrip("/"), "key_a": os.environ["PLATFORM_KEY_A"],
               "key_b": os.environ["PLATFORM_KEY_B"], "local": False}
        return
    port = _free_port()
    env = dict(os.environ, PYTHONPATH=str(ROOT / "gateway"), PLATFORM_METERING_SINK="memory")
    proc = subprocess.Popen([sys.executable, "-m", "platform_gateway.server", "--mock", "--env", "local",
                             "--port", str(port)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            urllib.request.urlopen(url + "/healthz", timeout=1)
            break
        except OSError:
            time.sleep(0.1)
    yield {"url": url, "key_a": "lab-key-tenant-a", "key_b": "lab-key-tenant-b", "local": True}
    proc.terminate()
