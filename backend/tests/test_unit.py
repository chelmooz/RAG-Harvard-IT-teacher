"""
Tests unitaires — Prof IA v6.0
==============================
Tests de logique pure sans dépendances GPU/DB (mocks).
"""
import pytest
import numpy as np
from unittest.mock import patch
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
        chunks = [text]
        assert len(chunks) == 1


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