"use client";

import { useState } from "react";
import type { Claim } from "../types";

export default function CitationLink({ claim }: { claim: Claim }) {
  const [expanded, setExpanded] = useState(false);
  if (!claim.source) return null;
  const { source } = claim;
  const label = source.citation_string ?? source.title;

  return (
    <span className="citation">
      {source.source_url ? (
        <a href={source.source_url} target="_blank" rel="noopener noreferrer" className="citation-link">
          {label}
        </a>
      ) : (
        <span className="citation-link citation-link--plain">{label}</span>
      )}
      {source.locator && <span className="citation-locator"> @ {source.locator}</span>}
      {!claim.verified && claim.claim_type === "authority" && <span className="citation-unverified"> (unverified)</span>}
      <button type="button" className="citation-expand" onClick={() => setExpanded((v) => !v)} aria-label="Show extract">
        {expanded ? "hide extract" : "show extract"}
      </button>
      {expanded && <blockquote className="citation-extract">{source.extract}</blockquote>}
    </span>
  );
}
