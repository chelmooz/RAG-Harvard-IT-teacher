# Audit Méticuleux Pré-Déploiement — RAG-Harvard-IT-teacher
**Date** : 2026-08-27
**Cible** : `origin/feat/auto-eval-rag` @ `94e6c41` (Bazzite-only, CI vert, V6 docs)
**Périmètre** : codebase complet (backend FastAPI, frontend React, docker, CI, vault docs)
**Contexte** : JARVIS Portable — BC-250 16 Go GDDR6 OC, single-user, hors-réseau, qualité > latence

---

## SCORE PRÉ-DÉPLOIEMENT : **92 / 100**

> Détail : codebase déployable, sûre et **cohérente** (sécurité, lint, tests backend solides).
> CI **entièrement verte** (run `33067522002` : 6/6 jobs success, Docker Build + Intégration réels).
> Stratégie **Bazzite-only** validée — scripts Debian retirés, docs V6 alignées.
> Principaux points restants déduits : (1) couverture de tests frontend minimale
> (1 smoke test) ; (2) calibration matérielle BC-250 non mesurable (environnement absent).

---

## 1. Sécurité — 9/10

| Contrôle | État | Preuve |
|----------|------|--------|
| Secrets hardcodés | ✅ Aucun | grep `api_key/secret/password/token=["'...` → 0 match |
| Injection SQL | ✅ Paramétrée | asyncpg `$1,$2,…` partout (database.py, main.py) ; aucun `.format()`/`+` dans SQL |
| Comparaison token | ✅ Temps-constant | `secrets.compare_digest` (main.py:52) |
| CORS | ✅ Restreint par défaut | `CORS_ORIGINS` = localhost (config.py:142), piloté par .env |
| Auth API | ✅ Bearer obligatoire | `verify_api_token` sur tous endpoints sauf `/health`,`/docs` |
| Défaut fail-safe | ✅ | `AUTO_EVALUATE=False` (config.py:115) + compose |
| API_TOKEN requis | ✅ | validateur `_validate_api_token` (sinon startup refuse) |

Note : commentaire config.py:11-12 (« CORS : toutes origines (*) ») contredit encore la valeur par défaut localhost — incohérence **doc uniquement**, le code reste sûr. Non bloquant.

---

## 2. Qualité statique — 10/10

- **Backend ruff** : `ruff check api/ tests/` → **All checks passed!** (vérifié localement)
- **Frontend eslint** : `npx eslint src/ --ext .js,.jsx` → **0 warning/0 error**
- **Aucun** `TODO`/`FIXME`/`NotImplementedError`/stub dans `backend/api/`
- Typage strict (pydantic v2, hints complets), DIP via `Depends`

---

## 3. Tests — 7.5/10 (backend fort / frontend faible)

| Suite | État | Détail |
|-------|------|--------|
| Backend unit (`-m "not integration"`) | ✅ | 65 passed ; code inchangé |
| Frontend (`react-scripts test`) | ⚠️ | **1 seul** smoke test (rendu Landing). 0 test composant/integration |
| Intégration (Postgres+pgvector) | ✅ | fixture `pool` auto-initialise le schéma ; **exécuté et passé en CI** (run `33067522002`, 2m32s, non skippé) |
| Propagation exit-code pytest | ✅ | correction `rc=5` (no tests) en place |

Risque : couverture frontend quasi nulle. Recommandé : tests `api.js` (auth/timeout) + 1 test composant (ex. `Dashboard`).

---

## 4. CI/CD — 10/10

État validé par re-run GitHub Actions `33067522002` (tous jobs `success`) :
- ✅ `Lint Backend (ruff)` — `All checks passed!`
- ✅ `Lint Frontend (eslint)` — 0 warning/0 error
- ✅ `Test Backend (pytest unit)` — 65 passed
- ✅ `Test Backend (integration)` — schéma auto-init, exécuté et passé (2m32s)
- ✅ `Test Frontend (react-scripts test)` — 1 passed
- ✅ `Docker Build` — torch ROCm→CPU fallback OK (pandas `2.2.3` prébuild cp313)

Correctifs commités (`ee959f0`, `92191fd`, `67de18d`, `94e6c41`) **validés par re-run vert**.
Aucun point restant.

---

## 5. Complétude & Architecture — 10/10

- Aucune implémentation partielle détectée (scan stubs/TODO négatif)
- DIP respecté (composition root dans `main.py` + `dependencies.py`)
- Séparation claire api / rag_engine / database / evaluation / document_processor
- OKF + vault LLM-Wiki documentés et cohérents (Modèle 3)
- **Stratégie OS unifiée** : Bazzite-only (rpm-ostree) — scripts Debian retirés, pas de mélange

---

## 6. Documentation — 10/10

- README FR/EN exhaustifs, §8.1 **install path unique Bazzite** (plus de branche Debian)
- `Prof-IA-v6-Documentation-BC250.md` : specs Bazzite-first complètes (kargs rpm-ostree, UMR 40CU, SMU UV/OC, qwen3:14b, dual ROCm/Vulkan, auto-éval séq, OKF vault)
- `scripts/AGENTS.md` aligné (bc250 40CU/SMU/core-unlock, plus de unlock-40cu.sh)
- Roadmap micro-tâches présente (`H:\Suivi\AUTO_EVAL_ROADMAP.md`, `CI_FIX_ROADMAP.md`)
- Incohérence CORS * vs localhost (config.py comment) seule mineure restante — non bloquante

---

## 7. Opérabilité — 8/10

- Endpoint `/health` multi-composants, logs structurés (loguru)
- Rollback documenté (`git revert` + `docker compose up -d`)
- Défauts fail-safe (AUTO_EVALUATE off par défaut)
- Calibration BC-250 (Pearson r ≥ 0.7 Judge vs humain, baseline, load test) **non mesurable** — hardware absent
  (bloque l'*activation* `AUTO_EVALUATE=true`, pas le *déploiement* du codebase)

---

## Verdict

🟢 **DÉPLOIEMENT DU CODEBASE : GO** — qualité, sécurité, tests backend, CI et documentation sont au standard ; auto-évaluation désactivée par défaut (zéro risque régression).

🔴 **ACTIVATION AUTO-ÉVAL (`AUTO_EVALUATE=true`) : NOGO** tant que Phase 3 (calibration BC-250) non validée sur hardware.

⚠️ **ACTIONS RECOMMANDÉES (non bloquantes)** :
1. Renforcer la couverture de tests frontend (1 → N : `api.js`, composants)
2. Calibration BC-250 (Pearson r) quand hardware dispo pour activer auto-éval

*Preuves : ruff local, eslint local, lecture main.py/config.py/database.py/Dockerfiles/ci.yml, grep sécurité, test frontend local (1 passed), CI run 33067522002 6/6 vert, git log 94e6c41.*