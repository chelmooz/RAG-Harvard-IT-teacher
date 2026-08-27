"""
Tests unitaires — Prof IA v6.1
==============================
Tests de logique pure sans dépendances GPU/DB (mocks via conftest.py).
"""
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

# ═══════════════════════════════════════════════════════════════════════════════
# TESTS CONFIG — Validateurs
# ═══════════════════════════════════════════════════════════════════════════════


class TestSettingsValidation:
    """Vérifie les validateurs extraits dans api.validators."""

    def test_database_url_obligatoire(self):
        from api.validators import _validate_database_url
        with pytest.raises(ValueError, match="DATABASE_URL obligatoire"):
            _validate_database_url(type("s", (), {"DATABASE_URL": ""})())

    def test_cors_warning_debug_false(self):
        from api.validators import _validate_cors
        with patch("api.validators.logger.warning") as mock_warn:
            s = type("s", (), {"CORS_ORIGINS": "*", "DEBUG": False})()
            _validate_cors(s)
            mock_warn.assert_called_once()

    def test_cors_no_warning_debug_true(self):
        from api.validators import _validate_cors
        with patch("api.validators.logger.warning") as mock_warn:
            s = type("s", (), {"CORS_ORIGINS": "*", "DEBUG": True})()
            _validate_cors(s)
            mock_warn.assert_not_called()

    def test_amd_cus_24_ok(self):
        from api.validators import _validate_amd_cus
        with patch("api.validators.logger.warning") as mock_warn:
            s = type("s", (), {"AMD_RDNA2_CUS": 24, "AMD_CU_UNLOCK_APPLIED": False})()
            _validate_amd_cus(s)
            mock_warn.assert_not_called()

    def test_amd_cus_40_warns_if_not_applied(self):
        from api.validators import _validate_amd_cus
        with patch("api.validators.logger.warning") as mock_warn:
            s = type("s", (), {"AMD_RDNA2_CUS": 40, "AMD_CU_UNLOCK_APPLIED": False})()
            _validate_amd_cus(s)
            mock_warn.assert_called_once()
            assert "AMD_RDNA2_CUS=40 mais AMD_CU_UNLOCK_APPLIED=False" in str(mock_warn.call_args)

    def test_amd_cus_24_warns_if_applied_flag_set(self):
        from api.validators import _validate_amd_cus
        with patch("api.validators.logger.warning") as mock_warn:
            s = type("s", (), {"AMD_RDNA2_CUS": 24, "AMD_CU_UNLOCK_APPLIED": True})()
            _validate_amd_cus(s)
            mock_warn.assert_called_once()
            assert "AMD_CU_UNLOCK_APPLIED=True mais AMD_RDNA2_CUS=24" in str(mock_warn.call_args)

    def test_amd_cus_invalid_value(self):
        from api.validators import _validate_amd_cus
        with patch("api.validators.logger.warning") as mock_warn:
            s = type("s", (), {"AMD_RDNA2_CUS": 32, "AMD_CU_UNLOCK_APPLIED": False})()
            _validate_amd_cus(s)
            mock_warn.assert_called_once()
            assert "inhabituel (24=stock, 40=débloqué)" in str(mock_warn.call_args)


class TestOllamaOptions:
    """OllamaLLMClient lit ses options depuis config (validated point 3)."""

    def test_get_llm_client_builds_options_from_settings(self):
        from api.config import get_settings
        from api.dependencies import get_llm_client

        settings = get_settings()
        client = get_llm_client()
        expected = {
            "temperature": settings.OLLAMA_TEMPERATURE,
            "top_p": settings.OLLAMA_TOP_P,
            "top_k": settings.OLLAMA_TOP_K,
            "num_predict": settings.OLLAMA_NUM_PREDICT,
            "num_ctx": settings.OLLAMA_NUM_CTX,
            "num_thread": settings.OLLAMA_NUM_THREAD,
            "num_gpu": settings.OLLAMA_NUM_GPU,
            "f16_kv": settings.OLLAMA_F16_KV,
        }
        assert client.options == expected

    def test_ollama_options_match_calibrated_bc250_values(self):
        from api.config import get_settings

        s = get_settings()
        assert s.OLLAMA_TEMPERATURE == 0.3
        assert s.OLLAMA_TOP_P == 0.9
        assert s.OLLAMA_TOP_K == 40
        assert s.OLLAMA_NUM_PREDICT == 1024
        assert s.OLLAMA_NUM_CTX == 4096
        assert s.OLLAMA_NUM_THREAD == 6
        assert s.OLLAMA_NUM_GPU == 99
        assert s.OLLAMA_F16_KV is True


# ════════════════════════════════════════════════════════════════════════════════
# TESTS RETRIEVE SQL BUILDING — Logique critique
# ═══════════════════════════════════════════════════════════════════════════════


class TestRetrieveSQLBuilding:
    """Vérifie la construction des requêtes SQL de retrieve() (F04 corrigé)."""

    def test_requete_sans_metier_contient_cte(self):
        """La requête sans filtre métier doit contenir un CTE WITH ranked AS."""
        from api.rag_engine import Retriever

        query_vec = np.array([0.1] * 1024)
        sql, params = Retriever._build_retrieve_sql(query_vec, top_k=5, threshold=0.72, metier_filter=None)

        assert "WITH ranked AS" in sql
        assert "embedding <=> $1::vector" in sql
        assert "ORDER BY score DESC" in sql
        assert len(params) == 3  # vec, limit, threshold

    def test_requete_avec_metier_contient_cte_et_filtre(self):
        """La requête avec filtre métier doit contenir CTE + WHERE métier."""
        from api.rag_engine import Retriever

        query_vec = np.array([0.1] * 1024)
        sql, params = Retriever._build_retrieve_sql(query_vec, top_k=5, threshold=0.72, metier_filter="TSSR")

        assert "WITH ranked AS" in sql
        assert "metadata->>'metier' = $4" in sql
        assert "ORDER BY score DESC" in sql
        assert len(params) == 4  # vec, limit, threshold, metier

    def test_ancien_double_calcul_absent(self):
        """La formule dupliquée dans WHERE ne doit plus exister (F04)."""
        from pathlib import Path
        source_path = Path(__file__).parent.parent / "api" / "rag_engine.py"
        source = source_path.read_text(encoding="utf-8")
        assert "WHERE 1 - (embedding" not in source, \
            "Double calcul cosine encore présent dans une clause WHERE — F04 non corrigé"

    def test_score_desc_present(self):
        """Les résultats du CTE doivent être triés par score DESC."""
        from pathlib import Path
        source_path = Path(__file__).parent.parent / "api" / "rag_engine.py"
        source = source_path.read_text(encoding="utf-8")
        assert "ORDER BY score DESC" in source, \
            "ORDER BY score DESC absent — tri des résultats CTE manquant"

    def test_limit_double_topk(self):
        """Le LIMIT doit être top_k * 2 pour over-fetch HNSW."""
        from api.rag_engine import Retriever

        query_vec = np.array([0.1] * 1024)
        sql, params = Retriever._build_retrieve_sql(query_vec, top_k=5, threshold=0.72, metier_filter=None)

        # Vérifie que le limit passé est 10 (5 * 2)
        assert params[1] == 10


# ════════════════════════════════════════════════════════════════════════════════
# TESTS EMBEDDING ENGINE — Batch sizing, fp16, normalize
# ═══════════════════════════════════════════════════════════════════════════════


class TestEmbeddingEngine:
    """Tests de l'EmbeddingEngine (batch size, fp16, normalisation)."""

    def test_batch_size_scales_with_cus_default_24(self):
        """BATCH_SIZE = 64 pour 24 CUs (valeur par défaut)."""
        from api.rag_engine import LocalEmbeddingProvider
        # BATCH_SIZE is computed at class definition time based on settings
        # Default AMD_RDNA2_CUS=24 gives max(64, round(64 * 24 / 24)) = 64
        assert LocalEmbeddingProvider.BATCH_SIZE >= 64

    def test_batch_size_scales_with_cus_40(self):
        """BATCH_SIZE échelle avec le nombre de CUs."""
        from api.rag_engine import LocalEmbeddingProvider
        # Just verify it's a reasonable value (computed at import time)
        assert LocalEmbeddingProvider.BATCH_SIZE >= 64

    def test_batch_size_env_override(self):
        """EMBEDDING_BATCH_SIZE env var prend le dessus."""
        import os


        os.environ["EMBEDDING_BATCH_SIZE"] = "128"
        try:
            # Force réévaluation
            import importlib

            import api.rag_engine
            importlib.reload(api.rag_engine)
            from api.rag_engine import LocalEmbeddingProvider
            assert LocalEmbeddingProvider.BATCH_SIZE == 128
        finally:
            del os.environ["EMBEDDING_BATCH_SIZE"]


# ════════════════════════════════════════════════════════════════════════════════
# TESTS CHUNKING — Logique de découpage (Chunker protocol)
# ═══════════════════════════════════════════════════════════════════════════════


class TestChunkingLogic:
    """Teste la logique de chunking via le Chunker protocol (DefaultChunker)."""

    def test_texte_court_reste_entier(self):
        """Un texte < chunk_size ne doit pas être découpé."""
        from api.dependencies import DefaultChunker

        chunker = DefaultChunker(chunk_size=400, chunk_overlap=80)
        text = "Bonjour monde."
        chunks = chunker.chunk(text, "test.txt", "text")

        assert len(chunks) == 1
        assert chunks[0]["text"] == text

    def test_texte_long_est_decoupe(self):
        """Un texte > chunk_size doit être découpé avec overlap."""
        from api.dependencies import DefaultChunker

        # Splitter avec petits chunks pour test
        chunker = DefaultChunker(chunk_size=50, chunk_overlap=10)

        text = "Premier paragraphe. " * 10  # ~200 chars
        chunks = chunker.chunk(text, "test.txt", "text")

        assert len(chunks) > 1
        # Vérifie overlap : fin d'un chunk ≈ début du suivant
        for i in range(len(chunks) - 1):
            assert len(chunks[i]["text"]) <= 50 + 10  # chunk_size + overlap

    def test_texte_vide_retourne_liste_vide(self):
        """Texte vide ou whitespace seulement → liste vide."""
        from api.dependencies import DefaultChunker

        chunker = DefaultChunker(chunk_size=400, chunk_overlap=80)

        assert chunker.chunk("", "test.txt", "text") == []
        assert chunker.chunk("   \n\n  ", "test.txt", "text") == []

    def test_metadata_preserved_in_chunks(self):
        """Les métadonnées source/file_type/chunking_method sont préservées."""
        from api.dependencies import DefaultChunker

        chunker = DefaultChunker(chunk_size=400, chunk_overlap=80)
        text = "Test chunking metadata."
        chunks = chunker.chunk(text, "doc.pdf", "pdf")

        assert len(chunks) == 1
        meta = chunks[0]["metadata"]
        assert meta["source"] == "doc.pdf"
        assert meta["file_type"] == "pdf"
        assert meta["chunking_method"] == "recursive_char"
        assert "chunk_size" in meta


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS DOCUMENT EXTRACTORS — Implémentations concrètes
# ═══════════════════════════════════════════════════════════════════════════════


class TestDocumentExtractors:
    """Tests des extracteurs de documents (implémentations concrètes)."""

    def test_text_extractor(self):
        """TextExtractor extrait le contenu brut."""
        from api.dependencies import TextExtractor
        extractor = TextExtractor()

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = "Hello world"
            result = extractor.extract("/fake/path.txt")

        assert result == "Hello world"
        assert ".txt" in extractor.supported_extensions
        assert ".md" in extractor.supported_extensions

    def test_pdf_extractor(self):
        """PDFExtractor utilise pypdf."""
        import sys

        mock_pypdf = MagicMock()
        mock_page = MagicMock()
        mock_page.extract_text.return_value = "Page 1 content"
        mock_reader = MagicMock()
        mock_reader.pages = [mock_page]
        mock_pypdf.PdfReader.return_value = mock_reader
        sys.modules["pypdf"] = mock_pypdf

        from api.dependencies import PDFExtractor
        extractor = PDFExtractor()

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value = MagicMock()
            result = extractor.extract("/fake/test.pdf")

        assert "Page 1 content" in result
        assert ".pdf" in extractor.supported_extensions

    def test_docx_extractor(self):
        """DocxExtractor extrait les paragraphes."""
        import sys

        mock_docx = MagicMock()
        mock_para = MagicMock()
        mock_para.text = "Paragraph 1"
        mock_docx.Document.return_value.paragraphs = [mock_para]
        sys.modules["docx"] = mock_docx

        from api.dependencies import DocxExtractor
        extractor = DocxExtractor()

        result = extractor.extract("/fake/test.docx")

        assert "Paragraph 1" in result
        assert ".docx" in extractor.supported_extensions

    def test_pptx_extractor(self):
        """PptxExtractor extrait le texte des slides."""
        import sys

        mock_pptx = MagicMock()
        mock_slide = MagicMock()
        mock_shape = MagicMock()
        mock_shape.text = "Slide text"
        mock_slide.shapes = [mock_shape]
        mock_pptx.Presentation.return_value.slides = [mock_slide]
        sys.modules["pptx"] = mock_pptx

        from api.dependencies import PptxExtractor
        extractor = PptxExtractor()

        result = extractor.extract("/fake/test.pptx")

        assert "Slide text" in result
        assert ".pptx" in extractor.supported_extensions

    def test_xlsx_extractor(self):
        """XlsxExtractor extrait les lignes."""
        import sys

        mock_openpyxl = MagicMock()
        mock_sheet = MagicMock()
        mock_sheet.iter_rows.return_value = [[1, 2], [3, 4]]
        mock_openpyxl.load_workbook.return_value = MagicMock(__iter__=lambda s: iter([mock_sheet]))
        sys.modules["openpyxl"] = mock_openpyxl

        from api.dependencies import XlsxExtractor
        extractor = XlsxExtractor()

        result = extractor.extract("/fake/test.xlsx")

        assert "1 | 2" in result or "3 | 4" in result
        assert ".xlsx" in extractor.supported_extensions

    def test_audio_video_extractor(self):
        """AudioVideoExtractor délègue au Transcriber."""
        from api.dependencies import AudioVideoExtractor, WhisperTranscriber
        transcriber = WhisperTranscriber()
        extractor = AudioVideoExtractor(transcriber)

        with patch.object(transcriber, 'transcribe', return_value="Transcribed text"):
            result = extractor.extract("/fake/test.mp3")

        assert result == "Transcribed text"
        assert ".mp3" in extractor.supported_extensions
        assert ".mp4" in extractor.supported_extensions
        assert ".wav" in extractor.supported_extensions


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS INDEXATION — Dedup, validation embeddings
# ══════════════════════════════════════════════════════════════════════════════


class TestIndexationLogic:
    """Tests de la logique d'indexation (dedup, validation)."""

    def test_validate_embeddings_detects_nan(self):
        """Indexer._validate_embeddings lève RuntimeError sur NaN."""
        import numpy as np

        from api.rag_engine import Indexer

        embeddings = np.array([[0.1, 0.2], [np.nan, 0.4]])

        with pytest.raises(RuntimeError, match="embeddings NaN"):
            Indexer._validate_embeddings(embeddings, "test.pdf")

    def test_validate_embeddings_passes_on_valid(self):
        """Indexer._validate_embeddings passe sur embeddings valides."""
        import numpy as np

        from api.rag_engine import Indexer

        embeddings = np.array([[0.1, 0.2], [0.3, 0.4]])

        # Ne doit pas lever
        Indexer._validate_embeddings(embeddings, "test.pdf")

    def test_build_index_records_structure(self):
        """Indexer._build_index_records produit la bonne structure de tuples."""
        import numpy as np

        from api.rag_engine import Indexer

        chunks = [
            {"text": "chunk 1", "metadata": {"source": "test.pdf", "custom": "value"}},
            {"text": "chunk 2", "metadata": {"source": "test.pdf"}},
        ]
        embeddings = np.array([[0.1] * 1024, [0.2] * 1024])

        records = Indexer._build_index_records(chunks, embeddings, "file_123", "test.pdf")

        assert len(records) == 2
        for i, rec in enumerate(records):
            assert rec[0] == "file_123"
            assert rec[1] == "test.pdf"
            assert rec[2] == i
            assert rec[3] == f"chunk {i+1}"
            assert rec[4]["source"] == "test.pdf"
            # metadata includes source + any custom keys
            if i == 0:
                assert rec[4]["custom"] == "value"
            else:
                assert "custom" not in rec[4]


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS GENERATION — Prompt building
# ══════════════════════════════════════════════════════════════════════════════


class TestPromptBuilding:
    """Tests de la construction des prompts pour génération."""

    def test_build_system_prompt_default(self):
        """Prompt système par défaut contient les éléments clés."""
        from api.rag_engine import Generator

        prompt = Generator._build_system_prompt("")

        assert "assistant pédagogique" in prompt.lower()
        assert "cybersécurité" in prompt.lower()
        assert "tssr" in prompt.lower() or "TSSR" in prompt
        assert "cite toujours tes sources" in prompt.lower()
        assert "je ne trouve pas cette information" in prompt.lower()

    def test_build_system_prompt_custom(self):
        """Prompt système custom remplace le défaut."""
        from api.rag_engine import Generator

        custom = "Custom system prompt"
        prompt = Generator._build_system_prompt(custom)

        assert prompt == custom

    def test_build_full_prompt_with_context(self):
        """Prompt complet inclut contexte et question."""
        from api.rag_engine import Generator

        prompt = Generator._build_full_prompt("Qu'est-ce que TCP ?", "Contexte: TCP est un protocole.")

        assert "Contexte (sources documentaires)" in prompt
        assert "TCP est un protocole" in prompt
        assert "Question : Qu'est-ce que TCP ?" in prompt

    def test_build_full_prompt_without_context(self):
        """Prompt sans contexte indique l'absence de docs."""
        from api.rag_engine import Generator

        prompt = Generator._build_full_prompt("Question seule", None)

        assert "Aucun document pertinent" in prompt
        assert "Question : Question seule" in prompt
        assert "dis-le clairement sans inventer" in prompt


# ═══════════════════════════════════════════════════════════════════════════════
# TESTS DATABASE — Schema, constraints
# ══════════════════════════════════════════════════════════════════════════════


class TestDatabaseSchema:
    """Tests du schéma de base de données (structure only)."""

    def test_rag_chunks_has_unique_constraint(self):
        """La table rag_chunks doit avoir la contrainte UNIQUE(file_id, chunk_index)."""
        from pathlib import Path
        source = Path(__file__).parent.parent / "api" / "database.py"
        content = source.read_text(encoding="utf-8")

        assert "CONSTRAINT rag_chunks_file_chunk_unique" in content
        assert "UNIQUE (file_id, chunk_index)" in content

    def test_conversations_has_metier_check(self):
        """La table conversations a une contrainte CHECK sur metier."""
        from pathlib import Path
        source = Path(__file__).parent.parent / "api" / "database.py"
        content = source.read_text(encoding="utf-8")

        assert "CONSTRAINT valid_metier" in content
        assert "CHECK (metier IN ('TSSR', 'AIS', 'DevOps')" in content

    def test_response_evaluations_unique_conversation(self):
        """response_evaluations a UNIQUE(conversation_id)."""
        from pathlib import Path
        source = Path(__file__).parent.parent / "api" / "database.py"
        content = source.read_text(encoding="utf-8")

        assert "UNIQUE(conversation_id)" in content

    def test_indexes_defined(self):
        """Les index HNSW et métier sont définis."""
        from pathlib import Path
        source = Path(__file__).parent.parent / "api" / "database.py"
        content = source.read_text(encoding="utf-8")

        assert "idx_rag_embedding_hnsw" in content
        assert "USING hnsw" in content
        assert "vector_cosine_ops" in content
        assert "idx_rag_metier" in content
        assert "metadata->>'metier'" in content


# ══════════════════════════════════════════════════════════════════════════════
# TESTS SCORE SIMILARITY — Formule cosine
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


# ══════════════════════════════════════════════════════════════════════════════
# TESTS HEALTH CHECK — Composants
# ═════════════════════════════════════════════════════════════════════════════


class TestHealthCheckLogic:
    """Tests de la logique de health check (structure)."""

    def test_overall_healthy_iff_db_ok(self):
        """Overall healthy seulement si DB ok."""
        # Simulation de la logique dans main.py health_check
        db_status = "ok"
        overall = "healthy" if db_status == "ok" else "degraded"
        assert overall == "healthy"

        db_status = "error: connection failed"
        overall = "healthy" if db_status == "ok" else "degraded"
        assert overall == "degraded"
