import { useEffect, useMemo, useRef, useState } from "react";
import { postChatQuery } from "../api/client";
import { usePortfolioData } from "../state/DataProvider";
import ChatMessageRenderer from "./chat/ChatMessageRenderer";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

type ChatErrorState = {
  message: string;
  failedInput?: string;
};

const MAX_HISTORY_TURNS = 8;
const MAX_PERSISTED_MESSAGES = 24;

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), textarea:not([disabled]), [href], input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

function getStorageKey(activePortfolioId: number | null) {
  return `global-chat-messages:${activePortfolioId ?? "none"}`;
}

function toApiHistory(messages: ChatMessage[]) {
  return messages.slice(-MAX_HISTORY_TURNS * 2).map((message) => ({
    role: message.role,
    content: message.text,
  }));
}

export default function GlobalChatWidget() {
  const { state } = usePortfolioData();
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<ChatErrorState | null>(null);
  const inputRef = useRef<HTMLTextAreaElement | null>(null);
  const panelRef = useRef<HTMLDivElement | null>(null);
  const messagesRef = useRef<HTMLDivElement | null>(null);

  const context = useMemo(
    () => ({
      activePortfolioId: state.activePortfolioId,
      status: state.status,
      holdingsCount: state.holdings.length,
      warningCount: state.dataWarnings.length,
    }),
    [state.activePortfolioId, state.status, state.holdings.length, state.dataWarnings.length]
  );

  useEffect(() => {
    const raw = sessionStorage.getItem(getStorageKey(state.activePortfolioId));
    if (!raw) {
      setMessages([]);
      setError(null);
      return;
    }

    try {
      const parsed = JSON.parse(raw) as ChatMessage[];
      if (!Array.isArray(parsed)) {
        setMessages([]);
        return;
      }
      setMessages(
        parsed
          .filter(
            (message): message is ChatMessage =>
              typeof message?.id === "string" &&
              (message?.role === "user" || message?.role === "assistant") &&
              typeof message?.text === "string"
          )
          .slice(-MAX_PERSISTED_MESSAGES)
      );
      setError(null);
    } catch {
      setMessages([]);
      setError(null);
    }
  }, [state.activePortfolioId]);

  useEffect(() => {
    sessionStorage.setItem(
      getStorageKey(state.activePortfolioId),
      JSON.stringify(messages.slice(-MAX_PERSISTED_MESSAGES))
    );
  }, [messages, state.activePortfolioId]);

  useEffect(() => {
    if (!isOpen) return;

    inputRef.current?.focus();

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        setIsOpen(false);
      }

      if (event.key === "Tab" && panelRef.current) {
        const focusable = [...panelRef.current.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)] as HTMLElement[];
        if (focusable.length === 0) return;

        const first = focusable[0];
        const last = focusable[focusable.length - 1];
        const activeElement = document.activeElement;

        if (event.shiftKey && activeElement === first) {
          event.preventDefault();
          last.focus();
        } else if (!event.shiftKey && activeElement === last) {
          event.preventDefault();
          first.focus();
        }
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [isOpen]);

  useEffect(() => {
    if (!isOpen || !messagesRef.current) return;
    messagesRef.current.scrollTop = messagesRef.current.scrollHeight;
  }, [isOpen, messages, isLoading]);

  const sendMessage = async (rawText: string) => {
    const text = rawText.trim();
    if (!text || isLoading) return;

    if (state.activePortfolioId == null) {
      setError({ message: "Select a portfolio before sending a chat message." });
      return;
    }

    setError(null);
    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      text,
    };
    setMessages((current) => [...current, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await postChatQuery({
        portfolio_id: state.activePortfolioId,
        question: text,
        page_context: `status=${context.status}; holdings=${context.holdingsCount}; warnings=${context.warningCount}`,
        conversation_history: toApiHistory(messages),
      });

      setMessages((current: ChatMessage[]) => [
        ...current,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          text: response.assistant_message,
        },
      ]);
    } catch (caughtError) {
      const message =
        caughtError instanceof Error ? caughtError.message : "Failed to send message.";
      setError({ message, failedInput: text });
      setMessages((current: ChatMessage[]) =>
        current.filter((messageItem) => messageItem.id !== userMessage.id)
      );
    } finally {
      setIsLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
    setError(null);
    sessionStorage.removeItem(getStorageKey(state.activePortfolioId));
  };

  const handleRetry = async () => {
    if (!error?.failedInput) return;
    await sendMessage(error.failedInput);
  };

  return (
    <div className="global-chat-widget">
      {!isOpen ? (
        <button
          type="button"
          className="chat-launcher-fab"
          aria-label="Open global chat"
          onClick={() => setIsOpen(true)}
        >
          Chat
        </button>
      ) : (
        <section ref={panelRef} className="chat-panel" role="dialog" aria-modal="false" aria-label="Global chat panel">
          <header className="chat-panel-header">
            <strong>Global Chat</strong>
            <div style={{ display: "flex", gap: "0.5rem" }}>
              <button type="button" className="chat-close-btn" onClick={clearChat} disabled={isLoading}>
                Clear chat
              </button>
              <button type="button" className="chat-close-btn" onClick={() => setIsOpen(false)}>
                Close
              </button>
            </div>
          </header>

          <div ref={messagesRef} className="chat-messages" aria-live="polite">
            {messages.length === 0 ? (
              <p className="chat-empty">Ask about the active portfolio context to get started.</p>
            ) : (
              messages.map((message) => (
                <article key={message.id} className={`chat-message chat-message-${message.role}`}>
                  {message.role === "assistant" ? <ChatMessageRenderer content={message.text} /> : <div>{message.text}</div>}
                </article>
              ))
            )}
            {isLoading ? <p className="chat-loading">Assistant is thinking…</p> : null}
            {error ? (
              <div className="chat-error-box">
                <span>{error.message}</span>
                {error.failedInput ? (
                  <button type="button" onClick={() => void handleRetry()}>
                    Retry
                  </button>
                ) : null}
              </div>
            ) : null}
          </div>

          <div className="chat-input-wrap">
            <textarea
              ref={inputRef}
              rows={3}
              className="chat-input"
              aria-label="Type your chat message"
              placeholder="Type a message"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  void sendMessage(input);
                }
              }}
            />
            <button
              type="button"
              className="chat-send-btn"
              aria-label="Send chat message"
              onClick={() => void sendMessage(input)}
              disabled={isLoading || input.trim().length === 0}
            >
              Send
            </button>
          </div>
        </section>
      )}
    </div>
  );
}
