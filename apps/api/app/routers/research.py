from fastapi import APIRouter
from pydantic import BaseModel

from agents.orchestrator import run_research
from research.schemas import ResearchMode, StructuredAnswer
from research.session import add_chat_message, create_question, save_answer
from settings import settings

router = APIRouter()


class ResearchRequest(BaseModel):
    session_id: int
    question: str
    jurisdiction: str
    modes: list[ResearchMode]
    model: str = settings.openai_chat_model


class ResearchResponse(BaseModel):
    question_id: int
    answer_id: int
    answer: StructuredAnswer
    verification_report: dict


@router.post("/research", response_model=ResearchResponse)
def research(request: ResearchRequest) -> ResearchResponse:
    question_id = create_question(
        request.session_id, request.question, [m.value for m in request.modes], {"jurisdiction": request.jurisdiction}
    )

    final_state = run_research(request.question, request.jurisdiction, request.modes, model=request.model)
    answer = StructuredAnswer.model_validate(final_state["final_answer"])

    answer_id = save_answer(question_id, answer)

    add_chat_message(request.session_id, role="user", content=request.question)
    add_chat_message(
        request.session_id,
        role="assistant",
        content=answer.short_answer,
        answer_id=answer_id,
        web_results=[r.model_dump(mode="json") for r in answer.web_verification],
    )

    return ResearchResponse(
        question_id=question_id,
        answer_id=answer_id,
        answer=answer,
        verification_report=final_state.get("verification_report", {}),
    )
