"""
Schemas v6.0 — Prof IA (AMD BC-250)
====================================
Modèles Pydantic et dataclasses partagés.
"""

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel


@dataclass(slots=True)
class ConversationRecord:
    """Regroupe les données de conversation pour _persist_conversation (SRP)."""
    session_id: str
    query: str
    response: str
    context: str | None
    chunks: list[dict[str, Any]]
    rag_used: bool
    threshold: float
    elapsed_ms: int
    metier: str | None
    model_name: str = ""
    id: str = ""


class ChatRequest(BaseModel):
    query: str
    session_id: str | None = None
    metier: str | None = None
    top_k: int | None = None
    threshold: float | None = None


class ChatResponse(BaseModel):
    response: str
    sources: list[dict]
    session_id: str
    rag_used: bool
    chunks_retrieved: int
    response_time_ms: int
    conversation_id: str = ""


class FeedbackRequest(BaseModel):
    """Feedback humain sur une conversation (alimente response_evaluations)."""
    conversation_id: str
    human_rating: int | None = None       # 1-5 (NULL si non noté)
    human_feedback: str | None = None     # commentaire libre
    is_golden: bool = False               # marque la réponse comme exemplaire


class FeedbackResponse(BaseModel):
    status: str
    conversation_id: str
    is_golden: bool


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    ollama: str
    gpu: str
    embedding_model: str
