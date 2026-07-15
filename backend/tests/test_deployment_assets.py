from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_compose_has_restart_health_and_persistence() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert compose.count("restart: unless-stopped") >= 3
    assert "healthcheck:" in compose
    assert "postgres_data:" in compose
    assert "jarvis_data:" in compose
    assert "jarvis_logs:" in compose


def test_api_is_local_only_by_default() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "127.0.0.1" in compose
    assert "JARVIS_BIND_ADDRESS=127.0.0.1" in env


def test_runner_is_unprivileged_and_has_no_docker_socket() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "read_only: true" in compose
    assert "no-new-privileges:true" in compose
    assert "cap_drop:" in compose
    assert "/var/run/docker.sock" not in compose


def test_examples_do_not_contain_real_credentials() -> None:
    env = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "ghp_" not in env
    assert "sk-" not in env
    assert "OPENAI_API_KEY=\n" in env
    assert "ANTHROPIC_API_KEY=\n" in env
