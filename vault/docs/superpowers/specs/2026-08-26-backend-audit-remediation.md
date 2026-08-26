---
type: concept
title: Remédiation audit backend Prof-IA (P0–P2)
description: Correction des bugs backend vérifiés contre le code (init_db/asyncpg, DELETE, tâche asyncio, CORS, num_gpu, OLLAMA_MODEL).
resource: backend/api/
status: stable
stale_after: 2027-08-26
tags:
  - prof-ia
  - backend
  - audit
  - bugfix
generated:
  by: "agent:opencode"
  at: "2026-08-26"
verified:
  by: "human:michel"
  at: "2026-08-26"
sources:
  - uri: "backend/api/database.py"
  - uri: "backend/api/main.py"
  - uri: "backend/api/config.py"
  - uri: "docker-compose.yml"
  - uri: "backend/tests/test_integration.py"
aliases:
  - backend-audit-remediation
statut: confirme
okf_version: "0.2"
concepts:
  - Prof-IA
  - pgvector
  - asyncpg
  - Ollama
questions_ouvertes:
  - "Embeddings ROCm cassé sur gfx1013 → fallback CPU ou endpoint embedding Ollama à confirmer."
---

# Remédiation audit backend Prof-IA (P0–P2)

Audit « strictement vérifié contre le code », sans affirmation non prouvée. Deux P0, deux P1,
deux P2 identifiés et corrigés. Pré-déploiement : corrections appliquées mais **non testées à
l'exécution** (aucun Postgres/Ollama disponible en environnement pré-déploiement).

## Racine commune (P0-1 + P0-2)

`backend/api/database.py` : `init_db()` appelait `register_vector(pool)` — **API asyncpg
erronée** (`register_vector` attend une connexion, pas un pool). Conséquence en cascade :

- Le codec `pgvector` n'était jamais enregistré → toute requête vectorielle plans crash
  (démarrage du pool / requêtes RAG).
- Le codec **`jsonb`** n'était **jamais enregistré** → les `ConversationRecord.context`/`chunks`
  (colonnes `jsonb`) étaient stockés mais **non décodés en lecture** → l'historique de
  conversation était **muet/silencieux** (pages History vides) bien que les lignes existent.

**Correction** : suppression de `_register_pgvector(pool)` ; ajout du callback
`init=_init_connection` (par connexion) qui appelle `register_vector(conn)` **et**
`conn.set_type_codec("jsonb", …)` (encoder/decoder json). `asyncpg.create_pool(..., init=...)`
enregistre ainsi vector + jsonb une fois par connexion, de façon idempotente.

## Détail des correctifs

### P0-1 — `register_vector(pool)` (database.py)
- **Bug** : `init_db()` → `_register_pgvector(pool)` utilise l'API pool au lieu de la connexion.
- **Racine** : mauvaise signature `pgvector.asyncpg.register_vector`.
- **Fix** : `async def _init_connection(conn)` + `register_vector(conn)` ; `create_pool(init=_init_connection)`.

### P0-2 — codec `jsonb` manquant (database.py)
- **Bug** : `context`/`chunks` jsonb non décodés → historique muet.
- **Fix** : `await conn.set_type_codec("jsonb", schema="pg_catalog", encoder=json.dumps, decoder=json.loads, format="text")` dans `_init_connection`.
- **Tests** : `backend/tests/test_integration.py` (fixture `pool`) enregistre désormais vector + jsonb via `init` → `test_insert_et_dedoublonnage` atteint son assertion de dédoublonnage (P0-4).

### P0-3 — `DELETE … RETURNING COUNT(*)` invalide (main.py, `delete_document`)
- **Bug** : `fetchval("DELETE … RETURNING COUNT(*)")` → erreur SQL (COUNT(*) hors RETURNING).
- **Fix** : `rows = await conn.fetch("DELETE … RETURNING id")` puis `deleted = len(rows)`.

### P1-1 — tâche asyncio orpheline (main.py, `/chat`)
- **Bug** : `asyncio.create_task(...)` sans référence → risque GC / `Task was destroyed`.
- **Fix** : `_task = asyncio.create_task(...)` ; `_bg_tasks.add(_task)` ; `_task.add_done_callback(_bg_tasks.discard)` (module `_bg_tasks: set`).

### P1-2 — `CORS_ORIGINS` en `*` (config.py)
- **Bug** : `CORS_ORIGINS: str = "*"` → ouvert à toutes origines.
- **Fix** : défaut restreint `http://localhost:3000,http://127.0.0.1:3000` ; commentaire incitant à lister les origines en prod via `.env`.

### P2-1 — `num_gpu` (config.py / rag_engine.py)
- **Bug** : commentaire/doc disait `num_gpu=-1` (invalide pour Ollama).
- **Fix** : commentaire corrigé en `num_gpu=99` (toutes les couches GPU).

### P2-2 — `OLLAMA_MODEL` défaut (docker-compose.yml)
- **Bug** : défaut `mistral:7b-instruct-q4_K_M` (obsolète vs décision).
- **Fix** : défaut `${OLLAMA_MODEL:-qwen3:14b}` (aligné sur la décision modèle).

## Preuves (extraits)

- `database.py:45` `async def _init_connection(conn)` + `:71` `init=_init_connection`.
- `main.py:63` `_bg_tasks: set = set()` ; `:285` add ; `:420` `deleted = len(rows)`.
- `config.py` `CORS_ORIGINS` défaut localhost ; `num_gpu=99` comment.
- `docker-compose.yml` `OLLAMA_MODEL:-qwen3:14b`.
- `test_integration.py:50` `set_type_codec` dans fixture `pool` (init callback).

## Statut

Appliqué (Plan A). À valider en exécution sur la cible (BC-250/Bazzite) : démarrage du pool,
upload, `/chat`, historique, test d'intégration Postgres.
