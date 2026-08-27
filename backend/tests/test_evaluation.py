"""
Tests unitaires — Auto-évaluation RAG (Juge + Avocat du diable).
================================================================
Logique pure, client Ollama mocké (aucun GPU/DB réel).
"""
import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

from api.evaluation import (
    DEVIL_ADVOCATE_SYSTEM_PROMPT,
    JUDGE_SYSTEM_PROMPT,
    AutoEvaluationPayload,
    AutoVerdict,
    DevilAdvocateResult,
    JudgeResult,
    _aggregate,
    _run_devil_advocate,
    _run_judge,
    run_evaluation,
)


def _make_client(payload: dict | None = None, *, raw: str | None = None,
                 side_effect=None) -> AsyncMock:
    client = AsyncMock()
    resp = MagicMock()
    resp.raise_for_status = MagicMock()
    if side_effect is not None:
        client.post.side_effect = side_effect
        return client
    body = raw if raw is not None else json.dumps(payload)
    resp.json.return_value = {"response": body}
    client.post.return_value = resp
    client.aclose = AsyncMock()
    return client


# ═══════════════════════════════════════════════════════════════════════════════
# MT-01.03 — Tests prompts (juge + avocat)
# ═══════════════════════════════════════════════════════════════════════════════


class TestJudgePrompt:
    async def test_judge_returns_valid_score_range(self):
        client = _make_client({
            "score": 0.82,
            "criteria": {"faithfulness": 0.9, "relevance": 0.8},
            "reasoning": "Réponse fidèle et pertinente.",
        })
        judge, _ = await _run_judge("Qu'est-ce que TCP ?", "TCP est un protocole.",
                                    "TCP est un protocole de transport.",
                                    client=client)
        assert 0.0 <= judge.score <= 1.0
        assert judge.criteria["faithfulness"] == 0.9
        assert judge.criteria["relevance"] == 0.8
        assert judge.reasoning

    async def test_judge_posted_with_json_format(self):
        captured = {}
        client = _make_client({
            "score": 0.9, "criteria": {"faithfulness": 0.9, "relevance": 0.9},
            "reasoning": "ok",
        })

        async def fake_post(url, json=None, **kw):
            captured["json"] = json
            return MagicMock(raise_for_status=MagicMock(),
                             json=lambda: {"response": json.dumps({"score": 0.9,
                                 "criteria": {}, "reasoning": "ok"})})

        client.post.side_effect = fake_post
        await _run_judge("q", "c", "r", client=client)
        assert captured["json"]["format"] == "json"
        assert captured["json"]["options"]["temperature"] == 0.0


class TestDevilAdvocatePrompt:
    async def test_devil_flags_unsupported_claim(self):
        client = _make_client({
            "contested_claims": ["Le ciel est vert."],
            "confidence": 0.85,
        })
        devil, _ = await _run_devil_advocate("q", "Contexte sur réseau.",
                                             "Le ciel est vert.", client=client)
        assert len(devil.contested_claims) > 0
        assert devil.confidence > 0.0

    async def test_devil_empty_when_fully_supported(self):
        client = _make_client({
            "contested_claims": [],
            "confidence": 0.0,
        })
        devil, _ = await _run_devil_advocate("q", "TCP est fiable.",
                                             "TCP est fiable.", client=client)
        assert devil.contested_claims == []


# ═══════════════════════════════════════════════════════════════════════════════
# MT-01.02 / _aggregate — Matrice de décision
# ═══════════════════════════════════════════════════════════════════════════════


class TestAggregate:
    def test_pass_when_high_score_no_claims(self):
        verdict = _aggregate(
            JudgeResult(score=0.9, criteria={}, reasoning="ok"),
            DevilAdvocateResult(contested_claims=[], confidence=0.0),
        )
        assert verdict == AutoVerdict.PASS

    def test_review_when_low_score(self):
        verdict = _aggregate(
            JudgeResult(score=0.4, criteria={}, reasoning="ok"),
            DevilAdvocateResult(contested_claims=[], confidence=0.0),
        )
        assert verdict == AutoVerdict.REVIEW_NEEDED

    def test_reject_when_low_score_many_claims(self):
        verdict = _aggregate(
            JudgeResult(score=0.4, criteria={}, reasoning="ok"),
            DevilAdvocateResult(contested_claims=["a", "b", "c"], confidence=0.9),
        )
        assert verdict == AutoVerdict.REJECT

    def test_review_when_claims_present(self):
        verdict = _aggregate(
            JudgeResult(score=0.85, criteria={}, reasoning="ok"),
            DevilAdvocateResult(contested_claims=["x"], confidence=0.7),
        )
        assert verdict == AutoVerdict.REVIEW_NEEDED

    def test_review_when_eval_error(self):
        verdict = _aggregate(
            JudgeResult(score=0.0, criteria={}, reasoning="eval_error"),
            DevilAdvocateResult(contested_claims=[], confidence=0.0),
        )
        assert verdict == AutoVerdict.REVIEW_NEEDED


# ═══════════════════════════════════════════════════════════════════════════════
# MT-01.06 — Exécution SÉQUENTIELLE (pas de gather)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSequentialOrder:
    async def test_judge_called_before_devil(self):
        captured = []

        client = _make_client({
            "score": 0.8, "criteria": {"faithfulness": 0.8, "relevance": 0.8},
            "reasoning": "ok",
        })

        async def fake_post(url, json=None, **kw):
            captured.append(json["system"])
            return MagicMock(raise_for_status=MagicMock(),
                             json=lambda: {"response": json.dumps({
                                 "score": 0.8, "criteria": {}, "reasoning": "ok",
                                 "contested_claims": [], "confidence": 0.0})})

        client.post.side_effect = fake_post
        await run_evaluation("q", "c", "r", client=client)

        assert captured[0] == JUDGE_SYSTEM_PROMPT
        assert captured[1] == DEVIL_ADVOCATE_SYSTEM_PROMPT
        assert len(captured) == 2


# ═══════════════════════════════════════════════════════════════════════════════
# MT-01.07 — Résilience (JSON malformé, timeout)
# ═══════════════════════════════════════════════════════════════════════════════


class TestResilience:
    async def test_judge_handles_malformed_json_output(self):
        client = _make_client(raw="{not valid json")
        judge, _ = await _run_judge("q", "c", "r", client=client)
        assert judge.reasoning == "eval_error"
        assert judge.score == 0.0

    async def test_evaluate_response_handles_timeout_gracefully(self):
        client = _make_client(side_effect=TimeoutError())
        payload = await run_evaluation("q", "c", "r", client=client)
        # Pas de crash : verdict sûr, aucune écriture partielle (Phase 2)
        assert payload.verdict == AutoVerdict.REVIEW_NEEDED
        assert payload.judge.reasoning == "eval_error"

    async def test_devil_handles_malformed_json(self):
        client = _make_client(raw="<<<")
        devil, _ = await _run_devil_advocate("q", "c", "r", client=client)
        assert devil.contested_claims == []
        assert devil.confidence == 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# MT-02.02 / MT-02.06 — Persistance auto-évaluation (UPSERT symétrique + idempotence)
# ═══════════════════════════════════════════════════════════════════════════════


class TestSaveAutoEvaluation:
    async def test_does_not_overwrite_human_review_fields(self):
        from api.database import save_auto_evaluation

        conn = AsyncMock()
        await save_auto_evaluation(
            conn, "conv-1", 0.8, {"faithfulness": 0.8}, "run-1",
            issues=[{"evaluation_run_id": "run-1", "issue_type": "hallucination",
                     "claim_hash": "abc", "description": "x"}],
        )
        # Récupère tout le SQL exécuté
        sqls = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
        assert "human_rating" not in sqls
        assert "human_feedback" not in sqls
        assert "is_golden" not in sqls
        assert "auto_score" in sqls
        assert "auto_criteria" in sqls

    async def test_save_feedback_does_not_overwrite_auto_score(self):
        from api.database import save_feedback

        conn = AsyncMock()
        await save_feedback(conn, "conv-1", 5, "super", True)
        sqls = " ".join(str(c.args[0]) for c in conn.execute.call_args_list)
        assert "auto_score" not in sqls
        assert "auto_criteria" not in sqls
        assert "human_rating" in sqls

    async def test_issues_insert_is_idempotent_sql(self):
        from api.database import save_auto_evaluation

        conn = AsyncMock()
        await save_auto_evaluation(
            conn, "conv-1", 0.8, {}, "run-1",
            issues=[{"evaluation_run_id": "run-1", "issue_type": "hallucination",
                     "claim_hash": "abc", "description": "x"}],
        )
        issues_sql = None
        for c in conn.execute.call_args_list:
            if "response_issues" in str(c.args[0]):
                issues_sql = str(c.args[0])
        assert issues_sql is not None
        assert "ON CONFLICT (conversation_id, evaluation_run_id, issue_type, claim_hash)" in issues_sql
        assert "DO NOTHING" in issues_sql


class TestBuildIssues:
    def test_build_issues_from_devil_claims(self):
        from api.evaluation import AutoEvaluationPayload, build_issues

        payload = AutoEvaluationPayload(
            conversation_id="conv-1",
            evaluation_run_id="run-1",
            verdict=AutoVerdict.REVIEW_NEEDED,
            judge=JudgeResult(score=0.7, criteria={}, reasoning="ok"),
            devil=DevilAdvocateResult(
                contested_claims=["Le ciel est vert."], confidence=0.8),
        )
        issues = build_issues(payload)
        assert len(issues) == 1
        assert issues[0]["issue_type"] == "hallucination"
        assert issues[0]["evaluation_run_id"] == "run-1"
        assert issues[0]["claim_hash"] == __import__("hashlib").sha256(
            b"Le ciel est vert.").hexdigest()

    def test_build_issues_low_score_adds_low_relevance(self):
        from api.evaluation import AutoEvaluationPayload, build_issues

        payload = AutoEvaluationPayload(
            conversation_id="conv-1",
            evaluation_run_id="run-1",
            verdict=AutoVerdict.REJECT,
            judge=JudgeResult(score=0.3, criteria={}, reasoning="eval_error"),
            devil=DevilAdvocateResult(contested_claims=[], confidence=0.0),
        )
        issues = build_issues(payload)
        assert any(i["issue_type"] == "low_relevance" for i in issues)


# ═══════════════════════════════════════════════════════════════════════════════
# MT-02.03 — FK race : _eval_after_persist attend la persistance
# MT-02.05 — Échantillonnage déterministe EVAL_SAMPLE_RATE
# ═══════════════════════════════════════════════════════════════════════════════


class TestEvalAfterPersist:
    async def test_waits_for_conversation_persisted(self, monkeypatch):
        import sys

        import api.main as m

        order = []

        async def fake_persist():
            order.append("persist")

        persist_task = asyncio.create_task(fake_persist())

        async def fake_save(*a, **k):
            order.append("save")

        payload = AutoEvaluationPayload(
            conversation_id="conv-1",
            evaluation_run_id="run-1",
            verdict=AutoVerdict.PASS,
            judge=JudgeResult(score=0.9, criteria={}, reasoning="ok"),
            devil=DevilAdvocateResult(contested_claims=[], confidence=0.0),
        )

        # Mock httpx.AsyncClient au niveau module sys pour bypasser le MagicMock du conftest
        class MockClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        monkeypatch.setattr(sys.modules["httpx"], "AsyncClient", lambda *a, **k: MockClient())
        monkeypatch.setattr(m, "run_evaluation", AsyncMock(return_value=payload))
        monkeypatch.setattr(m, "save_auto_evaluation", fake_save)

        class MockConn:
            pass

        class MockPool:
            def acquire(self):
                class _AcquireCtx:
                    async def __aenter__(self):
                        return MockConn()
                    async def __aexit__(self, *args):
                        pass
                return _AcquireCtx()

        mock_pool = MockPool()
        monkeypatch.setattr(m, "get_db", AsyncMock(return_value=mock_pool))
        monkeypatch.setattr(m.settings, "AUTO_EVALUATE", True)
        monkeypatch.setattr(m.settings, "EVAL_SAMPLE_RATE", 1.0)

        await m._eval_after_persist(persist_task, "conv-1", "q", "ctx", "resp")

        assert order == ["persist", "save"]

    async def test_skips_when_auto_evaluate_false(self, monkeypatch):
        import sys

        import api.main as m

        persist_task = asyncio.create_task(asyncio.sleep(0))
        saved = []

        async def fake_save(*a, **k):
            saved.append(True)

        class MockClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        monkeypatch.setattr(sys.modules["httpx"], "AsyncClient", lambda *a, **k: MockClient())
        monkeypatch.setattr(m, "run_evaluation", AsyncMock())
        monkeypatch.setattr(m, "save_auto_evaluation", fake_save)
        monkeypatch.setattr(m.settings, "AUTO_EVALUATE", False)

        await m._eval_after_persist(persist_task, "conv-1", "q", "ctx", "resp")
        assert saved == []

    async def test_sample_rate_zero_skips(self, monkeypatch):
        import sys

        import api.main as m

        persist_task = asyncio.create_task(asyncio.sleep(0))
        saved = []

        async def fake_save(*a, **k):
            saved.append(True)

        class MockClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        monkeypatch.setattr(sys.modules["httpx"], "AsyncClient", lambda *a, **k: MockClient())
        monkeypatch.setattr(m, "run_evaluation", AsyncMock())
        monkeypatch.setattr(m, "save_auto_evaluation", fake_save)
        monkeypatch.setattr(m.settings, "AUTO_EVALUATE", True)
        monkeypatch.setattr(m.settings, "EVAL_SAMPLE_RATE", 0.0)

        await m._eval_after_persist(persist_task, "conv-1", "q", "ctx", "resp")
        assert saved == []

    async def test_sample_rate_one_always_runs(self, monkeypatch):
        import sys

        import api.main as m

        persist_task = asyncio.create_task(asyncio.sleep(0))
        saved = []

        async def fake_save(*a, **k):
            saved.append(True)

        payload = AutoEvaluationPayload(
            conversation_id="conv-1",
            evaluation_run_id="run-1",
            verdict=AutoVerdict.PASS,
            judge=JudgeResult(score=0.9, criteria={}, reasoning="ok"),
            devil=DevilAdvocateResult(contested_claims=[], confidence=0.0),
        )

        class MockClient:
            async def __aenter__(self):
                return self
            async def __aexit__(self, *args):
                pass

        class MockConn:
            pass

        class MockPool:
            def acquire(self):
                class _AcquireCtx:
                    async def __aenter__(self):
                        return MockConn()
                    async def __aexit__(self, *args):
                        pass
                return _AcquireCtx()

        mock_pool = MockPool()
        monkeypatch.setattr(sys.modules["httpx"], "AsyncClient", lambda *a, **k: MockClient())
        monkeypatch.setattr(m, "run_evaluation", AsyncMock(return_value=payload))
        monkeypatch.setattr(m, "save_auto_evaluation", fake_save)
        monkeypatch.setattr(m, "get_db", AsyncMock(return_value=mock_pool))
        monkeypatch.setattr(m.settings, "AUTO_EVALUATE", True)
        monkeypatch.setattr(m.settings, "EVAL_SAMPLE_RATE", 1.0)

        await m._eval_after_persist(persist_task, "conv-1", "q", "ctx", "resp")
        assert saved == [True]
