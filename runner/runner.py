import json
import os
import time
import urllib.error
import urllib.request

API_URL = os.environ.get("JARVIS_API_URL", "http://api:8000").rstrip("/")
TOKEN = os.environ.get("SANDBOX_RUNNER_TOKEN", "")
POLL_SECONDS = max(1, int(os.environ.get("RUNNER_POLL_SECONDS", "5")))


def _request(path: str, method: str = "GET", payload: dict | None = None) -> dict | None:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = urllib.request.Request(f"{API_URL}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=15) as response:
        body = response.read()
        return json.loads(body) if body else None


def main() -> None:
    # This process is intentionally separate from the API. Phase 22 only provides
    # the durable worker lifecycle; container execution stays behind Phase 20's
    # allowlist and resource-policy contract.
    while True:
        try:
            _request("/health")
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            print(f"runner heartbeat failed: {exc}", flush=True)
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
