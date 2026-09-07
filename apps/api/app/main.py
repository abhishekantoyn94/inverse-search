from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from apps.api.app.routers import chat, config, health, research, sessions

app = FastAPI(title="Inverse — Adversarial Legal Research API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(config.router)
app.include_router(research.router)
app.include_router(chat.router)
app.include_router(sessions.router)
