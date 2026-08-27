"""
Protocols (Interfaces) for Prof IA v6.0 — Dependency Inversion.
Defines contracts without implementation details.
"""
from typing import Protocol

from numpy.typing import NDArray


class EmbeddingProvider(Protocol):
    """Contract for embedding generation."""

    def encode(self, texts: list[str]) -> NDArray:
        """Encode a batch of texts to normalized vectors."""
        ...

    def encode_single(self, text: str) -> NDArray:
        """Encode a single text to a normalized vector."""
        ...

    @property
    def batch_size(self) -> int:
        """Batch size for vectorized encoding."""
        ...


class LLMClient(Protocol):
    """Contract for LLM text generation."""

    async def generate(self, prompt: str, system: str) -> str:
        """Generate a response from prompt + system prompt."""
        ...

    async def check_health(self) -> bool:
        """Check if LLM service is available."""
        ...


class VectorStore(Protocol):
    """Contract for vector storage and retrieval."""

    async def initialize(self) -> None:
        """Initialize the store (create tables, indexes)."""
        ...

    async def retrieve(
        self,
        query_vector: NDArray,
        top_k: int,
        threshold: float,
        metier_filter: str | None,
    ) -> list[dict]:
        """Retrieve similar chunks."""
        ...

    async def index_chunks(
        self,
        chunks: list[dict[str, object]],
        file_id: str,
        filename: str,
    ) -> None:
        """Index chunks with embeddings."""
        ...

    async def get_stats(self) -> dict[str, object]:
        """Get collection statistics."""
        ...

    async def reset(self) -> None:
        """Reset collection (delete all)."""
        ...

    async def check_health(self) -> bool:
        """Check if vector store is healthy."""
        ...

    async def close(self) -> None:
        """Close connections."""
        ...


class DocumentExtractor(Protocol):
    """Contract for document text extraction."""

    @property
    def supported_extensions(self) -> set[str]:
        """File extensions this extractor handles."""
        ...

    def extract(self, file_path: str) -> str:
        """Extract text from a file."""
        ...


class Chunker(Protocol):
    """Contract for text chunking."""

    def chunk(self, text: str, source: str, file_type: str) -> list[dict]:
        """Split text into chunks with metadata."""
        ...


class Transcriber(Protocol):
    """Contract for audio/video transcription."""

    def transcribe(self, file_path: str) -> str:
        """Transcribe audio/video to text."""
        ...

    def unload(self) -> None:
        """Release model from memory."""
        ...
