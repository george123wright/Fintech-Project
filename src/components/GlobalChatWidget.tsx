import { useEffect, useMemo, useRef, useState } from "react";
import ChatMessageRenderer from "./chat/ChatMessageRenderer";
import { usePortfolioData } from "../state/DataProvider";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  text: string;
};

function buildAssistantReply(input: string, context: {
  activePortfolioId: number | null;
  status: string;
  holdingsCount: number;
  warningCount: number;
}) {
  const portfolio =
    context.activePortfolioId == null ? "No active portfolio is selected yet." : `Portfolio #${context.activePortfolioId} is currently active.`;

  return [
    `You asked: \"${input.trim()}\"`,
    portfolio,
    `Data status: ${context.status}. Holdings loaded: ${context.holdingsCount}.`,
    context.warningCount > 0
      ? `There are ${context.warningCount} data warning(s) in context.`
      : "No data warnings are currently present.",
  ].join("\n");
}

const FOCUSABLE_SELECTOR =
  'button:not([disabled]), textarea:not([disabled]), [href], input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export default function GlobalChatWidget() {
  const { state } = usePortfolioData();
  const [isOpen, setIsOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [failedInput, setFailedInput] = useState<string | null>(null);
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

    setFailedInput(null);
    setMessages((current: ChatMessage[]) => [
      ...current,
      {
        id: `user-${Date.now()}`,
        role: "user",
        text,
      },
    ]);
    setInput("");
    setIsLoading(true);

    await new Promise((resolve) => setTimeout(resolve, 900));

    const shouldFail = text.toLowerCase().includes("fail");
    if (shouldFail) {
      setIsLoading(false);
      setFailedInput(text);
      return;
    }

    const reply = buildAssistantReply(text, context);
    setMessages((current: ChatMessage[]) => [
      ...current,
      {
        id: `assistant-${Date.now()}`,
        role: "assistant",
        text: reply,
      },
    ]);
    setIsLoading(false);
  };

  const handleRetry = async () => {
    if (!failedInput) return;
    await sendMessage(failedInput);
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
            <button type="button" className="chat-close-btn" onClick={() => setIsOpen(false)}>
              Close
            </button>
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
            {failedInput ? (
              <div className="chat-error-box">
                <span>Message failed to send.</span>
                <button type="button" onClick={() => void handleRetry()}>
                  Retry
                </button>
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
