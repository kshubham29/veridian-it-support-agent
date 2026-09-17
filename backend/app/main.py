"""FastAPI entrypoint for the Veridian Corp Internal IT Service Agent."""
from __future__ import annotations

import os

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

load_dotenv()

from .routes.api import router  # noqa: E402  (must load env before llm config)
from .services import llm  # noqa: E402

app = FastAPI(
    title="Veridian IT Service Agent API",
    version="1.0.0",
    description="AI-powered internal IT support agent: policy retrieval, ticketing and audit trail.",
)

origins = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in origins] + ["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):  # pragma: no cover
    return JSONResponse(status_code=500, content={"detail": f"Unexpected server error: {exc}"})


@app.get("/")
def root():
    return {
        "service": "Veridian IT Service Agent",
        "mode": llm.mode(),
        "docs": "/docs",
        "endpoints": [
            "/api/chat",
            "/api/tickets",
            "/api/requests",
            "/api/knowledge-base",
            "/api/audit/{ticket_id}",
            "/api/dashboard/stats",
        ],
    }
