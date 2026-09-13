import pytest
from app.config import Settings


@pytest.fixture(autouse=True)
def clear_database_environment(monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.delenv("JARVIS_DATABASE_URL", raising=False)


@pytest.mark.parametrize("name", ["DATABASE_URL", "JARVIS_DATABASE_URL"])
def test_database_url_environment_is_honored(monkeypatch, name):
    url = "postgresql+psycopg://example:example@postgres:5432/jarvis"
    monkeypatch.setenv(name, url)
    assert Settings(_env_file=None).database_url == url


def test_prefixed_database_url_wins_when_both_are_set(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:////unused/old.db")
    monkeypatch.setenv("JARVIS_DATABASE_URL", "sqlite:////data/preserved.db")
    assert Settings(_env_file=None).database_url == "sqlite:////data/preserved.db"


def test_environment_overrides_dotenv_even_across_aliases(tmp_path, monkeypatch):
    dotenv = tmp_path / ".env"
    dotenv.write_text("JARVIS_DATABASE_URL=sqlite:////unused/file.db\n")
    monkeypatch.setenv("DATABASE_URL", "sqlite:////data/environment.db")
    assert Settings(_env_file=dotenv).database_url == "sqlite:////data/environment.db"


@pytest.mark.parametrize("name", ["DATABASE_URL", "JARVIS_DATABASE_URL"])
def test_database_url_can_be_loaded_from_dotenv(tmp_path, name):
    dotenv = tmp_path / ".env"
    dotenv.write_text(f"{name}=sqlite:////data/preserved.db\n")
    assert Settings(_env_file=dotenv).database_url == "sqlite:////data/preserved.db"


def test_native_default_and_explicit_constructor_remain_supported():
    assert Settings(_env_file=None).database_url == "sqlite:///./jarvis.db"
    assert (
        Settings(database_url="sqlite:///explicit.db", _env_file=None).database_url
        == "sqlite:///explicit.db"
    )
