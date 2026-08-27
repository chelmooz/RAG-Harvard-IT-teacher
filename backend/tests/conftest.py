"""Configuration pytest pour Prof IA v6.0 — Mocks complets pour tests unitaires."""
import os
import sys
from unittest.mock import MagicMock

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
os.environ.setdefault("API_TOKEN_SOURCE", "test-token-source-123456789012345678901234")
os.environ.setdefault("API_TOKEN", "test-token")
os.environ.setdefault("OLLAMA_HOST", "http://localhost:11434")
os.environ.setdefault("HSA_OVERRIDE_GFX_VERSION", "10.1.3")
os.environ.setdefault("PYTORCH_HIP_ALLOC_CONF", "max_split_size_mb:512")

import numpy as np


class MockTensor:
    pass

mock_st = MagicMock()
mock_st.encode.return_value = np.array([[0.1] * 1024, [0.2] * 1024])
mock_st.half.return_value = mock_st

sys.modules["sentence_transformers"] = MagicMock(SentenceTransformer=lambda *a, **kw: mock_st)
sys.modules["torch"] = MagicMock(
    cuda=MagicMock(is_available=lambda: False),
    device=lambda x: "cpu",
    inference_mode=lambda: MagicMock(__enter__=lambda s: None, __exit__=lambda s, *a: None),
    compile=lambda m, **kw: m,
    Tensor=MockTensor,
    nn=MagicMock(Module=MagicMock),
)
sys.modules["torch.cuda"] = MagicMock(
    is_available=lambda: False,
    get_device_properties=lambda x: MagicMock(name="Mock GPU", total_memory=12*1024**3),
)
sys.modules["torch.nn"] = MagicMock(Module=MagicMock)
sys.modules["transformers"] = MagicMock()
sys.modules["transformers.configuration_utils"] = MagicMock(PretrainedConfig=MagicMock)
sys.modules["transformers.utils.import_utils"] = MagicMock()
sys.modules["whisper"] = MagicMock(load_model=lambda *a, **kw: MagicMock(transcribe=lambda *a, **kw: {"text": "mocked"}))
sys.modules["openpyxl"] = MagicMock()
sys.modules["docx"] = MagicMock()
sys.modules["pptx"] = MagicMock()
sys.modules["pypdf"] = MagicMock()

# Imports after sys.modules mocking (required for heavy dependency mocking)
import asyncio  # noqa: E402
from unittest.mock import AsyncMock, patch  # noqa: E402

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402


@pytest.fixture(scope="session")
def event_loop():
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()

pytest_asyncio.mode = "auto"

@pytest.fixture(autouse=True)
def mock_torch_cuda(monkeypatch):
    monkeypatch.setenv("HSA_OVERRIDE_GFX_VERSION", "10.1.3")
    monkeypatch.setenv("PYTORCH_HIP_ALLOC_CONF", "max_split_size_mb:512")
    with patch("torch.cuda.is_available", return_value=False):
        yield

@pytest.fixture(autouse=True)
def mock_asyncpg_pool(monkeypatch):
    mock_pool = AsyncMock()
    mock_conn = AsyncMock()
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
    mock_pool.close = AsyncMock()

    async def mock_get_db():
        return mock_pool

    monkeypatch.setattr("api.database.get_db", mock_get_db)
    # rag_engine imports get_db locally in initialize(), so patch database.get_db is enough
    yield mock_pool, mock_conn

@pytest.fixture(autouse=True)
def mock_httpx_client(monkeypatch):
    """Mock du client HTTP Ollama via OllamaLLMClient."""
    mock_client = AsyncMock()
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json.return_value = {"response": "Mocked Ollama response"}
    mock_client.post.return_value = mock_response
    mock_client.get.return_value = mock_response
    mock_client.aclose = AsyncMock()

    # Patch OllamaLLMClient._client (lazy import inside class)
    monkeypatch.setattr("api.dependencies.OllamaLLMClient._client", mock_client, raising=False)
    yield mock_client

@pytest.fixture(autouse=True)
def mock_sentence_transformer(monkeypatch):
    """Mock SentenceTransformer pour LocalEmbeddingProvider."""
    mock_model = MagicMock()
    mock_model.encode.return_value = np.array([[0.1] * 1024, [0.2] * 1024])
    mock_model.half.return_value = mock_model

    # LocalEmbeddingProvider imports SentenceTransformer directly
    monkeypatch.setattr("api.rag_engine.LocalEmbeddingProvider.__init__",
                        lambda self, model_name="BAAI/bge-m3": setattr(self, 'model', mock_model) or None)
    # Also patch the module-level import
    monkeypatch.setattr("api.rag_engine.SentenceTransformer", lambda *args, **kwargs: mock_model)
    yield mock_model

@pytest.fixture
def mock_embedding_engine():
    mock = MagicMock()
    mock.encode.return_value = np.array([[0.1] * 1024])
    mock.encode_single.return_value = np.array([0.1] * 1024)
    mock.BATCH_SIZE = 64
    return mock

@pytest.fixture
def mock_rag_engine(mock_embedding_engine):
    mock = MagicMock()
    mock.embedding_engine = mock_embedding_engine
    mock.retrieve = AsyncMock(return_value=[
        {"text": "chunk 1", "metadata": {"source": "test.pdf"}, "score": 0.85, "rank": 1}
    ])
    mock.generate = AsyncMock(return_value="Mocked response")
    mock.index_chunks = AsyncMock()
    mock.get_collection_stats = AsyncMock(return_value={
        "total_chunks": 10, "total_documents": 2, "backend": "pgvector"
    })
    mock.reset_collection = AsyncMock()
    mock.check_ollama_health = AsyncMock()
    mock.check_db_health = AsyncMock()
    mock.close = AsyncMock()
    return mock
