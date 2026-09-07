from datetime import datetime

from fastapi import APIRouter
from pydantic import BaseModel

from research.session import create_session, get_or_create_default_user, list_sessions_for_user

router = APIRouter()


class SessionResponse(BaseModel):
    session_id: int


class SessionSummary(BaseModel):
    session_id: int
    preview: str
    last_active_at: datetime


@router.post("/sessions", response_model=SessionResponse)
def new_session() -> SessionResponse:
    return SessionResponse(session_id=create_session())


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions() -> list[SessionSummary]:
    user_id = get_or_create_default_user()
    return [SessionSummary(**row) for row in list_sessions_for_user(user_id)]
