from app.config import _clean_env


def test_clean_env_strips_wrapping_quotes(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "\"sk-example\"")
    assert _clean_env("OPENROUTER_API_KEY") == "sk-example"


def test_clean_env_returns_empty_for_missing(monkeypatch) -> None:
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    assert _clean_env("OPENROUTER_API_KEY") == ""
