"""
Auto-évaluation RAG — Juge + Avocat du diable (Phase 1).
=======================================================
Modèle unique qwen3:14b, exécution SÉQUENTIELLE (OLLAMA_NUM_PARALLEL=1).
Quality-first : format=json, temperature=0, num_predict=150.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import uuid
from enum import Enum

import httpx
from loguru import logger
from pydantic import BaseModel, Field

from .config import get_settings

_JSON_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


class AutoVerdict(str, Enum):
    PASS = "pass"
    REVIEW_NEEDED = "review_needed"
    REJECT = "reject"


class JudgeResult(BaseModel):
    score: float = Field(ge=0.0, le=1.0)
    criteria: dict[str, float] = Field(default_factory=dict)
    reasoning: str = ""


class DevilAdvocateResult(BaseModel):
    contested_claims: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)


class AutoEvaluationPayload(BaseModel):
    conversation_id: str | None = None
    evaluation_run_id: str
    verdict: AutoVerdict
    judge: JudgeResult
    devil: DevilAdvocateResult
    raw_judge: str = ""
    raw_devil: str = ""


JUDGE_SYSTEM_PROMPT = (
    "Tu es un évaluateur rigoureux de réponses RAG en français. Tu juges si la "
    "réponse est fidèle au CONTEXTE fourni et pertinente pour la QUESTION. "
    "Réponds UNIQUEMENT en JSON valide, sans texte ni balise autour. "
    'Format: {"score": float 0-1, "criteria": {"faithfulness": float 0-1, '
    '"relevance": float 0-1}, "reasoning": string court}.'
)

DEVIL_ADVOCATE_SYSTEM_PROMPT = (
    "Tu es un avocat du diable. Ton rôle est de détecter, dans la RÉPONSE, les "
    "affirmations qui ne sont PAS soutenues par le CONTEXTE fourni "
    "(hallucinations, extrapolations non fondées). Réponds UNIQUEMENT en JSON "
    'valide. Format: {"contested_claims": [liste de strings, chaque affirmation '
    'contestée citée ou paraphrasée], "confidence": float 0-1 de ta certitude}.'
)


def _build_judge_prompt(query: str, context: str, response: str) -> str:
    return (
        f"QUESTION:\n{query}\n\n"
        f"CONTEXTE FOURNI:\n{context}\n\n"
        f"RÉPONSE À ÉVALUER:\n{response}\n\n"
        "Rends le JSON."
    )


def _build_devil_prompt(query: str, context: str, response: str) -> str:
    return (
        f"QUESTION:\n{query}\n\n"
        f"CONTEXTE FOURNI:\n{context}\n\n"
        f"RÉPONSE À CONTESTER:\n{response}\n\n"
        "Rends le JSON. Si tout est soutenu par le contexte, retourne "
        '{"contested_claims": [], "confidence": 0.0}.'
    )


def _extract_json(raw: str) -> dict:
    cleaned = _JSON_FENCE_RE.sub("", raw.strip())
    return json.loads(cleaned)


def _default_eval_options() -> dict:
    settings = get_settings()
    return {
        "temperature": 0.0,
        "top_p": 1.0,
        "num_predict": settings.EVAL_NUM_PREDICT,
        "num_ctx": settings.EVAL_NUM_CTX,
    }


async def call_ollama_evaluator(
    prompt: str,
    system: str,
    *,
    client: httpx.AsyncClient | None = None,
    model: str | None = None,
    options: dict | None = None,
    timeout: float | None = None,
) -> dict:
    """Appel Ollama en mode JSON (format=json, temperature=0).

    Lève asyncio.TimeoutError / httpx.HTTPError / json.JSONDecodeError
    en cas d'échec — le caller décide du fallback (review_needed).
    """
    settings = get_settings()
    model = model or settings.OLLAMA_MODEL
    options = options or _default_eval_options()
    timeout = timeout if timeout is not None else settings.EVAL_TIMEOUT_S

    payload = {
        "model": model,
        "prompt": prompt,
        "system": system,
        "stream": False,
        "format": "json",
        "options": options,
    }

    own_client = client is None
    client = client or httpx.AsyncClient(timeout=timeout)
    try:
        async with asyncio.timeout(timeout):
            resp = await client.post(
                f"{settings.OLLAMA_HOST}/api/generate", json=payload
            )
            resp.raise_for_status()
            data = resp.json()
        raw = data.get("response", "")
        return _extract_json(raw)
    finally:
        if own_client:
            await client.aclose()


async def _run_judge(
    query: str,
    context: str,
    response: str,
    *,
    client: httpx.AsyncClient,
    model: str | None = None,
    options: dict | None = None,
    timeout: float | None = None,
) -> tuple[JudgeResult, str]:
    prompt = _build_judge_prompt(query, context, response)
    try:
        data = await call_ollama_evaluator(
            prompt, JUDGE_SYSTEM_PROMPT,
            client=client, model=model, options=options, timeout=timeout,
        )
        score = float(data.get("score", 0.0))
        criteria = {
            k: float(v) for k, v in (data.get("criteria") or {}).items()
        }
        return JudgeResult(
            score=score,
            criteria=criteria,
            reasoning=str(data.get("reasoning", "")),
        ), ""
    except Exception as exc:  # timeout / httpx / json
        logger.warning(f"Juge: échec évaluation → review_needed ({exc})")
        return JudgeResult(score=0.0, criteria={}, reasoning="eval_error"), ""


async def _run_devil_advocate(
    query: str,
    context: str,
    response: str,
    *,
    client: httpx.AsyncClient,
    model: str | None = None,
    options: dict | None = None,
    timeout: float | None = None,
) -> tuple[DevilAdvocateResult, str]:
    prompt = _build_devil_prompt(query, context, response)
    try:
        data = await call_ollama_evaluator(
            prompt, DEVIL_ADVOCATE_SYSTEM_PROMPT,
            client=client, model=model, options=options, timeout=timeout,
        )
        claims = [str(c) for c in (data.get("contested_claims") or [])]
        confidence = float(data.get("confidence", 0.0))
        return DevilAdvocateResult(
            contested_claims=claims, confidence=confidence
        ), ""
    except Exception as exc:
        logger.warning(f"Avocat: échec évaluation → aucun claim contesté ({exc})")
        return DevilAdvocateResult(contested_claims=[], confidence=0.0), ""


def _aggregate(judge: JudgeResult, devil: DevilAdvocateResult) -> AutoVerdict:
    if judge.reasoning == "eval_error":
        return AutoVerdict.REVIEW_NEEDED
    claims = len(devil.contested_claims)
    if judge.score < 0.5 and claims > 2:
        return AutoVerdict.REJECT
    if claims > 0 or judge.score < 0.6:
        return AutoVerdict.REVIEW_NEEDED
    return AutoVerdict.PASS


async def run_evaluation(
    query: str,
    context: str,
    response: str,
    *,
    client: httpx.AsyncClient | None = None,
    model: str | None = None,
    options: dict | None = None,
    timeout: float | None = None,
    conversation_id: str | None = None,
) -> AutoEvaluationPayload:
    """Orchestre Juge + Avocat SÉQUENTIELLEMENT (pas de gather)."""
    settings = get_settings()
    timeout = timeout if timeout is not None else settings.EVAL_TIMEOUT_S
    # Idempotence (MT-02.06) : run_id déterministe dérivé du conversation_id
    # (deux passes identiques → même run_id → ON CONFLICT DO NOTHING en DB).
    if conversation_id:
        run_id = hashlib.sha256(conversation_id.encode()).hexdigest()[:32]
    else:
        run_id = str(uuid.uuid4())

    own_client = client is None
    client = client or httpx.AsyncClient(timeout=timeout)
    try:
        judge, raw_judge = await _run_judge(
            query, context, response,
            client=client, model=model, options=options, timeout=timeout,
        )
        devil, raw_devil = await _run_devil_advocate(
            query, context, response,
            client=client, model=model, options=options, timeout=timeout,
        )
    finally:
        if own_client:
            await client.aclose()

    verdict = _aggregate(judge, devil)
    return AutoEvaluationPayload(
        conversation_id=conversation_id,
        evaluation_run_id=run_id,
        verdict=verdict,
        judge=judge,
        devil=devil,
        raw_judge=raw_judge,
        raw_devil=raw_devil,
    )


def build_issues(payload: AutoEvaluationPayload) -> list[dict]:
    """Construit les lignes response_issues à partir du payload (idempotent).

    Chaque claim contesté par l'Avocat → issue 'hallucination' (hash du claim).
    Score faible du Juge → issue 'low_relevance'. Le evaluation_run_id est
    partagé (déterministe) → ON CONFLICT DO NOTHING évite les doublons.
    """
    rid = payload.evaluation_run_id
    issues: list[dict] = []

    for claim in payload.devil.contested_claims:
        issues.append({
            "evaluation_run_id": rid,
            "issue_type": "hallucination",
            "claim_hash": hashlib.sha256(claim.encode()).hexdigest(),
            "description": claim[:500],
        })

    if payload.judge.score < 0.5:
        issues.append({
            "evaluation_run_id": rid,
            "issue_type": "low_relevance",
            "claim_hash": "score_low",
            "description": f"score={payload.judge.score}",
        })

    return issues

