from sqlalchemy import select

from knowledge.db import SessionLocal
from knowledge.models import ChatMessage, ChatRole
from knowledge.models import Claim as ClaimRow
from knowledge.models import ResearchAnswer, ResearchQuestion, ResearchSession, User
from research.schemas import Claim, ClaimType, StructuredAnswer

DEFAULT_USER_EMAIL = "anonymous@local"


def get_or_create_default_user() -> int:
    """No auth system yet — every browser gets sessions under one shared user record."""
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.email == DEFAULT_USER_EMAIL))
        if user is None:
            user = User(email=DEFAULT_USER_EMAIL)
            db.add(user)
            db.commit()
            db.refresh(user)
        return user.id


def create_session() -> int:
    user_id = get_or_create_default_user()
    with SessionLocal() as db:
        session = ResearchSession(user_id=user_id)
        db.add(session)
        db.commit()
        db.refresh(session)
        return session.id


def _iter_claims(answer: StructuredAnswer) -> list[tuple[str, Claim]]:
    pairs: list[tuple[str, Claim]] = []
    list_sections = [
        "governing_statutes", "binding_authorities", "persuasive_authorities",
        "factually_similar_authorities", "legally_similar_authorities",
        "authorities_supporting", "authorities_against", "distinguishing_authorities",
        "comparative_authorities", "novel_or_analogous_authorities",
    ]
    for section_name in list_sections:
        for claim in getattr(answer, section_name):
            pairs.append((section_name, claim))

    pairs.append(("adversarial_analysis.strongest_argument_for", answer.adversarial_analysis.strongest_argument_for))
    pairs.append(("adversarial_analysis.strongest_argument_against", answer.adversarial_analysis.strongest_argument_against))
    for claim in [
        *answer.adversarial_analysis.weaknesses,
        *answer.adversarial_analysis.likely_opposing_authorities,
        *answer.adversarial_analysis.possible_responses,
    ]:
        pairs.append(("adversarial_analysis", claim))

    for claim in answer.inverse_research.authorities_supporting_inverse:
        pairs.append(("inverse_research.authorities_supporting_inverse", claim))
    if answer.inverse_research.alternative_interpretation:
        pairs.append(("inverse_research.alternative_interpretation", answer.inverse_research.alternative_interpretation))

    return pairs


def create_question(session_id: int, text: str, modes: list[str], jurisdiction_filter: dict) -> int:
    with SessionLocal() as db:
        question = ResearchQuestion(
            session_id=session_id, text=text, modes=modes, jurisdiction_filter=jurisdiction_filter
        )
        db.add(question)
        db.commit()
        db.refresh(question)
        return question.id


def save_answer(question_id: int, answer: StructuredAnswer) -> int:
    """Persists the structured answer and explodes every Claim into its own row so the
    Source Verification gate (and later audits) can check each one independently."""
    with SessionLocal() as db:
        answer_row = ResearchAnswer(question_id=question_id, structured_answer=answer.model_dump(mode="json"))
        db.add(answer_row)
        db.flush()

        for section_name, claim in _iter_claims(answer):
            db.add(
                ClaimRow(
                    answer_id=answer_row.id,
                    section_name=section_name,
                    claim_text=claim.text,
                    claim_type=ClaimType(claim.claim_type.value),
                    source_document_id=claim.source.document_id if claim.source else None,
                    source_section_id=claim.source.section_id if claim.source else None,
                    extract_text=claim.source.extract if claim.source else None,
                    confidence=claim.confidence,
                    verified=claim.verified,
                )
            )
        db.commit()
        return answer_row.id


def get_latest_answer_for_session(session_id: int) -> StructuredAnswer | None:
    """The grounding context for /chat follow-ups — the most recent full research
    answer in this session, or None if the thread has never run a full pipeline yet."""
    with SessionLocal() as db:
        row = db.scalar(
            select(ResearchAnswer)
            .join(ResearchQuestion, ResearchAnswer.question_id == ResearchQuestion.id)
            .where(ResearchQuestion.session_id == session_id)
            .order_by(ResearchAnswer.created_at.desc())
            .limit(1)
        )
        if row is None:
            return None
        return StructuredAnswer.model_validate(row.structured_answer)


def add_chat_message(
    session_id: int,
    role: str,
    content: str,
    answer_id: int | None = None,
    web_results: list[dict] | None = None,
) -> int:
    with SessionLocal() as db:
        message = ChatMessage(
            session_id=session_id,
            role=ChatRole(role),
            content=content,
            answer_id=answer_id,
            web_results=web_results,
        )
        db.add(message)
        db.commit()
        db.refresh(message)
        return message.id


def get_answer_by_id(answer_id: int) -> StructuredAnswer | None:
    with SessionLocal() as db:
        row = db.get(ResearchAnswer, answer_id)
        if row is None:
            return None
        return StructuredAnswer.model_validate(row.structured_answer)


def list_chat_messages(session_id: int) -> list[ChatMessage]:
    with SessionLocal() as db:
        rows = db.scalars(
            select(ChatMessage).where(ChatMessage.session_id == session_id).order_by(ChatMessage.created_at)
        )
        return list(rows)


def list_sessions_for_user(user_id: int) -> list[dict]:
    """For the chat-history sidebar: every session, newest first, with its first
    message as a preview and when it was last active."""
    with SessionLocal() as db:
        sessions = db.scalars(
            select(ResearchSession)
            .where(ResearchSession.user_id == user_id)
            .order_by(ResearchSession.created_at.desc())
        )
        summaries = []
        for session in sessions:
            first_message = db.scalar(
                select(ChatMessage)
                .where(ChatMessage.session_id == session.id, ChatMessage.role == ChatRole.USER)
                .order_by(ChatMessage.created_at)
                .limit(1)
            )
            last_message = db.scalar(
                select(ChatMessage)
                .where(ChatMessage.session_id == session.id)
                .order_by(ChatMessage.created_at.desc())
                .limit(1)
            )
            if first_message is None:
                continue  # an empty session (created but never used) doesn't clutter history
            summaries.append(
                {
                    "session_id": session.id,
                    "preview": first_message.content[:80],
                    "last_active_at": (last_message or first_message).created_at,
                }
            )
        return summaries
