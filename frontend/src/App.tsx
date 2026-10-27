import { useEffect, useRef, useState } from "react";
import type { FormEvent, KeyboardEvent } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import AshbyApplication from "./components/AshbyApplication";

type Message = {
  id: string;
  role: "assistant" | "user";
  content: string;
  timestamp: Date;
};

type AgentResponse = {
  status: string;
  response: string;
  message: string;
};

const initialMessage: Message = {
  id: "welcome",
  role: "assistant",
  content:
    "Hi, I’m your job-search copilot. Share a job link or ask me about your search. I can read job postings and compare them with your saved preferences. To prepare an Ashby application, open Apply to a job; I’ll show every answer for your review before anything is submitted.",
  timestamp: new Date(),
};

const suggestions = [
  "What should I look for in my next role?",
  "Can you evaluate this job posting?",
  "Help me prepare for an interview",
];

function App() {
  const [view, setView] = useState<"assistant" | "apply">("assistant");
  const [messages, setMessages] = useState<Message[]>([initialMessage]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const endOfMessages = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    endOfMessages.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, sending]);

  async function sendMessage(text: string) {
    const trimmed = text.trim();
    if (!trimmed || sending) return;

    const userMessage: Message = {
      id: crypto.randomUUID(),
      role: "user",
      content: trimmed,
      timestamp: new Date(),
    };
    setMessages((current) => [...current, userMessage]);
    setDraft("");
    setError(null);
    setSending(true);

    try {
      const response = await fetch("/api/v1/agent/input", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: trimmed }),
      });

      if (!response.ok) {
        const detail = await response.text();
        throw new Error(detail || `Request failed with status ${response.status}`);
      }

      const payload = (await response.json()) as AgentResponse;
      const assistantMessage: Message = {
        id: crypto.randomUUID(),
        role: "assistant",
        content: payload.response,
        timestamp: new Date(),
      };
      setMessages((current) => [...current, assistantMessage]);
    } catch (cause) {
      setError(
        cause instanceof Error
          ? cause.message
          : "Could not reach the agent. Check that the API service is running.",
      );
    } finally {
      setSending(false);
      composer.current?.focus();
    }
  }

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void sendMessage(draft);
  }

  function handleComposerKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void sendMessage(draft);
    }
  }

  const isNewConversation = messages.length === 1;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand-lockup">
          <div className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </div>
          <div>
            <div className="brand-name">Recruiter</div>
            <div className="brand-caption">PERSONAL COPILOT</div>
          </div>
        </div>

        <button
          className="new-chat-button"
          onClick={() => {
            setMessages([{ ...initialMessage, timestamp: new Date() }]);
            setError(null);
          }}
        >
          <span aria-hidden="true">＋</span>
          New conversation
        </button>

        <div className="sidebar-section-label">WORKSPACE</div>
        <div className="workspace-card">
          <div className="workspace-avatar">A</div>
          <div className="workspace-copy">
            <span>My job search</span>
            <small>Private workspace</small>
          </div>
          <span className="workspace-menu" aria-hidden="true">···</span>
        </div>

        <div className="sidebar-section-label recent-label">YOUR WORK</div>
        <button className={`workflow-link ${view === "assistant" ? "active" : ""}`} onClick={() => setView("assistant")}>
          <span aria-hidden="true">✳</span> Assistant
        </button>
        <button className={`workflow-link ${view === "apply" ? "active" : ""}`} onClick={() => setView("apply")}>
          <span aria-hidden="true">↗</span> Apply to a job
        </button>

        <div className="sidebar-spacer" />
        <div className="sidebar-note">
          <span className="privacy-icon" aria-hidden="true">◈</span>
          <span>Your search is private and local.</span>
        </div>
        <div className="user-card">
          <div className="user-avatar">A</div>
          <div className="user-copy">
            <span>Apoorv</span>
            <small>Personal account</small>
          </div>
          <span className="workspace-menu" aria-hidden="true">···</span>
        </div>
      </aside>

      <main className="main-panel">
        <header className="topbar">
          <div className="breadcrumb">
            <span>My job search</span>
            <span className="breadcrumb-separator">/</span>
            <span className="breadcrumb-current">{view === "assistant" ? "Assistant" : "Application"}</span>
          </div>
          {view === "assistant" && <div className="topbar-status"><span className="status-dot" />Ready to help</div>}
        </header>

        {view === "apply" ? <AshbyApplication /> : <>
        <section className={`conversation ${isNewConversation ? "conversation-empty" : ""}`}>
          {isNewConversation && (
            <div className="welcome-heading">
              <div className="welcome-eyebrow">YOUR JOB SEARCH, IN GOOD HANDS</div>
              <h1>Make your next move<br /><em>a thoughtful one.</em></h1>
              <p>Research opportunities, weigh the details, and move forward with confidence.</p>
            </div>
          )}

          <div className="message-list" aria-live="polite">
            {messages.slice(isNewConversation ? 0 : 1).map((message) => (
              <article key={message.id} className={`message-row ${message.role}`}>
                <div className={`message-avatar ${message.role}`} aria-hidden="true">
                  {message.role === "assistant" ? <span className="mini-mark">✳</span> : "A"}
                </div>
                <div className="message-body">
                  <div className="message-meta">
                    <strong>{message.role === "assistant" ? "Recruiter" : "You"}</strong>
                    <time>{message.timestamp.toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })}</time>
                  </div>
                  {message.role === "assistant" ? (
                    <div className="markdown-content">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
                    </div>
                  ) : (
                    <div className="user-message-content">{message.content}</div>
                  )}
                </div>
              </article>
            ))}
            {sending && (
              <article className="message-row assistant">
                <div className="message-avatar assistant" aria-hidden="true"><span className="mini-mark">✳</span></div>
                <div className="message-body">
                  <div className="message-meta"><strong>Recruiter</strong><span className="thinking-label">Thinking</span></div>
                  <div className="typing-indicator" aria-label="Agent is thinking"><i /><i /><i /></div>
                </div>
              </article>
            )}
            <div ref={endOfMessages} />
          </div>

          {error && <div className="error-banner" role="alert">{error}</div>}

          {isNewConversation && (
            <div className="suggestion-list" aria-label="Suggested prompts">
              {suggestions.map((suggestion) => (
                <button key={suggestion} onClick={() => void sendMessage(suggestion)}>
                  <span>{suggestion}</span><span aria-hidden="true">↗</span>
                </button>
              ))}
            </div>
          )}
        </section>

        <footer className="composer-area">
          <form className="composer" onSubmit={handleSubmit}>
            <textarea
              ref={composer}
              value={draft}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={handleComposerKeyDown}
              placeholder="Share a job link, ask a question, or tell me what you’re looking for…"
              rows={2}
              maxLength={4000}
              aria-label="Message the recruiting assistant"
              disabled={sending}
            />
            <div className="composer-toolbar">
              <div className="composer-hint"><kbd>↵</kbd> to send <span>·</span> <kbd>⇧ ↵</kbd> for a new line</div>
              <button className="send-button" type="submit" disabled={sending || !draft.trim()} aria-label="Send message">
                {sending ? <span className="send-spinner" /> : <span aria-hidden="true">↑</span>}
              </button>
            </div>
          </form>
          <div className="disclaimer">AI can make mistakes. Verify important details before making career decisions.</div>
        </footer>
        </>}
      </main>
    </div>
  );
}

export default App;
