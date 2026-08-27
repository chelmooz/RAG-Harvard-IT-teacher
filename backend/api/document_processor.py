"""
Document Processor v6.1 — AMD BC-250 (Cyan Skillfish)
=======================================================
DIP appliqué :
  - DocumentExtractor injectés (un par format)
  - Chunker injecté (Protocol)
  - Transcriber injecté (Protocol)
  - Plus de Whisper singleton interne — délégué au Transcriber injecté
"""

import asyncio
from pathlib import Path
from typing import Any

from loguru import logger

from .config import get_settings
from .protocols import Chunker, DocumentExtractor, Transcriber

settings = get_settings()


class DocumentProcessor:
    """Processeur de documents multi-formats — dépendances injectées (DIP)."""

    SUPPORTED_FORMATS = {
        ".pdf":  "pdf",
        ".txt":  "text",
        ".md":   "text",
        ".docx": "docx",
        ".pptx": "pptx",
        ".xlsx": "xlsx",
        ".mp3":  "audio",
        ".mp4":  "video",
        ".wav":  "audio",
    }

    def __init__(
        self,
        upload_dir: str = "/app/data/uploads",
        extractors: list[DocumentExtractor] | None = None,
        chunker: Chunker | None = None,
        transcriber: Transcriber | None = None,
    ):
        self.upload_dir = Path(upload_dir)
        self.upload_dir.mkdir(parents=True, exist_ok=True)

        # Dépendances injectées (avec fallbacks pour compatibilité)
        self._extractors = extractors or []
        self._chunker = chunker
        self._transcriber = transcriber

        # Build extension -> extractor map
        self._extractor_map: dict[str, DocumentExtractor] = {}
        for ext in self._extractors:
            for e in ext.supported_extensions:
                self._extractor_map[e.lower()] = ext

    # ── Sauvegarde fichier ─────────────────────────────────────────────────────

    async def save_file(self, file, file_id: str) -> str:
        """
        Sauvegarde un fichier uploadé en streaming par chunks de 8 Mo.

        POURQUOI 8 Mo ?
        La GDDR6 unifiée BC-250 traite les accès mémoire en bursts de 256 bits.
        Lire le fichier entier d'un coup peut saturer les 16 Go si plusieurs
        uploads sont simultanés. 8 Mo = bon compromis débit / pression mémoire.
        """
        ext = Path(file.filename).suffix.lower()
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Extension non autorisée : {ext}")

        # file_id est toujours un UUID (généré par l'appelant) → pas de path traversal
        file_path = self.upload_dir / f"{file_id}{ext}"
        chunk_size = 8 * 1024 * 1024  # 8 Mo

        with open(file_path, "wb") as f:
            while True:
                data = await file.read(chunk_size)
                if not data:
                    break
                f.write(data)

        size = file_path.stat().st_size
        logger.info(f"💾 Sauvegardé : {file_path.name} ({size // 1024} Ko)")
        return str(file_path)

    # ── Pipeline principal ─────────────────────────────────────────────────────

    async def process_document(
        self, file_path: str, filename: str
    ) -> list[dict[str, Any]]:
        """
        Pipeline complet : extraction + chunking.

        Les extractions lourdes (PDF, DOCX…) sont CPU-bound.
        asyncio.to_thread() les délègue à un thread OS pour ne pas bloquer
        la boucle d'événements FastAPI pendant le traitement.
        """
        ext = Path(file_path).suffix.lower()
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Format non supporté : {ext}")

        # Trouver l'extracteur approprié
        extractor = self._extractor_map.get(ext.lower())
        if not extractor:
            raise ValueError(f"Aucun extracteur pour l'extension : {ext}")

        text = await asyncio.to_thread(extractor.extract, file_path)
        chunks = self._chunk_text(text, filename, self.SUPPORTED_FORMATS[ext])
        logger.info(f"✅ {len(chunks)} chunks créés pour « {filename} »")
        return chunks

    # ── Chunking (délégué au Chunker injecté) ──────────────────────────────────

    def _chunk_text(
        self,
        text: str,
        source: str,
        file_type: str,
    ) -> list[dict[str, Any]]:
        """
        Découpe le texte via le Chunker injecté.
        """
        if not text.strip():
            return []

        if self._chunker:
            return self._chunker.chunk(text, source, file_type)

        # Fallback (ne devrait pas arriver si DI configuré)
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP,
            separators=["\n\n", "\n", ". ", " ", ""],
            length_function=len,
        )
        raw_chunks = splitter.split_text(text)
        return [
            {
                "text": chunk,
                "metadata": {
                    "source": source,
                    "file_type": file_type,
                    "chunking_method": "recursive_char",
                    "chunk_size": len(chunk),
                },
            }
            for chunk in raw_chunks
            if chunk.strip()
        ]

    # ── Indexation répertoire ──────────────────────────────────────────────────

    def _validate_directory(self, directory: str) -> Path:
        dir_path = Path(directory).resolve(strict=False)
        allowed = self.upload_dir.resolve()
        if not dir_path.is_relative_to(allowed):
            raise ValueError(
                f"Chemin refusé : {dir_path} — seuls les sous-répertoires de "
                f"{allowed} sont autorisés"
            )
        if not dir_path.exists():
            raise ValueError(f"Répertoire inexistant : {directory}")
        return dir_path

    @staticmethod
    def _collect_files(dir_path: Path) -> list[Path]:
        return [
            p for p in dir_path.rglob("*")
            if p.is_file() and p.suffix.lower() in DocumentProcessor.SUPPORTED_FORMATS
        ]

    async def index_directory(
        self,
        directory: str,
        rag_engine,
    ) -> dict[str, Any]:
        """
        Indexe tous les fichiers d'un répertoire EN PARALLÈLE.

        asyncio.gather + Semaphore (compat Python 3.11+) pour le parallélisme.
        Chaque tâche = extraction (thread) + encodage GPU batch + INSERT asyncpg.

        try/except dans _process_one : un fichier défaillant n'annule pas tout.
        """
        dir_path = self._validate_directory(directory)

        files = self._collect_files(dir_path)

        stats = {
            "total_files": len(files),
            "processed": 0,
            "failed": 0,
            "total_chunks": 0,
        }

        semaphore = asyncio.Semaphore(4)  # Limite concurrence

        async def _process_one(file_path: Path):
            async with semaphore:
                try:
                    chunks = await self.process_document(str(file_path), file_path.name)
                    await rag_engine.index_chunks(
                        chunks, str(file_path.stem), file_path.name
                    )
                    stats["processed"] += 1
                    stats["total_chunks"] += len(chunks)
                    logger.info(f"✅ {file_path.name} : {len(chunks)} chunks indexés")
                except Exception as e:
                    stats["failed"] += 1
                    logger.error(f"❌ {file_path.name} : {e}")

        await asyncio.gather(*[_process_one(fp) for fp in files])

        logger.info(
            f"📊 Indexation terminée : {stats['processed']}/{stats['total_files']} "
            f"fichiers | {stats['total_chunks']} chunks | {stats['failed']} erreurs"
        )
        return stats
