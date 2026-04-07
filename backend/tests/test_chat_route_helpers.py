from app.api.v1.routes.chat import _assistant_preview


def test_assistant_preview_collapses_whitespace() -> None:
    assert _assistant_preview("hello   world\n\nfrom\tassistant") == "hello world from assistant"


def test_assistant_preview_truncates_long_content() -> None:
    text = "x" * 300
    preview = _assistant_preview(text, max_chars=20)
    assert preview == ("x" * 20) + "…"
