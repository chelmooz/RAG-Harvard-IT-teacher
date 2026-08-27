# PROJECT KNOWLEDGE BASE

**Generated:** 2026-08-27
**Commit:** bbac4a0
**Branch:** feat/auto-eval-rag

## OVERVIEW
This repository implements a fully local Retrieval‑Augmented Generation (RAG) teaching assistant for IT curricula (TSSR / AIS / DevOps). It combines a vector‑retrieval engine with a compiled LLM‑Wiki knowledge vault, adhering to OKF provenance principles and running entirely on premises.

## STRUCTURE
```
├── backend/                # FastAPI RAG engine, document processors, evaluation tests
├── frontend/               # React UI (terminal, dashboard, minimal)
├── config/                 # Nginx reverse‑proxy configuration
├── scripts/                # Helper scripts (unlock, line checks, etc.)
├── experimental/           # Experimental features and fine‑tuning notebooks
├── vault/                  # Layer B – LLM Wiki knowledge vault (Modèle 3)
│   ├── AGENTS.md           # The Schema (OKF front‑matter rules)
│   └── wiki/               # Generated knowledge notes
├── vault/raw/              # Drop folder for source documents
└── vault/log.md            # OKF maintenance log
```

## WHERE TO LOOK
| Task | Location | Notes |
|------|----------|-------|
| Run the RAG stack | `docker compose up -d` (root) | Exposes UI at `localhost:3000` |
| Inspect embeddings | `vault/raw/` and `vault/wiki/` | PDFs, MD, DOCX, CSV ingestion pipelines |
| View knowledge base | `vault/wiki/` | Linked, source‑cited notes |
| Extend architecture | `backend/`, `frontend/` | Follow modular FastAPI / React patterns |
| Add hardware notes | `experimental/` | BC‑250 unlock & OC procedures |

## CODE MAP
The code base follows a modular FastAPI + React layout:

- **Backend**: `backend/api/` contains `main.py`, `rag_engine/`, `database.py`, `document_processor/`, `evaluation.py`.
- **Frontend**: `frontend/src/` hosts the React components, routed via Nginx.
- **Embedding model**: `BAAI/bge-m3` (1024‑dim) selected for French‑language MTEB suitability.
- **LLM model**: `qwen3:14b` served via Ollama on `127.0.0.1:11434` (exposed as `:11436`).

Only the back‑end imports `vault/` for OKF provenance; the front‑end never accesses raw files.

## CONVENTIONS
- **Strict typing** (`pydantic` v2) across all Python modules.
- **Code formatting** enforced by `ruff` (line length 120) and `pre‑commit`.
- **Testing**: all evaluation logic lives under `backend/tests/`, run with `pytest`.
- **Documentation**: markdown files in root and `Prof-IA-v5-Documentation-BC250.md`.
- **Hardware notes** kept in `experimental/` and `BC-250-INSTALL-GUIDE.md`.

## ANTI-PATTERNS (THIS PROJECT)
- **Hard‑coded API keys** – prohibited; all secrets go through `.env.example` and runtime injection.
- **Partial or disabled implementations** – components must be complete or removed.
- **Excessive logging** – only structured JSON logs; avoid verbose console output.
- **Non‑deterministic sleeps or polling** – use `monitor`/`task` notifications instead.
- **Direct file system writes without atomic ops** – use `tempfile` and rename.

## UNIQUE STYLES
- **Markdown with front‑matter** for every knowledge note; `[[wiki-links]]` for provenance.
- **Reusable UI components** that accept theme props for dark / light mode.
- **Context‑aware prompts** that embed retrieval results directly into the LLM call.

## COMMANDS
```bash
# Launch full stack
docker compose up -d

# Run test suite
python -m pytest backend/tests/

# Pull the base LLM model
ollama pull qwen3:14b

# Ingest a new document
curl -F "file=@path/to/doc.pdf" http://localhost:8001/documents/upload
```

## NOTES
- **Hardware target**: AMD BC‑250 (Cyan Skillfish) with up to 40 unlocked CUs and 8 CPU cores; see `BC-250-INSTALL-GUIDE.md` for unlock and OC steps.
- **Model context**: `num_ctx` set to 8192 for deep RAG workloads, 1024 for quick vault queries.
- **Auto‑evaluation**: after each `/chat` response the backend can trigger a sequential Judge + Devil’s Advocate run on the same `qwen3:14b` model (controlled by `AUTO_EVALUATE` flag).