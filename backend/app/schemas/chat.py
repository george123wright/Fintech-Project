from __future__ import annotations

from pydantic import BaseModel, Field, field_validator

MAX_CHAT_QUESTION_LENGTH = 4000
MAX_CHAT_HISTORY_TURNS = 20


class ChatMessage(BaseModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(min_length=1, max_length=8000)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Message content cannot be empty")
        return stripped


class ChatQueryRequest(BaseModel):
    portfolio_id: int = Field(gt=0)
    question: str = Field(min_length=1, max_length=MAX_CHAT_QUESTION_LENGTH)
    page_context: str | None = Field(default=None, max_length=12000)
    conversation_history: list[ChatMessage] = Field(default_factory=list)

    @field_validator("question")
    @classmethod
    def validate_question(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Question cannot be empty")
        return stripped

    @field_validator("page_context")
    @classmethod
    def validate_page_context(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("conversation_history")
    @classmethod
    def validate_history_size(cls, value: list[ChatMessage]) -> list[ChatMessage]:
        if len(value) > MAX_CHAT_HISTORY_TURNS:
            raise ValueError(f"conversation_history exceeds max turns ({MAX_CHAT_HISTORY_TURNS})")
        return value


class ChatCitation(BaseModel):
    label: str
    detail: str | None = None


class ChatLatencyMetadata(BaseModel):
    total_ms: int = Field(ge=0)
    provider: str
    model: str | None = None


class ChatQueryResponse(BaseModel):
    assistant_message: str
    context_summary: str | None = None
    citations: list[ChatCitation] = Field(default_factory=list)
    latency: ChatLatencyMetadata
    warnings: list[str] = Field(default_factory=list)


class ChatErrorDetail(BaseModel):
    code: str
    message: str
    warnings: list[str] = Field(default_factory=list)


class ChatErrorResponse(BaseModel):
    detail: ChatErrorDetail
