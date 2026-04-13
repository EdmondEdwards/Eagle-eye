from __future__ import annotations

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .db import ensure_runtime_schema
from .live import live_messages
from .routes import router

settings = get_settings()
app = FastAPI(title=settings.app_name)
app.include_router(router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup() -> None:
    ensure_runtime_schema()


@app.websocket("/ws/live")
async def live_feed(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        async for message in live_messages():
            await websocket.send_text(message)
    except WebSocketDisconnect:
        return
