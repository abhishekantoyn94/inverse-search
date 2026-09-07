from fastapi import APIRouter

from settings import settings

router = APIRouter()


@router.get("/config")
def get_config() -> dict:
    return {
        "default_model": settings.openai_chat_model,
        "available_models": settings.available_chat_models,
    }
