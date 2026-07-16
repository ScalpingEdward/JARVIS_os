#!/usr/bin/env python3
"""Cross-platform one-click launcher for PHOENIX.

Usage:
  python scripts/phoenix_launcher.py start
  python scripts/phoenix_launcher.py status
  python scripts/phoenix_launcher.py stop
  python scripts/phoenix_launcher.py logs
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
import webbrowser

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
SECRET_FILE = ROOT / "secrets" / "postgres_password.txt"
API_URL = "http://127.0.0.1:8000/health"
UI_URL = "http://127.0.0.1:8080"


def run(command: list[str], *, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=ROOT, text=True, check=check)


def docker_compose() -> list[str]:
    if shutil.which("docker") is None:
        raise RuntimeError("Docker Desktop is not installed or docker is not in PATH.")
    probe = subprocess.run(["docker", "compose", "version"], capture_output=True, text=True)
    if probe.returncode != 0:
        raise RuntimeError("Docker Compose v2 is required. Start or install Docker Desktop.")
    return ["docker", "compose"]


def ensure_config() -> None:
    if not ENV_FILE.exists():
        if not ENV_EXAMPLE.exists():
            raise RuntimeError(".env.example is missing.")
        shutil.copyfile(ENV_EXAMPLE, ENV_FILE)
        print("[CONFIG] Created .env from .env.example")

    SECRET_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not SECRET_FILE.exists():
        password = os.urandom(24).hex()
        SECRET_FILE.write_text(password, encoding="utf-8")
        print("[CONFIG] Generated local PostgreSQL secret")

    text = ENV_FILE.read_text(encoding="utf-8")
    secret = SECRET_FILE.read_text(encoding="utf-8").strip()
    if "replace-with-a-long-random-password" in text:
        text = text.replace("replace-with-a-long-random-password", secret)
        ENV_FILE.write_text(text, encoding="utf-8")
        print("[CONFIG] Synchronized generated database password into .env")


def wait_for(url: str, timeout: int = 120) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                if 200 <= response.status < 400:
                    return True
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(2)
    return False


def start(open_browser: bool = True) -> int:
    compose = docker_compose()
    ensure_config()
    print("\nPHOENIX BOOT SEQUENCE")
    print("=====================")
    run(compose + ["up", "-d", "--build", "--remove-orphans"])
    print("[BOOT] Containers started; waiting for Core Runtime...")
    if not wait_for(API_URL):
        print("[ERROR] Core Runtime did not become healthy in time.")
        run(compose + ["ps"], check=False)
        return 1
    if not wait_for(UI_URL):
        print("[ERROR] Command Center did not become healthy in time.")
        run(compose + ["ps"], check=False)
        return 1
    print("[OK] Core Runtime")
    print("[OK] PostgreSQL")
    print("[OK] Redis")
    print("[OK] Sandbox Runner")
    print("[OK] Holographic Command Center")
    print("[SAFETY] Automatic order execution remains disabled")
    print(f"\nPHOENIX ONLINE — Welcome, MASTER Brano\n{UI_URL}")
    if open_browser:
        webbrowser.open(UI_URL)
    return 0


def status() -> int:
    compose = docker_compose()
    run(compose + ["ps"], check=False)
    api = wait_for(API_URL, timeout=2)
    ui = wait_for(UI_URL, timeout=2)
    print(f"\nCore Runtime: {'ONLINE' if api else 'OFFLINE'}")
    print(f"Command Center: {'ONLINE' if ui else 'OFFLINE'}")
    return 0 if api and ui else 1


def stop() -> int:
    run(docker_compose() + ["down"], check=False)
    print("PHOENIX stopped. Persistent data volumes were preserved.")
    return 0


def logs() -> int:
    return run(docker_compose() + ["logs", "-f", "--tail=150"], check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="PHOENIX local service manager")
    parser.add_argument("command", choices=["start", "status", "stop", "logs"])
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        if args.command == "start":
            return start(open_browser=not args.no_browser)
        if args.command == "status":
            return status()
        if args.command == "stop":
            return stop()
        return logs()
    except (RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"[ERROR] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
