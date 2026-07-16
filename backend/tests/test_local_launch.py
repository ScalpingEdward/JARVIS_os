from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_full_local_launch_contract() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for service in ("postgres:", "redis:", "api:", "frontend:", "sandbox-runner:"):
        assert service in compose
    assert "condition: service_healthy" in compose
    assert "automatic order execution" in (ROOT / "README.md").read_text(encoding="utf-8").lower()


def test_windows_and_cross_platform_launchers_exist() -> None:
    assert (ROOT / "START_PHOENIX.bat").is_file()
    assert (ROOT / "STOP_PHOENIX.bat").is_file()
    assert (ROOT / "start_phoenix.sh").is_file()
    launcher = (ROOT / "scripts" / "phoenix_launcher.py").read_text(encoding="utf-8")
    assert "PHOENIX ONLINE" in launcher
    assert "MASTER Brano" in launcher
    assert "docker" in launcher
