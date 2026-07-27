"""
Tests d'intégration — Prof IA v6.0
==================================
Tests avec PostgreSQL réel (nécessite docker-compose up postgres).

Lancer :
  pytest backend/tests/test_integration.py -v -m integration
"""
import os
import asyncio
import pytest
import pytest_asyncio


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS D'INTÉGRATION — Nécessite PostgreSQL (docker-compose up postgres)
# ══════════════════════════════════════════════════════════════════════════════


@pytest.fixture
def db_url():
    """URL de connexion PostgreSQL de test."""
    return os.getenv(
        "TEST_DATABASE_URL",
        "postgresql://REDACTED_USER@localhost:5432/prof_ia_v5"
    )


@pytest.fixture
def base_url():
    """Base URL for API calls (configurable via env)."""
    return os.getenv("TEST_API_BASE_URL", "http://localhost:8001")
    """Token API pour les tests E2E."""
    return os.getenv("TEST_API_TOKEN", "test-token")


@pytest_asyncio.fixture
async def pool(db_url):
    """Crée un pool de test vers PostgreSQL de test."""
    import asyncpg
    try:
        pool = await asyncpg.create_pool(db_url, min_size=1, max_size=2, command_timeout=10)
        yield pool
        await pool.close()
    except Exception as e:
        pytest.skip(f"PostgreSQL non disponible : {e}")


class TestDatabaseIntegration:
    """Tests avec PostgreSQL réel."""

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
            fake_vec = [0.0] * 1024
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
    async def test_pool_partage_get_db(self, db_url):
        """get_db() doit retourner le même pool à chaque appel."""
        import asyncpg as apg

        # Simuler deux appels concurrents à get_db()
        _pool_ref = [None]
        _lock = asyncio.Lock()

        async def fake_get_db():
            if _pool_ref[0] is None:
                async with _lock:
                    if _pool_ref[0] is None:
                        try:
                            _pool_ref[0] = await apg.create_pool(
                                db_url, min_size=1, max_size=2
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


class TestEndToEnd:
    """Test complet Upload → Index → Query (nécessite docker-compose up)."""

    @pytest.mark.asyncio
    async def test_upload_index_query(self, api_token, base_url):
        """Upload d'un fichier texte → indexation → query → chunks_retrieved > 0."""
        import httpx

        content = (
            "Le protocole TCP/IP est la base des communications réseau. "
            "Il définit comment les données sont découpées en paquets et transmises. "
            "Le modèle OSI comporte 7 couches. La couche 4 est la couche transport. "
            "TSSR signifie Technicien Supérieur Systèmes et Réseaux."
        )

        headers = {"Authorization": f"Bearer {api_token}"}

        async with httpx.AsyncClient(timeout=60.0) as client:
            # 1. Health check
            r = await client.get(f"{base_url}/health")
            assert r.status_code == 200, f"Backend non disponible : {r.status_code}"

            # 2. Upload
            files = {"file": ("test_integration.txt", content.encode(), "text/plain")}
            r = await client.post(
                f"{base_url}/documents/upload",
                files=files,
                data={"metier": "TSSR"},
                headers=headers,
            )
            assert r.status_code == 200, f"Upload échoué : {r.text}"
            file_id = r.json().get("file_id")
            assert file_id, "file_id absent de la réponse upload"

            # 3. Query
            r = await client.post(
                f"{base_url}/chat",
                json={
                    "query": "Qu'est-ce que TCP/IP ?",
                    "session_id": "test_integration",
                    "metier": "TSSR",
                },
                headers=headers,
            )
            assert r.status_code == 200, f"Chat échoué : {r.text}"
            data = r.json()
            assert data.get("chunks_retrieved", 0) > 0, \
                "Aucun chunk retrouvé — indexation ou retrieve() défaillant"

            # 4. Cleanup
            if file_id:
                await client.delete(f"{BASE_URL}/documents/{file_id}", headers=headers)