"""
Schemas v6.0 — Prof IA (AMD BC-250)
====================================
Modèles Pydantic et dataclasses partagés.
"""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from pydantic import BaseModel


@dataclass(slots=True)
class ConversationRecord:
    """Regroupe les données de conversation pour _persist_conversation (SRP)."""
    session_id: str
    query: str
    response: str
    context: Optional[str]
    chunks: List[Dict[str, Any]]
    rag_used: bool
    threshold: float
    elapsed_ms: int
    metier: Optional[str]
    model_name: str = ""


class ChatRequest(BaseModel):
    query: str
    session_id: Optional[str] = None
    metier: Optional[str] = None
    top_k: Optional[int] = None
    threshold: Optional[float] = None


class ChatResponse(BaseModel):
    response: str
    sources: List[dict]
    session_id: str
    rag_used: bool
    chunks_retrieved: int
    response_time_ms: int


class HealthResponse(BaseModel):
    status: str
    version: str
    database: str
    ollama: str
    gpu: str
    embedding_model: str
