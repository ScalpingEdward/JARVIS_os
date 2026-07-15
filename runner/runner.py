import json
import os
import resource
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

API_URL = os.environ.get("JARVIS_API_URL", "http://api:8000").rstrip("/")
TOKEN = os.environ.get("SANDBOX_RUNNER_TOKEN", "")
POLL_SECONDS = max(1, int(os.environ.get("RUNNER_POLL_SECONDS", "5")))
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
MAX_OUTPUT = 200_000


def _request(path: str, method: str = "GET", payload: dict | None = None) -> dict | None:
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Content-Type": "application/json"}
    if TOKEN:
        headers["Authorization"] = f"Bearer {TOKEN}"
    request = urllib.request.Request(f"{API_URL}{path}", data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            body = response.read()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        if exc.code == 204:
            return None
        raise


def _repo_url(repository: str) -> str:
    if GITHUB_TOKEN:
        return f"https://x-access-token:{GITHUB_TOKEN}@github.com/{repository}.git"
    return f"https://github.com/{repository}.git"


def _limit_resources(cpu_limit: float, memory_mb: int) -> None:
    memory = memory_mb * 1024 * 1024
    resource.setrlimit(resource.RLIMIT_AS, (memory, memory))
    cpu_seconds = max(1, int(cpu_limit * 60))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))


def _execute(job: dict) -> dict:
    work_root = Path(tempfile.mkdtemp(prefix="jarvis-sandbox-", dir="/tmp"))
    repo_dir = work_root / "repo"
    try:
        clone = subprocess.run(
            ["git", "clone", "--depth", "1", "--branch", job["ref"], _repo_url(job["repository"]), str(repo_dir)],
            capture_output=True,
            text=True,
            timeout=120,
            env={"PATH": os.environ.get("PATH", ""), "GIT_TERMINAL_PROMPT": "0"},
        )
        if clone.returncode != 0:
            return {"exit_code": clone.returncode, "stdout": clone.stdout[-MAX_OUTPUT:], "stderr": clone.stderr[-MAX_OUTPUT:]}

        command = job["test_command"]
        bwrap = [
            "bwrap", "--unshare-all", "--share-user", "--die-with-parent",
            "--ro-bind", "/usr", "/usr", "--ro-bind", "/bin", "/bin",
            "--ro-bind", "/lib", "/lib", "--ro-bind-try", "/lib64", "/lib64",
            "--proc", "/proc", "--dev", "/dev", "--tmpfs", "/tmp",
            "--bind", str(repo_dir), "/workspace", "--chdir", "/workspace",
            "--setenv", "HOME", "/tmp", "--setenv", "PYTHONDONTWRITEBYTECODE", "1",
            "/bin/sh", "-lc", command,
        ]
        try:
            result = subprocess.run(
                bwrap,
                capture_output=True,
                text=True,
                timeout=int(job["timeout_seconds"]),
                preexec_fn=lambda: _limit_resources(float(job["cpu_limit"]), int(job["memory_mb"])),
                env={"PATH": "/usr/local/bin:/usr/bin:/bin"},
            )
            return {"exit_code": result.returncode, "stdout": result.stdout[-MAX_OUTPUT:], "stderr": result.stderr[-MAX_OUTPUT:], "timed_out": False}
        except subprocess.TimeoutExpired as exc:
            return {
                "exit_code": None,
                "stdout": (exc.stdout or "")[-MAX_OUTPUT:] if isinstance(exc.stdout, str) else "",
                "stderr": (exc.stderr or "")[-MAX_OUTPUT:] if isinstance(exc.stderr, str) else "",
                "timed_out": True,
            }
    finally:
        shutil.rmtree(work_root, ignore_errors=True)


def run_once() -> bool:
    job = _request("/v1/sandbox/worker/claim-next", method="POST")
    if not job:
        return False
    result = _execute(job)
    _request(f"/v1/sandbox/runs/{job['id']}/complete", method="POST", payload=result)
    print(f"sandbox job {job['id']} completed with {result.get('exit_code')}", flush=True)
    return True


def main() -> None:
    while True:
        try:
            worked = run_once()
            if not worked:
                time.sleep(POLL_SECONDS)
        except (urllib.error.URLError, TimeoutError, ValueError, subprocess.SubprocessError) as exc:
            print(f"runner cycle failed: {exc}", flush=True)
            time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
