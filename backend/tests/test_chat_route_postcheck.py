from __future__ import annotations

from app.api.v1.routes import chat as chat_routes
from app.schemas.chat import ChatQueryRequest


def test_compact_page_context_truncates_and_squashes() -> None:
    raw = "status=ready   holdings=24\nwarnings=1 " + ("x" * 400)
    compact = chat_routes._compact_page_context(raw)

    assert "\n" not in compact
    assert len(compact) <= 281
    assert compact.endswith("…")


def test_response_missed_question_intent_detects_echo_only_output() -> None:
    assert chat_routes._response_missed_question_intent("status=ok holdings=24 warnings=1")
    assert not chat_routes._response_missed_question_intent(
        "Your diversification question: concentration is elevated because top-3 holdings are 62%, "
        "so risk is asymmetric. Context notes: status is ready."
    )


def test_build_messages_moves_page_context_to_secondary_user_notes(monkeypatch) -> None:
    monkeypatch.setattr(
        chat_routes,
        "build_portfolio_context",
        lambda db, portfolio_id: {"portfolio_id": portfolio_id, "warnings": []},
    )
    monkeypatch.setattr(chat_routes, "serialize_portfolio_context", lambda context: "{}")

    payload = ChatQueryRequest(
        portfolio_id=7,
        question="What changed in concentration risk this week?",
        page_context="status=ready; holdings=18; warnings=0",
        conversation_history=[],
    )
    messages, _ = chat_routes._build_messages(payload, db=None)

    assert len([m for m in messages if m["role"] == "system"]) == 1
    assert messages[-1]["role"] == "user"
    assert "Context notes (secondary, use only if relevant):" in messages[-1]["content"]
