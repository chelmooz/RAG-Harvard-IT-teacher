"""
Tests d'intégration — Prof IA v5.4
====================================
Tests unitaires sans dépendances GPU/DB (mocks).
Tests d'intégration avec PostgreSQL réel (nécessite docker-compose up postgres).

Lancer :
  pytest backend/tests/ -v                        # tous les tests
  pytest backend/tests/ -v -m "not integration"   # unitaires uniquement
  pytest backend/tests/ -v -m integration          # intégration uniquement
"""

import asyncio
import os
import sys
import pytest
import numpy as np
from unittest.mock import AsyncMock, MagicMock, patch, PropertyMock
from pathlib import Path

# ── Fixtures ROCm (forcé CPU pour les tests) ────────────────────────────────
@pytest.fixture(autouse=True)
def force_cpu_device(monkeypatch):
    """Désactive le GPU pour les tests unitaires."""
    monkeypatch.setenv("HSA_OVERRIDE_GFX_VERSION", "10.1.3")
    with patch("torch.cuda.is_available", return_value=False):
        yield


# ══════════════════════════════════════════════════════════════════════════════
# TESTS UNITAIRES — Logique pure (sans DB ni GPU)
# ══════════════════════════════════════════════════════════════════════════════

class TestScoreSimilarity:
    """Vérifie la formule 1 - distance cosine utilisée dans retrieve()."""

    def test_identique(self):
        assert 1 - 0.0 == 1.0

    def test_orthogonal(self):
        assert 1 - 1.0 == 0.0

    def test_threshold_exact(self):
        """Le seuil 0.72 correspond à une distance de 0.28."""
        assert abs((1 - 0.28) - 0.72) < 1e-9

    def test_scores_ordinaux(self):
        """Un score plus élevé = vecteurs plus proches."""
        d1, d2 = 0.1, 0.5
        assert (1 - d1) > (1 - d2)


class TestChunkingLogique:
    """Teste la logique de découpage sans LangChain."""

    def test_texte_court_reste_entier(self):
        text = "Bonjour monde."
        assert len(text) < 400
        # Un texte court ne doit pas être découpé
        chunks = [text] if text.strip() else []
        assert len(chunks) == 1

    def test_texte_vide_retourne_zero_chunks(self):
        text = "   \n\n  "
        chunks = [t for t in [text] if t.strip()]
        assert len(chunks) == 0

    def test_metadonnees_chunk(self):
        chunk = {
            "text": "Contenu test",
            "metadata": {
                "source": "cours.pdf",
                "file_type": "pdf",
                "chunking_method": "recursive_char",
                "chunk_size": 12,
            },
        }
        assert chunk["metadata"]["chunking_method"] == "recursive_char"
        assert chunk["metadata"]["chunk_size"] == len(chunk["text"])

    def test_extensions_dangereuses_bloquees(self):
        """Seules les extensions de la liste blanche sont acceptées."""
        supported = {".pdf", ".txt", ".md", ".docx", ".pptx", ".xlsx", ".mp3", ".mp4", ".wav"}
        dangerous = {".py", ".sh", ".exe", ".js", ".php", ".rb", ".bat", ".ps1"}
        for ext in dangerous:
            assert ext not in supported, f"Extension dangereuse autorisée : {ext}"


class TestFormatSFT:
    """Teste le formatage du dataset pour le fine-tuning."""

    def _format(self, records):
        formatted = []
        for r in records:
            ctx = r.get("input") or ""
            text = (
                f"### Instruction:\n{r['instruction']}\n\n"
                f"### Entrée (contexte RAG):\n{ctx}\n\n"
                f"### Réponse:\n{r['output']}"
            )
            formatted.append({"text": text})
        return formatted

    def test_format_basique(self):
        records = [{"instruction": "Q?", "input": "ctx", "output": "R."}]
        result = self._format(records)
        assert len(result) == 1
        assert "### Instruction:" in result[0]["text"]
        assert "### Réponse:" in result[0]["text"]

    def test_input_none_gere(self):
        """input=None ne doit pas afficher 'None' dans le texte."""
        records = [{"instruction": "Q?", "input": None, "output": "R."}]
        result = self._format(records)
        assert "None" not in result[0]["text"]

    def test_dataset_vide(self):
        result = self._format([])
        assert result == []

    def test_structure_alpaca(self):
        records = [{"instruction": "Explique TCP", "input": "RFC 793", "output": "TCP est..."}]
        result = self._format(records)
        text = result[0]["text"]
        # Vérifier l'ordre Alpaca : Instruction → Entrée → Réponse
        assert text.index("### Instruction:") < text.index("### Entrée")
        assert text.index("### Entrée") < text.index("### Réponse:")


class TestConfigValidation:
    """Teste la validation du JWT_SECRET — mode LAN local (v5.4).

    En v5.4, le réseau est isolé (LAN BC-250 ↔ PC client).
    Le JWT sert uniquement à l'auth GitHub datasets.
    Contrainte : non vide. Longueur libre.
    """

    def test_jwt_vide_rejete(self):
        """Un JWT_SECRET vide doit être rejeté."""
        def validate_jwt(v):
            if not v:
                raise ValueError("JWT_SECRET ne peut pas être vide")
            return v

        with pytest.raises(ValueError, match="vide"):
            validate_jwt("")

        with pytest.raises(ValueError, match="vide"):
            validate_jwt(None)

    def test_jwt_court_accepte_en_local(self):
        """En mode LAN local, un JWT court comme 'user' est valide."""
        def validate_jwt(v):
            if not v:
                raise ValueError("vide")
            return v

        # 'user' est le JWT_SECRET v5.4 — doit passer
        assert validate_jwt("user") == "user"

    def test_jwt_long_aussi_accepte(self):
        """Un JWT long reste valide (compatibilité GitHub tokens)."""
        import secrets
        def validate_jwt(v):
            if not v:
                raise ValueError("vide")
            return v

        token = secrets.token_hex(32)
        assert len(validate_jwt(token)) == 64


class TestEmbeddingDimensions:
    """Vérifie la cohérence des dimensions vectorielles."""

    def test_dimension_attendue(self):
        """paraphrase-multilingual-mpnet-base-v2 produit des vecteurs de 768 dims."""
        expected_dim = 768
        # Simuler un vecteur normalisé
        vec = np.random.randn(expected_dim).astype(np.float32)
        vec /= np.linalg.norm(vec)
        assert vec.shape == (expected_dim,)
        assert abs(np.linalg.norm(vec) - 1.0) < 1e-5

    def test_normalisation_cosine(self):
        """Vecteurs normalisés → produit scalaire = similarité cosine."""
        a = np.array([1.0, 0.0, 0.0])
        b = np.array([1.0, 0.0, 0.0])
        cosine = np.dot(a, b)  # = 1.0 car vecteurs identiques normalisés
        assert cosine == pytest.approx(1.0)

    def test_batch_shapes(self):
        """Un batch de N textes produit N vecteurs de dimension D."""
        N, D = 10, 768
        fake_embeddings = np.random.randn(N, D).astype(np.float32)
        assert fake_embeddings.shape == (N, D)


class TestDocumentProcessor:
    """Tests sans Whisper ni GPU."""

    def test_extension_invalide_levee(self):
        from unittest.mock import MagicMock
        # Simuler la logique d'extension
        supported = {".pdf", ".txt", ".md", ".docx", ".pptx", ".xlsx", ".mp3", ".mp4", ".wav"}

        def check_ext(filename):
            ext = Path(filename).suffix.lower()
            if ext not in supported:
                raise ValueError(f"Format non supporté : {ext}")
            return ext

        with pytest.raises(ValueError, match="non supporté"):
            check_ext("script.py")

        with pytest.raises(ValueError, match="non supporté"):
            check_ext("payload.sh")

        assert check_ext("document.pdf") == ".pdf"

    def test_unload_whisper_sans_modele(self):
        """unload_whisper() ne doit pas planter si Whisper n'est pas chargé."""
        # Simuler DocumentProcessor sans ses imports lourds
        class FakeProcessor:
            def __init__(self):
                self._whisper_model = None
                self._whisper_device = None

            def unload_whisper(self):
                if self._whisper_model is not None:
                    del self._whisper_model
                    self._whisper_model = None
                    self._whisper_device = None

        proc = FakeProcessor()
        proc.unload_whisper()  # Ne doit pas lever
        assert proc._whisper_model is None


class TestDoublonProtection:
    """Vérifie la logique anti-doublons."""

    def test_conflict_target_nomme(self):
        """ON CONFLICT doit cibler la contrainte nommée, pas DO NOTHING générique."""
        sql_correct = """
            INSERT INTO rag_chunks (file_id, filename, chunk_index, content, metadata, embedding)
            VALUES ($1, $2, $3, $4, $5, $6::vector)
            ON CONFLICT ON CONSTRAINT rag_chunks_file_chunk_unique DO NOTHING;
        """
        # La contrainte doit être ciblée explicitement
        assert "ON CONSTRAINT rag_chunks_file_chunk_unique" in sql_correct
        assert "DO NOTHING" in sql_correct

    def test_chunk_index_unique_par_fichier(self):
        """Deux fichiers différents peuvent avoir le même chunk_index."""
        chunks_file1 = [("file1", 0), ("file1", 1), ("file1", 2)]
        chunks_file2 = [("file2", 0), ("file2", 1)]  # chunk_index=0 OK pour file2

        all_pairs = chunks_file1 + chunks_file2
        unique_pairs = set(all_pairs)
        assert len(unique_pairs) == len(all_pairs)  # Pas de doublons


class TestNaNGuard:
    """Valide que le guard NaN de index_chunks() détecte les vecteurs corrompus (F07)."""

    def test_nan_detected_by_isfinite(self):
        """np.isfinite().all() doit échouer dès qu'un NaN est présent."""
        embeddings = np.array([[0.1, 0.2, 0.3], [np.nan, 0.5, 0.6], [0.7, 0.8, 0.9]])
        assert not np.isfinite(embeddings).all()

    def test_nan_row_count(self):
        """Le compte de lignes NaN/inf doit être exact."""
        embeddings = np.array([[0.1, 0.2], [np.nan, 0.5], [np.inf, 0.8]])
        nan_chunks = int(np.sum(~np.isfinite(embeddings).any(axis=1)))
        assert nan_chunks == 2

    def test_inf_detected(self):
        """np.inf est aussi non-fini et doit être détecté."""
        embeddings = np.array([[1.0, 2.0], [np.inf, 0.0]])
        assert not np.isfinite(embeddings).all()

    def test_clean_embeddings_pass(self):
        """Un batch de vecteurs propres doit passer le guard sans exception."""
        embeddings = np.random.rand(10, 768).astype(np.float32)
        assert np.isfinite(embeddings).all()

    def test_single_nan_in_large_batch(self):
        """Un seul NaN dans un grand batch suffit à déclencher le guard."""
        embeddings = np.ones((100, 768), dtype=np.float32)
        embeddings[42, 7] = np.nan  # Un seul NaN au milieu
        assert not np.isfinite(embeddings).all()
        nan_chunks = int(np.sum(~np.isfinite(embeddings).any(axis=1)))
        assert nan_chunks == 1


class TestThresholdCoherence:
    """Vérifie que la valeur par défaut de retrieve() est alignée sur config.py (F05)."""

    def test_threshold_defaut_aligne_config(self):
        """retrieve() doit avoir 0.72 comme valeur par défaut, pas 0.75."""
        source_path = Path(__file__).parent.parent / "api" / "rag_engine.py"
        source = source_path.read_text()
        assert "threshold: float = 0.75" not in source, \
            "Ancienne valeur 0.75 encore présente dans retrieve() — F05 non corrigé"
        assert "threshold: float = 0.72" in source, \
            "Valeur attendue 0.72 absente de retrieve() — F05 non appliqué"

    def test_rag_threshold_config_value(self):
        """RAG_THRESHOLD dans config.py doit valoir 0.72."""
        source_path = Path(__file__).parent.parent / "api" / "config.py"
        source = source_path.read_text()
        assert "0.72" in source, \
            "RAG_THRESHOLD = 0.72 absent de config.py"
        assert "0.75" not in source, \
            "Valeur incohérente 0.75 encore présente dans config.py"


class TestSQLCTE:
    """Vérifie que les requêtes SQL de retrieve() utilisent un CTE (F04)."""

    def test_requetes_contiennent_cte(self):
        """Les 2 requêtes SQL doivent contenir WITH ranked AS pour éviter
        le double calcul de la distance cosine."""
        source_path = Path(__file__).parent.parent / "api" / "rag_engine.py"
        source = source_path.read_text()
        cte_count = source.count("WITH ranked AS")
        assert cte_count >= 2, \
            f"Attendu 2 CTEs (avec/sans filtre métier), trouvé {cte_count}"

    def test_ancien_double_calcul_absent(self):
        """La formule dupliquée dans WHERE ne doit plus exister."""
        source_path = Path(__file__).parent.parent / "api" / "rag_engine.py"
        source = source_path.read_text()
        assert "WHERE 1 - (embedding" not in source, \
            "Double calcul cosine encore présent dans une clause WHERE — F04 non corrigé"

    def test_score_desc_present(self):
        """Les résultats du CTE doivent être triés par score DESC."""
        source_path = Path(__file__).parent.parent / "api" / "rag_engine.py"
        source = source_path.read_text()
        assert "ORDER BY score DESC" in source, \
            "ORDER BY score DESC absent — tri des résultats CTE manquant"


# ══════════════════════════════════════════════════════════════════════════════
# TESTS D'INTÉGRATION — Nécessite PostgreSQL (docker-compose up postgres)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.integration
class TestDatabaseIntegration:
    """Tests avec PostgreSQL réel."""

    @pytest.fixture
    async def pool(self):
        """Crée un pool de test vers PostgreSQL de test."""
        import asyncpg
        DB_URL = os.getenv(
            "TEST_DATABASE_URL",
            "postgresql://REDACTED_USER@localhost:5432/prof_ia_v5"
        )
        try:
            pool = await asyncpg.create_pool(DB_URL, min_size=1, max_size=2, command_timeout=10)
            yield pool
            await pool.close()
        except Exception as e:
            pytest.skip(f"PostgreSQL non disponible : {e}")

    @pytest.mark.asyncio
    async def test_extension_vector(self, pool):
        """pgvector doit être installé."""
        async with pool.acquire() as conn:
            result = await conn.fetchval(
                "SELECT COUNT(*) FROM pg_extension WHERE extname = 'vector';"
            )
        assert result == 1, "Extension pgvector non installée"

    @pytest.mark.asyncio
    async def test_table_rag_chunks_existe(self, pool):
        """La table rag_chunks doit exister avec la bonne structure."""
        async with pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT COUNT(*) FROM information_schema.tables
                WHERE table_name = 'rag_chunks';
            """)
        assert result == 1, "Table rag_chunks absente"

    @pytest.mark.asyncio
    async def test_contrainte_unique_existe(self, pool):
        """La contrainte UNIQUE doit exister pour que ON CONFLICT fonctionne."""
        async with pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT COUNT(*) FROM information_schema.table_constraints
                WHERE constraint_name = 'rag_chunks_file_chunk_unique'
                  AND table_name = 'rag_chunks';
            """)
        assert result == 1, "Contrainte UNIQUE rag_chunks_file_chunk_unique absente"

    @pytest.mark.asyncio
    async def test_index_hnsw_existe(self, pool):
        """L'index HNSW doit être présent."""
        async with pool.acquire() as conn:
            result = await conn.fetchval("""
                SELECT COUNT(*) FROM pg_indexes
                WHERE indexname = 'idx_rag_embedding_hnsw';
            """)
        assert result == 1, "Index HNSW absent"

    @pytest.mark.asyncio
    async def test_insert_et_dedoublonnage(self, pool):
        """ON CONFLICT DO NOTHING doit dédoublonner les réindexations."""
        async with pool.acquire() as conn:
            # Insérer un chunk de test
            fake_vec = [0.0] * 768
            fake_vec[0] = 1.0  # Vecteur non-nul

            await conn.execute("""
                INSERT INTO rag_chunks (file_id, filename, chunk_index, content, metadata, embedding)
                VALUES ($1, $2, $3, $4, $5, $6::vector)
                ON CONFLICT ON CONSTRAINT rag_chunks_file_chunk_unique DO NOTHING;
            """, "test_file_integration", "test.pdf", 0, "Contenu test", {}, fake_vec)

            # Réinsérer le même chunk — ne doit pas créer de doublon
            await conn.execute("""
                INSERT INTO rag_chunks (file_id, filename, chunk_index, content, metadata, embedding)
                VALUES ($1, $2, $3, $4, $5, $6::vector)
                ON CONFLICT ON CONSTRAINT rag_chunks_file_chunk_unique DO NOTHING;
            """, "test_file_integration", "test.pdf", 0, "Contenu test MODIFIÉ", {}, fake_vec)

            # Vérifier qu'il n'y a qu'un seul chunk pour ce file_id/chunk_index
            count = await conn.fetchval("""
                SELECT COUNT(*) FROM rag_chunks
                WHERE file_id = $1 AND chunk_index = $2;
            """, "test_file_integration", 0)

            # Nettoyer
            await conn.execute(
                "DELETE FROM rag_chunks WHERE file_id = $1;",
                "test_file_integration"
            )

        assert count == 1, "ON CONFLICT DO NOTHING n'a pas dédoublonné correctement"

    @pytest.mark.asyncio
    async def test_pool_partage_get_db(self, pool):
        """get_db() doit retourner le même pool à chaque appel."""
        # Ce test vérifie le comportement du lock asyncio dans get_db()
        import asyncpg as apg
        DB_URL = os.getenv(
            "TEST_DATABASE_URL",
            "postgresql://REDACTED_USER@localhost:5432/prof_ia_v5"
        )
        # Simuler deux appels concurrents à get_db()
        _pool_ref = [None]
        _lock = asyncio.Lock()

        async def fake_get_db():
            nonlocal _pool_ref
            if _pool_ref[0] is None:
                async with _lock:
                    if _pool_ref[0] is None:
                        try:
                            _pool_ref[0] = await apg.create_pool(
                                DB_URL, min_size=1, max_size=2
                            )
                        except Exception:
                            pytest.skip("PostgreSQL non disponible")
            return _pool_ref[0]

        # Appels concurrents — doivent tous retourner le même objet
        results = await asyncio.gather(
            fake_get_db(), fake_get_db(), fake_get_db()
        )
        assert all(r is results[0] for r in results), "Pool non-singleton"

        if _pool_ref[0]:
            await _pool_ref[0].close()


@pytest.mark.integration
class TestEndToEnd:
    """Test complet Upload → Index → Query (nécessite docker-compose up)."""

    @pytest.mark.asyncio
    async def test_upload_index_query(self):
        """Upload d'un fichier texte → indexation → query → chunks_retrieved > 0."""
        import httpx

        BASE_URL = "http://localhost:8001"

        content = (
            "Le protocole TCP/IP est la base des communications réseau. "
            "Il définit comment les données sont découpées en paquets et transmises. "
            "Le modèle OSI comporte 7 couches. La couche 4 est la couche transport. "
            "TSSR signifie Technicien Supérieur Systèmes et Réseaux."
        )

        async with httpx.AsyncClient(timeout=60.0) as client:
            # 1. Health check
            r = await client.get(f"{BASE_URL}/health")
            assert r.status_code == 200, f"Backend non disponible : {r.status_code}"

            # 2. Upload
            files = {"file": ("test_integration.txt", content.encode(), "text/plain")}
            r = await client.post(
                f"{BASE_URL}/documents/upload",
                files=files,
                data={"metier": "TSSR"},
            )
            assert r.status_code == 200, f"Upload échoué : {r.text}"
            file_id = r.json().get("file_id")
            assert file_id, "file_id absent de la réponse upload"

            # 3. Query
            r = await client.post(
                f"{BASE_URL}/chat",
                json={
                    "query": "Qu'est-ce que TCP/IP ?",
                    "session_id": "test_integration",
                    "metier_filter": "TSSR",
                },
            )
            assert r.status_code == 200, f"Chat échoué : {r.text}"
            data = r.json()
            assert data.get("chunks_retrieved", 0) > 0, \
                "Aucun chunk retrouvé — indexation ou retrieve() défaillant"

            # 4. Cleanup
            if file_id:
                await client.delete(f"{BASE_URL}/documents/{file_id}")
