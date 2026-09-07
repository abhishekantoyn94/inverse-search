"use client";

import type { Claim, StructuredAnswer, VerificationReport } from "../types";
import Accordion from "./Accordion";
import ClaimRow from "./ClaimRow";

function ClaimAccordion({ title, claims, defaultOpen }: { title: string; claims: Claim[]; defaultOpen?: boolean }) {
  if (claims.length === 0) return null;
  return (
    <Accordion title={title} count={claims.length} defaultOpen={defaultOpen}>
      {claims.map((claim, i) => (
        <ClaimRow key={i} claim={claim} />
      ))}
    </Accordion>
  );
}

function TextListAccordion({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <Accordion title={title} count={items.length}>
      <ul className="plain-list">
        {items.map((item, i) => (
          <li key={i}>{item}</li>
        ))}
      </ul>
    </Accordion>
  );
}

export default function ResearchCard({
  answer,
  verificationReport,
}: {
  answer: StructuredAnswer;
  verificationReport: VerificationReport;
}) {
  const adv = answer.adversarial_analysis;
  const hasAdversarial = adv.strongest_argument_for.text || adv.strongest_argument_against.text;
  const inv = answer.inverse_research;
  const hasInverse = inv.inverse_proposition && inv.inverse_proposition !== "Not researched in this session.";

  return (
    <div className="research-card">
      <div className="research-card-meta">
        {answer.jurisdiction} · {answer.issues.length} issue{answer.issues.length === 1 ? "" : "s"}
      </div>
      <p className="research-card-short-answer">{answer.short_answer}</p>

      {answer.material_facts.length > 0 && (
        <Accordion title="Material facts" count={answer.material_facts.length}>
          <ul className="plain-list">
            {answer.material_facts.map((f, i) => (
              <li key={i}>{f}</li>
            ))}
          </ul>
        </Accordion>
      )}
      <TextListAccordion title="Issues" items={answer.issues} />
      <ClaimAccordion title="Governing statutes" claims={answer.governing_statutes} />
      <ClaimAccordion title="Binding authorities" claims={answer.binding_authorities} defaultOpen />
      <ClaimAccordion title="Persuasive authorities" claims={answer.persuasive_authorities} />
      <ClaimAccordion title="Factually similar authorities" claims={answer.factually_similar_authorities} />
      <ClaimAccordion title="Legally similar authorities" claims={answer.legally_similar_authorities} />
      <ClaimAccordion title="Authorities supporting" claims={answer.authorities_supporting} />
      <ClaimAccordion title="Authorities against" claims={answer.authorities_against} />
      <ClaimAccordion title="Distinguishing authorities" claims={answer.distinguishing_authorities} />

      {hasAdversarial && (
        <Accordion title="Adversarial analysis" defaultOpen>
          {adv.strongest_argument_for.text && (
            <div className="sub-block">
              <div className="sub-block-label">Strongest argument for</div>
              <ClaimRow claim={adv.strongest_argument_for} />
            </div>
          )}
          {adv.strongest_argument_against.text && (
            <div className="sub-block">
              <div className="sub-block-label">Strongest argument against</div>
              <ClaimRow claim={adv.strongest_argument_against} />
            </div>
          )}
          {adv.weaknesses.length > 0 && (
            <div className="sub-block">
              <div className="sub-block-label">Weaknesses</div>
              {adv.weaknesses.map((c, i) => (
                <ClaimRow key={i} claim={c} />
              ))}
            </div>
          )}
          {adv.likely_opposing_authorities.length > 0 && (
            <div className="sub-block">
              <div className="sub-block-label">Likely opposing authorities</div>
              {adv.likely_opposing_authorities.map((c, i) => (
                <ClaimRow key={i} claim={c} />
              ))}
            </div>
          )}
          {adv.possible_responses.length > 0 && (
            <div className="sub-block">
              <div className="sub-block-label">Possible responses</div>
              {adv.possible_responses.map((c, i) => (
                <ClaimRow key={i} claim={c} />
              ))}
            </div>
          )}
        </Accordion>
      )}

      {hasInverse && (
        <Accordion title="Inverse research">
          <div className="sub-block">
            <div className="sub-block-label">Inverse proposition</div>
            <p>{inv.inverse_proposition}</p>
          </div>
          {inv.authorities_supporting_inverse.length > 0 && (
            <div className="sub-block">
              <div className="sub-block-label">Authorities supporting the inverse</div>
              {inv.authorities_supporting_inverse.map((c, i) => (
                <ClaimRow key={i} claim={c} />
              ))}
            </div>
          )}
          {inv.alternative_interpretation && (
            <div className="sub-block">
              <div className="sub-block-label">Alternative interpretation</div>
              <ClaimRow claim={inv.alternative_interpretation} />
            </div>
          )}
        </Accordion>
      )}

      <ClaimAccordion title="Comparative authorities" claims={answer.comparative_authorities} />
      <ClaimAccordion title="Novel / analogous authorities" claims={answer.novel_or_analogous_authorities} />
      <TextListAccordion title="Unresolved questions" items={answer.unresolved_questions} />
      <TextListAccordion title="Research gaps" items={answer.research_gaps} />

      {answer.web_verification.length > 0 && (
        <div className="web-verification">
          <div className="web-verification-label">Web verification (informal, not legal authority)</div>
          <div className="web-verification-links">
            {answer.web_verification.map((w, i) => (
              <a key={i} href={w.url} target="_blank" rel="noopener noreferrer" className="web-link-chip" title={w.snippet}>
                {w.title}
              </a>
            ))}
          </div>
        </div>
      )}

      <p className="research-card-conclusion">{answer.conclusion}</p>
      <div className="research-card-footnotes">
        <p>{answer.jurisdiction_coverage_note}</p>
        <p>{answer.date_coverage_note}</p>
        <p>
          {verificationReport.total_authority_claims} authority claim(s) checked ·{" "}
          {verificationReport.blocked_unverifiable_claims} blocked as unverifiable
        </p>
        {answer.modes_not_yet_researched.length > 0 && (
          <p>Not yet available (Phase 2): {answer.modes_not_yet_researched.join(", ")}</p>
        )}
      </div>
    </div>
  );
}
