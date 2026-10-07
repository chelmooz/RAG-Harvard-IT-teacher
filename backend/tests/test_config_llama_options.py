"""Tests G2-T02 — Config llama.cpp : contrat backend minimal.

Seams pré-convenus (XZ règle 6) : interface publique `Settings` / `get_settings()`
(injection env incluse) et greps d'acceptation du ticket 02.

Rappel architecture (ADR-002/003) :
  backend → LLAMA_SERVER_URL=http://llama-host:8081 → llama.cpp host/systemd → Vulkan/RADV
Le modèle est configuré côté service llama.cpp : le backend ne possède AUCUNE
variable de sélection de modèle (décision XZ #1). Les options de PROCESSUS
llama.cpp (-ngl, -c, -ctk, -ctv, -np, -fa, -b, -ub, --jinja, f16_kv, n_threads)
ne sont PAS des paramètres backend (XZ règle 4).
"""
import pytest

from api.config import Settings, get_settings

# Les 10 champs OLLAMA_* hérités que T02 doit supprimer de Settings.
OLLAMA_FIELDS = [
    "OLLAMA_HOST",
    "OLLAMA_MODEL",
    "OLLAMA_TEMPERATURE",
    "OLLAMA_TOP_P",
    "OLLAMA_TOP_K",
    "OLLAMA_NUM_PREDICT",
    "OLLAMA_NUM_CTX",
    "OLLAMA_NUM_THREAD",
    "OLLAMA_NUM_GPU",
    "OLLAMA_F16_KV",
]

# Transposition mécanique INTERDITE (XZ règle 4) : ces noms ne doivent jamais
# apparaître comme champs Settings — ce sont des options du processus llama.cpp.
# Les flags sans équivalent de nom (-ctk, -ctv, -np, -fa, -b, -ub, --jinja)
# n'ont pas de nom de champ à tester : l'absence des 4 ci-dessous + la liste
# OLLAMA_FIELDS couvrent le principe « aucune option de processus côté backend ».
PROCESS_OPTION_FIELDS = [
    "LLAMA_NUM_CTX",       # -c (contexte, côté serveur llama.cpp)
    "LLAMA_N_THREADS",     # n_threads (lanceur)
    "LLAMA_NUM_GPU",       # -ngl (lanceur)
    "LLAMA_F16_KV",        # cache KV, côté serveur
]


class TestLlamaServerUrl:
    """LLAMA_SERVER_URL = contrat unique backend → llama.cpp."""

    def test_valeur_par_defaut(self, monkeypatch):
        monkeypatch.delenv("LLAMA_SERVER_URL", raising=False)
        assert Settings(_env_file=None).LLAMA_SERVER_URL == "http://llama-host:8081"

    def test_injection_env(self, monkeypatch):
        monkeypatch.setenv("LLAMA_SERVER_URL", "http://autre-host:9090")
        assert Settings().LLAMA_SERVER_URL == "http://autre-host:9090"

    def test_get_settings_expose_le_contrat(self, monkeypatch):
        # Singleton lru_cache : premier appel de la suite (conftest n'injecte
        # pas LLAMA_SERVER_URL) → défaut canonique documenté ici.
        monkeypatch.delenv("LLAMA_SERVER_URL", raising=False)
        assert get_settings().LLAMA_SERVER_URL == "http://llama-host:8081"


class TestAucunLlamaModel:
    """Décision XZ #1 : NE PAS créer LLAMA_MODEL (modèle configuré côté llama.cpp)."""

    def test_llama_model_n_est_pas_un_champ(self):
        assert "LLAMA_MODEL" not in Settings.model_fields

    def test_llama_model_absent_de_l_instance(self):
        assert not hasattr(Settings(), "LLAMA_MODEL")


class TestChampsOllamaSupprimes:
    """T02 : les 10 champs OLLAMA_* quittent la classe Settings."""

    @pytest.mark.parametrize("field", OLLAMA_FIELDS)
    def test_champ_supprime(self, field):
        assert field not in Settings.model_fields

    @pytest.mark.parametrize("field", OLLAMA_FIELDS)
    def test_champ_absent_de_l_instance(self, field):
        assert not hasattr(Settings(), field)

    @pytest.mark.parametrize("field", OLLAMA_FIELDS)
    def test_variable_env_ollama_ne_devient_pas_active(self, field, monkeypatch):
        """Aucun OLLAMA_* en environnement ne doit (ré)activer un réglage."""
        monkeypatch.setenv(field, "valeur-legacy")
        assert not hasattr(Settings(), field)


class TestOptionsClientLlamaCpp:
    """Seules les options d'appel API (client HTTP) restent dans le backend.

    Valeurs calibrées BC-250 conservées (points de départ, pas garanties).
    """

    def test_valeurs_calibrees(self, monkeypatch):
        for f in ("LLAMA_TEMPERATURE", "LLAMA_TOP_P", "LLAMA_TOP_K", "LLAMA_MAX_TOKENS"):
            monkeypatch.delenv(f, raising=False)
        s = Settings(_env_file=None)
        assert s.LLAMA_TEMPERATURE == 0.3
        assert s.LLAMA_TOP_P == 0.9
        assert s.LLAMA_TOP_K == 40
        assert s.LLAMA_MAX_TOKENS == 1024  # ancien num_predict (OpenAI: max_tokens)

    def test_injection_env(self, monkeypatch):
        monkeypatch.setenv("LLAMA_MAX_TOKENS", "512")
        assert Settings().LLAMA_MAX_TOKENS == 512


class TestOptionsProcessusInterdites:
    """XZ règle 4 : aucune option de processus llama.cpp dans Settings."""

    @pytest.mark.parametrize("field", PROCESS_OPTION_FIELDS)
    def test_absente_de_settings(self, field):
        assert field not in Settings.model_fields


class TestParamsCpuPreserves:
    """Compatibilité (XZ règle 5) : BGE-M3 CPU, reranker CPU, BATCH_SIZE.

    Le reranker n'a AUCUN réglage dans Settings (ses paramètres vivent dans
    rag_engine — périmètre T00/T05) : rien à préserver à ce seam, seul le
    chemin CPU BGE-M3/BATCH_SIZE est garanti ici.
    """

    def test_embedder_et_batch_inchanges(self):
        s = Settings()
        assert s.EMBEDDING_MODEL == "BAAI/bge-m3"
        assert s.EMBEDDING_BATCH_SIZE == 64
        assert s.AMD_GTT_SIZE_MB == 12288
        assert s.AMD_RDNA2_CUS == 24
        assert s.AMD_CU_UNLOCK_APPLIED is False
        assert s.HSA_OVERRIDE_GFX_VERSION == "10.1.3"  # LEGACY, non injecté (T00)


class TestAutresSettingsNonRegresses:
    """Les autres settings existants ne régressent pas (XZ règle 6)."""

    def test_rag_db_eval_inchanges(self):
        s = Settings()
        assert s.RAG_THRESHOLD == 0.72
        assert s.RAG_TOP_K == 5
        assert s.CHUNK_SIZE == 400
        assert s.CHUNK_OVERLAP == 80
        # DATABASE_URL/API_TOKEN sont injectés par l'env (conftest/.env) :
        # seuls leur présence et leur type sont stables ici.
        assert isinstance(s.DATABASE_URL, str)
        assert s.EVAL_TIMEOUT_S == 15.0
        assert s.EVAL_NUM_PREDICT == 150
        assert s.EVAL_NUM_CTX == 2048
        assert s.EVAL_SAMPLE_RATE == 1.0

    def test_securite_et_app_inchanges(self):
        s = Settings()
        assert s.CORS_ORIGINS == "http://localhost:3000,http://127.0.0.1:3000"
        assert isinstance(s.API_TOKEN, str)
        assert isinstance(s.API_TOKEN_SOURCE, str)
        assert s.DEBUG is False
        assert s.APP_VERSION == "6.0.0"
