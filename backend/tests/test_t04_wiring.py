"""Tests G2-T04 — Wiring dependencies : get_rag_engine() → LlamaCppClient.

Contrat (ticket 04 + GO XZ) :
- get_rag_engine() ne lit plus settings.OLLAMA_HOST ni settings.OLLAMA_MODEL ;
- RAGEngine.__init__ n'accepte plus ollama_host ni model_name, ne stocke plus
  self.ollama_host ni self.model_name, plus de valeur par défaut lue depuis
  settings.OLLAMA_HOST ;
- le LLMClient injecté est un LlamaCppClient construit via get_llm_client()
  (LLAMA_SERVER_URL, options T02/T03) — l'architecture existante (factory par
  appel via Depends) est conservée, aucun singleton inventé ;
- check_ollama_health est renommé check_llm_health ;
- aucun LLAMA_MODEL, aucun endpoint Ollama actif.

TDD : ces tests sont écrits avant l'implémentation (RED → GREEN).
"""
import inspect

from api.config import get_settings
from api.dependencies import LlamaCppClient, get_llm_client, get_rag_engine
from api.rag_engine import RAGEngine


def _build_engine():
    """Composition réelle du chemin actif : get_rag_engine avec deps factices."""
    return get_rag_engine(
        embedding_provider=object(),
        llm_client=get_llm_client(),
    )


class TestGetRagEngineWiring:
    """get_rag_engine() : chemin actif sans OLLAMA_*, client T03 effectif."""

    def test_get_rag_engine_ne_lit_plus_ollama_settings(self):
        import inspect
        from api.dependencies import get_rag_engine

        assert "OLLAMA" not in inspect.getsource(get_rag_engine)
        assert _build_engine() is not None

    def test_engine_recoit_llamacpp_client_reel(self):
        engine = _build_engine()
        assert isinstance(engine.llm_client, LlamaCppClient)

    def test_engine_url_depuis_llama_server_url(self):
        settings = get_settings()
        engine = _build_engine()
        assert engine.llm_client.base_url == settings.LLAMA_SERVER_URL.rstrip("/")

    def test_engine_options_transmises_depuis_settings_llama(self):
        settings = get_settings()
        engine = _build_engine()
        assert engine.llm_client.options == {
            "temperature": settings.LLAMA_TEMPERATURE,
            "top_p": settings.LLAMA_TOP_P,
            "top_k": settings.LLAMA_TOP_K,
            "max_tokens": settings.LLAMA_MAX_TOKENS,
        }

    async def test_llm_client_fourni_est_utilise_tel_quel(self):
        provided = get_llm_client()
        try:
            engine = get_rag_engine(
                embedding_provider=object(),
                llm_client=provided,
            )
            assert engine.llm_client is provided
        finally:
            await provided.close()


class TestRageEngineSansParametresOllama:
    """RAGEngine.__init__ : signature et attributs sans résidu Ollama."""

    def test_signature_sans_ollama_host_ni_model_name(self):
        params = list(inspect.signature(RAGEngine.__init__).parameters)
        assert params == [
            "self",
            "db_url",
            "embedding_provider",
            "llm_client",
        ]

    def test_instance_sans_attributs_ollama(self):
        engine = _build_engine()
        assert not hasattr(engine, "ollama_host")
        assert not hasattr(engine, "model_name")

    def test_classe_sans_get_settings_ollama_host(self):
        source = inspect.getsource(RAGEngine)
        assert "OLLAMA" not in source


class TestCheckLlmHealthRenommage:
    """Renommage exigé par le ticket : check_ollama_health → check_llm_health."""

    def test_check_llm_health_existe(self):
        assert hasattr(RAGEngine, "check_llm_health")

    def test_check_ollama_health_disparu_de_rag_engine(self):
        assert not hasattr(RAGEngine, "check_ollama_health")

    async def test_check_llm_health_dellegue_au_client(self):
        from unittest.mock import AsyncMock

        engine = _build_engine()
        engine.llm_client.check_health = AsyncMock(return_value=True)
        assert await engine.check_llm_health() is True
        engine.llm_client.check_health.assert_awaited_once()


class TestRaccordMainHealth:
    """Correction ciblée XZ : /health n'invoque plus de méthode Ollama renommée.

    main.py:141 appelait check_ollama_health(), méthode renommée check_llm_health
    par G2-T04 — l'AttributeError était absorbée par le try/except du handler,
    produisant un status « unavailable » masqué. Le point d'appel doit suivre
    l'interface LLM v1.4.
    """

    @staticmethod
    def _main_source() -> str:
        from pathlib import Path

        main_path = Path(__file__).resolve().parents[1] / "api" / "main.py"
        return main_path.read_text(encoding="utf-8")

    def test_health_nappelle_plus_check_ollama_health(self):
        assert "check_ollama_health" not in self._main_source()

    def test_health_apelle_la_methode_llm_existante(self):
        assert "check_llm_health" in self._main_source()
        assert callable(getattr(RAGEngine, "check_llm_health", None))
