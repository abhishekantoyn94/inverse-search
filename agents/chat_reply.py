"""Follow-up replies for an existing research thread — the /chat endpoint's agent.
Unlike the main pipeline, this does NOT call the legal-corpus retrieval toolkit again
(that's what the explicit Advanced Search / Inverse Search actions are for), but it IS
allowed to reason from general legal knowledge and the web results given to it — same
OPEN_REASONING contract as synthesis: substantive answers allowed, no invented specific
citations. It also sees recent conversation turns, so a follow-up can build on earlier
follow-ups, not just the original research answer.
"""

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import joinedload

from agents.llm import OPEN_REASONING, structured_complete
from agents.source_verification import verify_claim
from knowledge.db import SessionLocal
from knowledge.models import DocumentSection
from research.schemas import Claim, StructuredAnswer, WebResult
from retrieval.websearch import format_web_results_for_prompt

SYSTEM_PROMPT = (
    "You are continuing a legal research conversation. Give a substantive, direct "
    "answer to the user's follow-up — use general legal knowledge and the WEB SEARCH "
    "RESULTS below as your primary reasoning material, the same way a knowledgeable "
    "analyst would. Weave in AVAILABLE CLAIMS from the prior research where they "
    "support or refine your answer. Do not invent a specific case name, statute "
    "citation, or quotation beyond what's in AVAILABLE CLAIMS or WEB SEARCH RESULTS — "
    "general doctrine can be discussed by name. reply should be conversational (a few "
    "sentences), not a full structured research answer. referenced_claims should be "
    "the exact claims (reusing their source document_id/section_id) that your reply "
    "relies on, or empty if none."
)


class ChatReplyOutput(BaseModel):
    reply: str
    referenced_claims: list[Claim]


def _flatten_claims(answer: StructuredAnswer) -> list[Claim]:
    claims = [
        *answer.governing_statutes, *answer.binding_authorities, *answer.persuasive_authorities,
        *answer.factually_similar_authorities, *answer.legally_similar_authorities,
        *answer.authorities_supporting, *answer.authorities_against, *answer.distinguishing_authorities,
        *answer.comparative_authorities, *answer.novel_or_analogous_authorities,
        answer.adversarial_analysis.strongest_argument_for,
        answer.adversarial_analysis.strongest_argument_against,
        *answer.adversarial_analysis.weaknesses,
        *answer.adversarial_analysis.likely_opposing_authorities,
        *answer.adversarial_analysis.possible_responses,
        *answer.inverse_research.authorities_supporting_inverse,
    ]
    return [c for c in claims if c.claim_type.value == "authority" and c.source is not None]


def _render_claims(claims: list[Claim]) -> str:
    if not claims:
        return "(no prior claims available)"
    return "\n".join(
        f"- [document_id={c.source.document_id} section_id={c.source.section_id}] {c.text}" for c in claims
    )


def generate_reply(
    prior_answer: StructuredAnswer,
    follow_up: str,
    web_results: list[WebResult],
    conversation_history: list[tuple[str, str]],
    model: str | None = None,
) -> ChatReplyOutput:
    """`conversation_history` is [(role, content), ...] for recent turns in this
    session, oldest first — real multi-turn memory beyond just the original answer."""
    history_text = "\n".join(f"{role}: {content}" for role, content in conversation_history) or "(no prior turns)"

    context = (
        f"ORIGINAL RESEARCH QUESTION:\n{prior_answer.question}\n\n"
        f"ORIGINAL SHORT ANSWER:\n{prior_answer.short_answer}\n\n"
        f"CONVERSATION SO FAR:\n{history_text}\n\n"
        f"AVAILABLE CLAIMS:\n{_render_claims(_flatten_claims(prior_answer))}\n\n"
        f"WEB SEARCH RESULTS:\n{format_web_results_for_prompt(web_results)}\n\n"
        f"FOLLOW-UP:\n{follow_up}"
    )
    result = structured_complete(SYSTEM_PROMPT, context, ChatReplyOutput, model=model, grounding=OPEN_REASONING)

    with SessionLocal() as session:
        section_ids = {c.source.section_id for c in result.referenced_claims if c.source}
        rows = session.scalars(
            select(DocumentSection).options(joinedload(DocumentSection.document)).where(DocumentSection.id.in_(section_ids))
        )
        cache = {row.id: row for row in rows}
        verified_claims = [verify_claim(c, cache) for c in result.referenced_claims]

    return ChatReplyOutput(reply=result.reply, referenced_claims=verified_claims)
