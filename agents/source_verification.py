"""The hard gate: every Claim of type 'authority' must have a (document_id, section_id)
pair that resolves to a real, retrieved document_sections row. Anything that doesn't is
downgraded to 'unresolved' and stripped of its source before the answer ever reaches
the user — this is what makes the "no fabricated authorities" requirement (spec §19) an
enforced property, not a prompting hope.

Once a claim's id pair is confirmed real, its whole SourceRef (title, citation_string,
locator, extract, source_url) is REBUILT from the authoritative DB record rather than
trusting the LLM's copy. The LLM may paraphrase an extract when writing a claim, which
used to fail a strict substring check even though the underlying citation was genuine —
id-existence is the actual anti-hallucination property; the display text should always
be the true stored text and a real link, not the model's rendering of it.
"""

from sqlalchemy import select
from sqlalchemy.orm import joinedload

from agents.state import ResearchState
from knowledge.db import SessionLocal
from knowledge.models import DocumentSection
from research.schemas import Claim, ClaimType, SourceRef, StructuredAnswer

_CLAIM_LIST_FIELDS = [
    "governing_statutes", "binding_authorities", "persuasive_authorities",
    "factually_similar_authorities", "legally_similar_authorities",
    "authorities_supporting", "authorities_against", "distinguishing_authorities",
    "comparative_authorities", "novel_or_analogous_authorities",
]


def verify_claim(claim: Claim, cache: dict[int, DocumentSection]) -> Claim:
    if claim.claim_type != ClaimType.AUTHORITY or claim.source is None:
        return claim

    section = cache.get(claim.source.section_id)
    if section is None or section.document_id != claim.source.document_id:
        return claim.model_copy(update={"claim_type": ClaimType.UNRESOLVED, "verified": False, "source": None})

    authoritative_source = SourceRef(
        document_id=section.document_id,
        section_id=section.id,
        title=section.document.title,
        citation_string=section.document.citation_string,
        locator=section.locator,
        extract=section.text,
        source_url=section.document.source_url,
    )
    return claim.model_copy(update={"verified": True, "source": authoritative_source})


def run(state: ResearchState) -> ResearchState:
    if "final_answer" not in state:
        return state

    answer = StructuredAnswer.model_validate(state["final_answer"])

    all_section_ids = set()
    for field_name in _CLAIM_LIST_FIELDS:
        for claim in getattr(answer, field_name):
            if claim.source:
                all_section_ids.add(claim.source.section_id)
    for claim in [
        answer.adversarial_analysis.strongest_argument_for,
        answer.adversarial_analysis.strongest_argument_against,
        *answer.adversarial_analysis.weaknesses,
        *answer.adversarial_analysis.likely_opposing_authorities,
        *answer.adversarial_analysis.possible_responses,
        *answer.inverse_research.authorities_supporting_inverse,
    ]:
        if claim.source:
            all_section_ids.add(claim.source.section_id)

    with SessionLocal() as session:
        rows = session.scalars(
            select(DocumentSection)
            .options(joinedload(DocumentSection.document))
            .where(DocumentSection.id.in_(all_section_ids))
        )
        cache = {row.id: row for row in rows}

        total = 0
        blocked = 0
        for field_name in _CLAIM_LIST_FIELDS:
            verified_claims = []
            for claim in getattr(answer, field_name):
                total += 1
                verified = verify_claim(claim, cache)
                blocked += int(not verified.verified and claim.claim_type == ClaimType.AUTHORITY)
                verified_claims.append(verified)
            setattr(answer, field_name, verified_claims)

        answer.adversarial_analysis.strongest_argument_for = verify_claim(
            answer.adversarial_analysis.strongest_argument_for, cache
        )
        answer.adversarial_analysis.strongest_argument_against = verify_claim(
            answer.adversarial_analysis.strongest_argument_against, cache
        )
        answer.adversarial_analysis.weaknesses = [
            verify_claim(c, cache) for c in answer.adversarial_analysis.weaknesses
        ]
        answer.adversarial_analysis.likely_opposing_authorities = [
            verify_claim(c, cache) for c in answer.adversarial_analysis.likely_opposing_authorities
        ]
        answer.adversarial_analysis.possible_responses = [
            verify_claim(c, cache) for c in answer.adversarial_analysis.possible_responses
        ]
        answer.inverse_research.authorities_supporting_inverse = [
            verify_claim(c, cache) for c in answer.inverse_research.authorities_supporting_inverse
        ]

    return {
        **state,
        "final_answer": answer.model_dump(mode="json"),
        "verification_report": {"total_authority_claims": total, "blocked_unverifiable_claims": blocked},
    }
