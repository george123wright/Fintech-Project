# Chat Assistant Rollout Plan

## Phase 1 (MVP)
- Add/confirm backend `POST /api/v1/chat/query` route wired to OpenRouter.
- Ensure the global chat widget is mounted at app shell level so it is visible on all pages.
- Render assistant responses as plain text (safe baseline rendering).

## Phase 2
- Enable math-aware rendering (KaTeX/Markdown math support) for assistant responses.
- Improve prompt grounding using a portfolio context pack (active portfolio, holdings summary, warnings, and relevant page context).

## Phase 3
- Add message persistence (session/local storage and/or backend storage strategy).
- Add chat rate limiting protections.
- Add telemetry/observability (latency, success/failure counts, error classes, token/usage where available).
- Polish UX (loading states, retries, error copy, accessibility, and responsive behavior).

## Acceptance Criteria
- Chat widget is visible on all pages.
- User can ask a question and receive a response.
- Equations render legibly in assistant output.
- Responses reference active portfolio context when available.

## Manual QA Checklist
- [ ] **No active portfolio:** Chat blocks send (or clearly warns) until a portfolio is selected.
- [ ] **Empty data:** With an active portfolio but sparse/empty holdings, assistant still responds safely and explains limited context.
- [ ] **API failure:** Simulate OpenRouter/backend failure and verify user-friendly error + retry behavior.
- [ ] **Long answers:** Verify scrolling, layout stability, and readable formatting for long responses.
- [ ] **Math-heavy answers:** Verify inline and block equations render clearly and remain readable on small screens.
