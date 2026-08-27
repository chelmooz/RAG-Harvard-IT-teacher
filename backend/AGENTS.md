# Backend – Prof-IA RAG Engine

**Purpose**: Implements the vector‑retrieval and RAG core that serves UI queries.

## Structure
```
backend/api/
├── main.py          # FastAPI entry point
├── rag_engine/      # Retrieval logic
└── tests/           # Evaluation tests
```

## Where to Look
| Task | Location | Notes |
|------|------------|-------|
| Add new document processor | `backend/api/document_processor/` | Follow existing scraper pattern |
| Extend evaluation | `backend/tests/` | Must pass pytest suite |

## Code Map
- **Retrieval**: `rag_engine/vector_store.py`
- **Document loading**: `rag_engine/document_loader.py`
- **API endpoints**: `backend/api/main.py`
- **Evaluation**: `backend/tests/test_evaluation.py`

## Conventions
- Pydantic v2 models for request/response validation.
- Structured JSON logging.
- Type‑checked public API (`pydantic` models).
- Unit‑test coverage ≥ 90 %.

## Anti‑Patterns
- Direct DB session leak – always use context managers.
- Imperative SQL strings – use SQLAlchemy ORM.
- Unchecked external input – always validate via schemas.

## Commands
```bash
# Run test suite
python -m pytest backend/tests/

# Add a new processor skeleton
mkdir -p backend/api/document_processor
touch backend/api/document_processor/__init__.py
```