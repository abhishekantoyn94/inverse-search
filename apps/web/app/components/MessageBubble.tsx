"use client";

import type { ThreadMessage } from "../types";
import ClaimRow from "./ClaimRow";
import ResearchCard from "./ResearchCard";

export default function MessageBubble({ message }: { message: ThreadMessage }) {
  if (message.role === "user") {
    return (
      <div className="message message--user">
        <div className="bubble bubble--user">{message.content}</div>
      </div>
    );
  }

  if (message.kind === "research") {
    return (
      <div className="message message--assistant">
        <ResearchCard answer={message.answer} verificationReport={message.verificationReport} />
      </div>
    );
  }

  if (message.kind === "error") {
    return (
      <div className="message message--assistant">
        <div className="bubble bubble--error">{message.content}</div>
      </div>
    );
  }

  return (
    <div className="message message--assistant">
      <div className="bubble bubble--assistant">
        {message.content}
        {message.referencedClaims.length > 0 && (
          <div className="bubble-claims">
            {message.referencedClaims.map((c, i) => (
              <ClaimRow key={i} claim={c} />
            ))}
          </div>
        )}
        {message.webResults.length > 0 && (
          <div className="web-verification-links">
            {message.webResults.map((w, i) => (
              <a key={i} href={w.url} target="_blank" rel="noopener noreferrer" className="web-link-chip" title={w.snippet}>
                {w.title}
              </a>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
