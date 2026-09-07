"use client";

import type { Claim } from "../types";
import CitationLink from "./CitationLink";

export default function ClaimRow({ claim }: { claim: Claim }) {
  return (
    <div className="claim-row">
      <span className={`tag tag--${claim.claim_type}`}>{claim.claim_type}</span>
      <span className="claim-text">{claim.text}</span>
      {claim.source && (
        <div className="claim-source">
          <CitationLink claim={claim} />
        </div>
      )}
    </div>
  );
}
