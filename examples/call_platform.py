"""Call the platform API with nothing but the standard library (Figure 4.8)."""
import json
import os
import urllib.request

URL = os.environ.get("PLATFORM_URL", "http://127.0.0.1:8080")
req = urllib.request.Request(
    f"{URL}/v1/chat/completions",
    data=json.dumps({"model": "standard", "max_tokens": 128,
                     "messages": [{"role": "user", "content": "Is water damage covered?"}]}).encode(),
    headers={"Content-Type": "application/json",
             "Authorization": f"Bearer {os.environ.get('PLATFORM_KEY', 'lab-key-tenant-a')}",
             "x-platform-feature": "example"},
    method="POST")
with urllib.request.urlopen(req) as r:
    print(r.status, r.headers.get("x-platform-trace-id"), json.loads(r.read())["choices"][0]["message"]["content"])
