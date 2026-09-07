"use client";

import type { SessionSummary } from "../types";

export default function Sidebar({
  sessions,
  activeSessionId,
  onNewChat,
  onSelectSession,
}: {
  sessions: SessionSummary[];
  activeSessionId: number | null;
  onNewChat: () => void;
  onSelectSession: (sessionId: number) => void;
}) {
  return (
    <aside className="sidebar">
      <button type="button" className="new-chat-button" onClick={onNewChat}>
        + New chat
      </button>
      <div className="session-list">
        {sessions.map((s) => (
          <button
            type="button"
            key={s.session_id}
            className={`session-item ${s.session_id === activeSessionId ? "session-item--active" : ""}`}
            onClick={() => onSelectSession(s.session_id)}
          >
            {s.preview || "New conversation"}
          </button>
        ))}
      </div>
    </aside>
  );
}
