"""The 'application' of the Chapter 4 lab. It knows the platform contract (Figure 4.8)
and nothing else: a URL, its credential, an alias, a feature name. Proof 1 changes the
model behind the alias and this file stays byte-for-byte identical.
"""
import json
import os
import urllib.error
import urllib.request

URL = os.environ.get("PLATFORM_URL", "http://127.0.0.1:8080")
KEY = os.environ.get("PLATFORM_KEY", "lab-key-tenant-a")


def ask(question: str, alias: str = "standard", feature: str = "refund-flow", key: str = KEY,
        url: str = URL, max_tokens: int = 256, conversation: str | None = None):
    body = json.dumps({"model": alias, "max_tokens": max_tokens,
                       "messages": [{"role": "user", "content": question}]}).encode()
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {key}",
               "x-platform-feature": feature}
    if conversation:
        headers["x-platform-conversation"] = conversation
    req = urllib.request.Request(f"{url}/v1/chat/completions", data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, dict(r.headers), json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), json.loads(e.read() or b"{}")


if __name__ == "__main__":
    status, headers, body = ask("Is water damage covered on the extended plan?")
    print(status, headers.get("x-platform-served-by"), body.get("choices", [{}])[0].get("message", {}).get("content"))
