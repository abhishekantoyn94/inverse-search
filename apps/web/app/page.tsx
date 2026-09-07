"use client";

import { useEffect, useRef, useState } from "react";
import AdvancedSearchPopover from "./components/AdvancedSearchPopover";
import MessageBubble from "./components/MessageBubble";
import Sidebar from "./components/Sidebar";
import {
  STANDARD_MODES,
  type ChatHistoryItem,
  type ChatResponse,
  type ConfigResponse,
  type ResearchMode,
  type ResearchResponse,
  type SessionSummary,
  type StructuredAnswer,
  type ThreadMessage,
} from "./types";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const FALLBACK_MODELS = ["gpt-4o-mini", "gpt-4o", "gpt-4.1-mini", "gpt-4.1", "o4-mini"];
const SESSION_STORAGE_KEY = "inverse_session_id";

let messageIdCounter = 0;
function nextId(): string {
  messageIdCounter += 1;
  return `m${messageIdCounter}`;
}

function countAuthorityClaims(answer: StructuredAnswer): number {
  const lists = [
    answer.governing_statutes, answer.binding_authorities, answer.persuasive_authorities,
    answer.factually_similar_authorities, answer.legally_similar_authorities,
    answer.authorities_supporting, answer.authorities_against, answer.distinguishing_authorities,
    answer.comparative_authorities, answer.novel_or_analogous_authorities,
    [answer.adversarial_analysis.strongest_argument_for, answer.adversarial_analysis.strongest_argument_against],
    answer.adversarial_analysis.weaknesses, answer.adversarial_analysis.likely_opposing_authorities,
    answer.adversarial_analysis.possible_responses, answer.inverse_research.authorities_supporting_inverse,
  ];
  return lists.flat().filter((c) => c.claim_type === "authority").length;
}

function historyToThreadMessages(history: ChatHistoryItem[]): ThreadMessage[] {
  return history.map((item): ThreadMessage => {
    if (item.role === "user") {
      return { id: nextId(), role: "user", content: item.content };
    }
    if (item.answer) {
      return {
        id: nextId(),
        role: "assistant",
        kind: "research",
        answer: item.answer,
        // total is reconstructable from the persisted answer; how many were blocked
        // at generation time isn't persisted separately, so it's omitted on replay.
        verificationReport: { total_authority_claims: countAuthorityClaims(item.answer), blocked_unverifiable_claims: 0 },
      };
    }
    return {
      id: nextId(),
      role: "assistant",
      kind: "text",
      content: item.content,
      referencedClaims: [],
      webResults: item.web_results ?? [],
    };
  });
}

export default function Home() {
  const [sessionId, setSessionId] = useState<number | null>(null);
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [jurisdiction, setJurisdiction] = useState("US-Federal");
  const [availableModels, setAvailableModels] = useState<string[]>(FALLBACK_MODELS);
  const [model, setModel] = useState<string>("gpt-4o-mini");
  const [advancedModes, setAdvancedModes] = useState<ResearchMode[]>([]);
  const [inverseOn, setInverseOn] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);

  const [messages, setMessages] = useState<ThreadMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);

  function refreshSessions() {
    fetch(`${API_URL}/sessions`)
      .then((res) => (res.ok ? (res.json() as Promise<SessionSummary[]>) : []))
      .then(setSessions)
      .catch(() => {});
  }

  useEffect(() => {
    fetch(`${API_URL}/config`)
      .then((res) => (res.ok ? (res.json() as Promise<ConfigResponse>) : null))
      .then((config) => {
        if (config) {
          setAvailableModels(config.available_models);
          setModel(config.default_model);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    refreshSessions();
    const stored = typeof window !== "undefined" ? window.localStorage.getItem(SESSION_STORAGE_KEY) : null;
    if (stored) {
      loadSession(Number(stored));
      return;
    }
    startNewChat();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, loading]);

  function startNewChat() {
    fetch(`${API_URL}/sessions`, { method: "POST" })
      .then((res) => res.json())
      .then((data: { session_id: number }) => {
        setSessionId(data.session_id);
        setMessages([]);
        window.localStorage.setItem(SESSION_STORAGE_KEY, String(data.session_id));
      })
      .catch(() => {});
  }

  function loadSession(id: number) {
    setSessionId(id);
    window.localStorage.setItem(SESSION_STORAGE_KEY, String(id));
    fetch(`${API_URL}/chat/${id}`)
      .then((res) => (res.ok ? (res.json() as Promise<ChatHistoryItem[]>) : []))
      .then((history) => setMessages(historyToThreadMessages(history)))
      .catch(() => setMessages([]));
  }

  async function handleSend() {
    const question = input.trim();
    if (!question || !sessionId || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { id: nextId(), role: "user", content: question }]);
    setLoading(true);

    const isFirstMessage = messages.length === 0;
    const wantsFullResearch = isFirstMessage || advancedModes.length > 0 || inverseOn;

    try {
      if (wantsFullResearch) {
        const modes = [...STANDARD_MODES, ...advancedModes, ...(inverseOn ? (["inverse"] as ResearchMode[]) : [])];
        const response = await fetch(`${API_URL}/research`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, question, jurisdiction, modes, model }),
        });
        if (!response.ok) throw new Error(`Research request failed (${response.status})`);
        const data: ResearchResponse = await response.json();
        setMessages((prev) => [
          ...prev,
          { id: nextId(), role: "assistant", kind: "research", answer: data.answer, verificationReport: data.verification_report },
        ]);
      } else {
        const response = await fetch(`${API_URL}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ session_id: sessionId, message: question, model }),
        });
        if (!response.ok) throw new Error(`Chat request failed (${response.status})`);
        const data: ChatResponse = await response.json();
        setMessages((prev) => [
          ...prev,
          {
            id: nextId(),
            role: "assistant",
            kind: "text",
            content: data.reply,
            referencedClaims: data.referenced_claims,
            webResults: data.web_results,
          },
        ]);
      }
      refreshSessions();
    } catch (err) {
      setMessages((prev) => [
        ...prev,
        { id: nextId(), role: "assistant", kind: "error", content: err instanceof Error ? err.message : "Something went wrong." },
      ]);
    } finally {
      setLoading(false);
      setAdvancedModes([]);
      setInverseOn(false);
    }
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLTextAreaElement>) {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  }

  return (
    <div className="app-shell">
      <Sidebar sessions={sessions} activeSessionId={sessionId} onNewChat={startNewChat} onSelectSession={loadSession} />

      <div className="app">
        <header className="topbar">
          <span className="wordmark">Inverse</span>
          <div className="topbar-right">
            <select className="jurisdiction-select" value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value)}>
              <option value="US-Federal">US — Federal</option>
              <option value="US-CA">US — California</option>
              <option value="US-NY">US — New York</option>
            </select>
            <div className="popover-container">
              <button type="button" className="icon-button" onClick={() => setSettingsOpen((v) => !v)} aria-label="Settings">
                ⚙
              </button>
              {settingsOpen && (
                <div className="popover popover--right">
                  <label className="field-label">Model</label>
                  <select value={model} onChange={(e) => setModel(e.target.value)}>
                    {availableModels.map((m) => (
                      <option key={m} value={m}>
                        {m}
                      </option>
                    ))}
                  </select>
                </div>
              )}
            </div>
          </div>
        </header>

        <main className="chat-column" ref={scrollRef}>
          {messages.length === 0 && (
            <div className="empty-state">
              <p>Ask a legal question. Inverse researches both sides of it.</p>
            </div>
          )}
          {messages.map((message) => (
            <MessageBubble key={message.id} message={message} />
          ))}
          {loading && (
            <div className="message message--assistant">
              <div className="bubble bubble--assistant bubble--loading">Researching…</div>
            </div>
          )}
        </main>

        <footer className="composer">
          <div className="composer-toggles">
            <AdvancedSearchPopover selected={advancedModes} onChange={setAdvancedModes} />
            <button
              type="button"
              className={`chip-toggle ${inverseOn ? "chip-toggle--active" : ""}`}
              onClick={() => setInverseOn((v) => !v)}
            >
              Inverse Search
            </button>
          </div>
          <div className="composer-row">
            <textarea
              className="composer-input"
              rows={1}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Can X be liable for Y given these facts under [jurisdiction] law?"
            />
            <button className="send-button" onClick={handleSend} disabled={loading || !input.trim() || !sessionId}>
              Send
            </button>
          </div>
        </footer>
      </div>
    </div>
  );
}
