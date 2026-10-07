"""Tests G2-T03 — LlamaCppClient : client d'inférence llama.cpp (API OpenAI-compatible).

Contrat (ticket 03) :
- Construction LlamaCppClient(base_url, options) — aucun paramètre « model »,
  aucun settings LLAMA_MODEL (arbitrage XZ T03).
- generate() : POST {base_url}/v1/chat/completions, messages [system, user],
  options en champs plats, parse choices[0].message.content.
- check_health() : GET {base_url}/health.
- close() : fermeture du transport HTTP.
- get_llm_client() : LlamaCppClient(settings.LLAMA_SERVER_URL, options) —
  le modèle est configuré côté llama.cpp/systemd, jamais côté backend.

TDD : ces tests sont écrits avant l'implémentation (RED → GREEN).
"""
import inspect
import json
from unittest.mock import AsyncMock, MagicMock

import httpx

from api.config import get_settings
from api.dependencies import LlamaCppClient, get_llm_client

BASE_URL = "http://llama-host:8081"
OPTIONS = {
    "temperature": 0.3,
    "top_p": 0.9,
    "top_k": 40,
    "max_tokens": 1024,
}


def _client_with_capture(handler, base_url=BASE_URL, options=None):
    """Construit un LlamaCppClient dont le transport HTTP est un MockTransport.

    La requête réelle (méthode, URL, corps) est capturée par le handler.
    """
    client = LlamaCppClient(base_url, dict(OPTIONS if options is None else options))
    client._client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return client


class TestConstruction:
    """Construction : signature exacte, URL injectable, aucun champ « model ».

    La signature est un contrat XZ (aucun paramètre « model ») : testée
    strictement, tout ajout de paramètre exige une arbitrage.
    """

    def test_signature_n_accepte_que_base_url_et_options(self):
        params = list(inspect.signature(LlamaCppClient.__init__).parameters)
        assert params == ["self", "base_url", "options"]

    def test_instance_sans_attribut_model(self):
        client = LlamaCppClient(BASE_URL, {})
        assert not hasattr(client, "model")

    def test_timeout_transport_180(self):
        client = LlamaCppClient(BASE_URL, {})
        assert client._client.timeout.connect == 180.0

    async def test_url_configurable(self):
        captured = {}

        def handler(request):
            captured["url"] = str(request.url)
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        client = _client_with_capture(handler, base_url="http://127.0.0.1:9999")
        await client.generate("test", "sys")
        assert captured["url"] == "http://127.0.0.1:9999/v1/chat/completions"

    async def test_slash_final_normalise(self):
        captured = {}

        def handler(request):
            captured["path"] = request.url.path
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        client = _client_with_capture(handler, base_url="http://llama-host:8081/")
        await client.generate("test", "sys")
        assert captured["path"] == "/v1/chat/completions"


class TestGenerate:
    """generate() : endpoint OpenAI, payload, parsing, tolérance aux erreurs."""

    async def test_poste_vers_v1_chat_completions(self):
        captured = {}

        def handler(request):
            captured["method"] = request.method
            captured["path"] = request.url.path
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"choices": [{"message": {"content": "Bonjour"}}]})

        client = _client_with_capture(handler)
        result = await client.generate("Salut", "Tu es un prof")
        assert captured["method"] == "POST"
        assert captured["path"] == "/v1/chat/completions"
        assert result == "Bonjour"

    async def test_payload_messages_system_puis_user(self):
        captured = {}

        def handler(request):
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        client = _client_with_capture(handler)
        await client.generate("Question élève", "Consigne prof")
        assert captured["body"]["messages"] == [
            {"role": "system", "content": "Consigne prof"},
            {"role": "user", "content": "Question élève"},
        ]

    async def test_payload_sans_champ_model(self):
        captured = {}

        def handler(request):
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        client = _client_with_capture(handler)
        await client.generate("test", "sys")
        assert "model" not in captured["body"]

    async def test_payload_options_en_champs_plats(self):
        captured = {}

        def handler(request):
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        client = _client_with_capture(handler)
        await client.generate("test", "sys")
        assert captured["body"]["temperature"] == 0.3
        assert captured["body"]["top_p"] == 0.9
        assert captured["body"]["top_k"] == 40
        assert captured["body"]["max_tokens"] == 1024

    async def test_erreur_http_renvoie_chaine_sans_lever(self):
        def handler(request):
            return httpx.Response(500, json={"error": "boom"})

        client = _client_with_capture(handler)
        result = await client.generate("test", "sys")
        assert isinstance(result, str)
        assert result.startswith("Erreur lors de la génération")

    async def test_erreur_transport_renvoie_chaine_sans_lever(self):
        def handler(request):
            raise httpx.ConnectError("connexion refusée", request=request)

        client = _client_with_capture(handler)
        result = await client.generate("test", "sys")
        assert isinstance(result, str)
        assert result.startswith("Erreur lors de la génération")

    async def test_reponse_sans_choices_renvoie_chaine_vide(self):
        def handler(request):
            return httpx.Response(200, json={"object": "chat.completion"})

        client = _client_with_capture(handler)
        result = await client.generate("test", "sys")
        assert result == "Erreur : réponse llama.cpp vide"

    async def test_reponse_json_invalide_renvoie_chaine_erreur(self):
        def handler(request):
            return httpx.Response(200, text="<html>proxy error</html>")

        client = _client_with_capture(handler)
        result = await client.generate("test", "sys")
        assert isinstance(result, str)
        assert result.startswith("Erreur lors de la génération")

    async def test_content_null_renvoie_chaine_vide(self):
        def handler(request):
            return httpx.Response(200, json={"choices": [{"message": {"content": None}}]})

        client = _client_with_capture(handler)
        result = await client.generate("test", "sys")
        assert result == "Erreur : réponse llama.cpp vide"

    async def test_options_ne_peuvent_pas_ecraser_messages(self):
        captured = {}

        def handler(request):
            captured["body"] = json.loads(request.content)
            return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

        client = _client_with_capture(
            handler, options={"messages": "injection", "temperature": 0.1}
        )
        await client.generate("test", "sys")
        assert captured["body"]["messages"] == [
            {"role": "system", "content": "sys"},
            {"role": "user", "content": "test"},
        ]


class TestCheckHealth:
    """check_health() : GET /health, True si prêt, False sinon."""

    async def test_health_ok(self):
        captured = {}

        def handler(request):
            captured["method"] = request.method
            captured["path"] = request.url.path
            return httpx.Response(200, json={"status": "ok"})

        client = _client_with_capture(handler)
        assert await client.check_health() is True
        assert captured["method"] == "GET"
        assert captured["path"] == "/health"

    async def test_serveur_absent_renvoie_false(self):
        def handler(request):
            raise httpx.ConnectError("connexion refusée", request=request)

        client = _client_with_capture(handler)
        assert await client.check_health() is False

    async def test_chargement_en_cours_503_renvoie_false(self):
        def handler(request):
            return httpx.Response(503, json={"error": "loading model"})

        client = _client_with_capture(handler)
        assert await client.check_health() is False


class TestCloseEtProtocole:
    """close() et conformité structurelle au protocole LLMClient."""

    async def test_close_ferme_le_transport(self):
        client = LlamaCppClient(BASE_URL, {})
        client._client = MagicMock()
        client._client.aclose = AsyncMock()
        await client.close()
        client._client.aclose.assert_awaited_once()

    def test_methodes_sont_des_coroutines(self):
        client = LlamaCppClient(BASE_URL, {})
        assert inspect.iscoroutinefunction(client.generate)
        assert inspect.iscoroutinefunction(client.check_health)
        assert inspect.iscoroutinefunction(client.close)


class TestFactoryGetLlmClient:
    """get_llm_client() : LlamaCppClient + LLAMA_SERVER_URL + options LLAMA_*."""

    async def test_retourne_llamacppclient(self):
        client = get_llm_client()
        try:
            assert isinstance(client, LlamaCppClient)
        finally:
            await client.close()

    async def test_utilise_llama_server_url_et_options_llama(self):
        settings = get_settings()
        client = get_llm_client()
        try:
            assert client.base_url == settings.LLAMA_SERVER_URL.rstrip("/")
            assert client.options == {
                "temperature": settings.LLAMA_TEMPERATURE,
                "top_p": settings.LLAMA_TOP_P,
                "top_k": settings.LLAMA_TOP_K,
                "max_tokens": settings.LLAMA_MAX_TOKENS,
            }
        finally:
            await client.close()

    async def test_options_sans_cle_ollama_ni_model(self):
        client = get_llm_client()
        try:
            assert not any(key.startswith("OLLAMA_") for key in client.options)
            assert "model" not in client.options
            assert "num_predict" not in client.options
            assert "num_ctx" not in client.options
        finally:
            await client.close()
