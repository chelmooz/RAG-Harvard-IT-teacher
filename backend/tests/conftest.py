"""Configuration pytest pour Prof IA v6.0."""
import pytest
import pytest_asyncio

# ── Fixtures partagées ────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Crée une boucle d'événements pour la session de test."""
    import asyncio
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()


# ── Configuration pytest-asyncio ──────────────────────────────────────────────

# Permet d'utiliser @pytest.mark.asyncio sans loop explicite
pytest_asyncio.mode = "auto"


# ── Fixtures ROCm (forcé CPU pour les tests) ──────────────────────────────────

@pytest.fixture(autouse=True)
def force_cpu_device(monkeypatch):
    """Désactive le GPU pour les tests unitaires."""
    monkeypatch.setenv("HSA_OVERRIDE_GFX_VERSION", "10.1.3")
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr("torch.cuda.is_available", lambda: False)
        yield
