from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from agents.chat_reply import generate_reply
from knowledge.models import ChatMessage
from research.schemas import Claim, StructuredAnswer
from research.session import (
    add_chat_message,
    get_answer_by_id,
    get_latest_answer_for_session,
    list_chat_messages,
)
from retrieval.websearch import web_search
from settings import settings

router = APIRouter()


class ChatRequest(BaseModel):
    session_id: int
    message: str
    model: str = settings.openai_chat_model


class ChatResponse(BaseModel):
    reply: str
    referenced_claims: list[Claim]
    web_results: list[dict]


class ChatHistoryItem(BaseModel):
    role: str
    content: str
    answer_id: int | None
    web_results: list[dict] | None
    answer: StructuredAnswer | None = None


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest) -> ChatResponse:
    prior_answer = get_latest_answer_for_session(request.session_id)
    if prior_answer is None:
        raise HTTPException(
            status_code=409,
            detail="No prior research in this session yet — run /research first (e.g. by sending the first message).",
        )

    history = [(m.role.value, m.content) for m in list_chat_messages(request.session_id)][-10:]

    # Fetched BEFORE generate_reply so the reply text can actually use these results —
    # previously this ran after and the results were only ever appended as dead links.
    # The original question is included so a short follow-up (e.g. "what defenses
    # apply?") doesn't lose the topic and search something unrelated.
    web_results = web_search(f"{prior_answer.question} — {request.message}")

    add_chat_message(request.session_id, role="user", content=request.message)

    result = generate_reply(prior_answer, request.message, web_results, history, model=request.model)
    web_results_json = [r.model_dump(mode="json") for r in web_results]

    add_chat_message(
        request.session_id,
        role="assistant",
        content=result.reply,
        web_results=web_results_json,
    )

    return ChatResponse(reply=result.reply, referenced_claims=result.referenced_claims, web_results=web_results_json)


@router.get("/chat/{session_id}", response_model=list[ChatHistoryItem])
def chat_history(session_id: int) -> list[ChatHistoryItem]:
    rows: list[ChatMessage] = list_chat_messages(session_id)
    return [
        ChatHistoryItem(
            role=row.role.value,
            content=row.content,
            answer_id=row.answer_id,
            web_results=row.web_results,
            answer=get_answer_by_id(row.answer_id) if row.answer_id else None,
        )
        for row in rows
    ]
