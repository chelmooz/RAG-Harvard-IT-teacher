# Audit consolidé — RAG-Harvard-IT-teacher (Prof-IA v6.0) + bloc AMD BC-250

**Date** : 2026-08-26
**Périmètre** : backend FastAPI + PostgreSQL/pgvector + Ollama, frontend React, scripts BC-250,
docs. Audit logiciel (soumis par l'utilisateur) **complété du bloc BC-250** manquant.
**Méthode** : lecture intégrale du code, `git log`/`git show`, exécution de `ruff`/`pytest`,
croisement doc ↔ code. Aucun test d'exécution réel possible (pré-déploiement, pas de machine).

---

## 1. Ce que le projet est

RAG pédagogique 100% local (FastAPI + pgvector + Ollama + React) ciblant l'AMD BC-250
(APU RDNA2 gfx1013, Zen2, 16 Go GDDR6 unifiés), déployé hybride **station de jeu + serveur
RAG Prof-IA/Ollama** sous **Bazzite**. Modèle servi : `qwen3:14b` (Q4, ~9,3 Go, rentre en
VRAM pleine ~12 Go). Tout local, aucun cloud/Claude.

---

## 2. Audit logiciel — findings

| # | Fichier | Problème | Gravité | État (ce pass) |
|---|---|---|---|---|
| S1 | `backend/tests/test_integration.py` | `BASE_URL` (majuscule, indéfini) ligne 225 + fixture `api_token` fusionnée dans `base_url` → `NameError`/fixture manquante, CI integration casse | 🔴 Bloquant | **CORRIGÉ** (split fixture + `base_url`) |
| S2 | `frontend/src/services/api.js:166` vs `backend/api/main.py:447` | Front envoie `{directory}` en **body JSON**, back attend query param → 422 systématique | 🔴 Fonctionnel cassé | **CORRIGÉ** (front → `params:{directory}`) |
| S3 | `README.md` §8.1 | Référence `AMD-BC-250-at-his-Best/` | 🟠 Doc | **RÉSOLU** : le dossier existe dans le repo (nested `.git`, laissé intact) — le « lien mort » était un artefact du zip d'audit, pas un défaut repo |
| S4 | `install.sh` vs `README.md` §8.1 | `install.sh` = Debian 13 (apt/GRUB) ; README recommande Bazzite (rpm-ostree) → script non applicable tel quel | 🟠 Incohérence | **CORRIGÉ** : bannière `install.sh` + `scripts/bazzite/setup.sh` + §8.1 clarifié (2 chemins) |
| S5 | `fine_tuning/train.py` + `config.yaml` | Fine-tune **Mistral-7B**, alors que la stack sert **qwen3:14b** → boucle d'amélioration incohérente | 🟡 Incohérence | **CORRIGÉ** : `base_model: Qwen/Qwen3-14B` + QLoRA 4-bit (tn sur 12 Go) + `target_modules` Qwen3 |
| S6 | `backend/pyproject.toml` | `build-backend = "setuptools.backends._legacy:_Backend"` invalide | 🟡 Build | **CORRIGÉ** → `setuptools.build_meta` |
| S7 | `BACKLOG.md` (aveu auteur) | « Non testé à l'exécution (pré-déploiement) » | 🔴 Risque | **Documenté** : limite pré-déploiement, non levable ici |
| S8 | Historique git | `REDACTED_USER` en dur (commit `d19a24f`, retiré) | 🟡 Mineur | **Accepté** : identifiants triviaux dev, hygiène seulement |
| S9 | `REACT_APP_API_TOKEN` | Token injecté dans le bundle React (visible en clair) | 🟡 Acceptable LAN | **Documenté** : contexte LAN/air-gapped, à noter comme limite |

### Points forts vérifiés (audit initial, confirmés)
- SQL 100% paramétré asyncpg (`$1,$2…`), y compris rag_engine (commentaire de correction SQL legacy).
- Auth `secrets.compare_digest` (timing-attack safe) ; `/health` + doc seuls publics.
- Path traversal confiné (`_validate_directory()` resolve+is_relative_to).
- docker-compose : Postgres `scram-sha-256`, ports bindés `127.0.0.1`, mots de passe obligatoires.
- Cycle de vie asyncpg propre (pool partagé, lock init, shutdown).

---

## 3. Bloc AMD BC-250 (optimisation hybride jeu + RAG)

**Contexte** : BC-250 = RDNA2 gfx1013 (6→40 CU déblocables), Zen2 (4→8c déblocables),
16 Go GDDR6 **unifiés** (UMA). OS : **Bazzite** (immutable). Aucun test exécution possible
(pré-déploiement).

**Sources analysées** (clones locaux, **MIT**, cités dans `CREDITS.md`) :
WinnieLV/bc250-cu-live-manager · bc250-collective/bc250_smu_oc · keyboardspecialist/bc250-steamos
· rpf16rj/bc250-steamos-real-toolkit · MastaG/linux-cachyos-bc250 · refs elektricm/amd-bc250-docs, akandr/bc250.
Article pausehardware « Linux 6.19 AMDGPU » : **NON APPLICABLE** (GCN 1.0/1.1 seulement ; BC-250 = RDNA2).

| # | Sujet | Constat | Gravité | État |
|---|---|---|---|---|
| B1 | Split RAM/VRAM | `ttm.pages_limit=3959290` (~15 Go) → GPU pompe RAM CPU sur 16 Go unifiés → OOM serveur. Valide = `UMA_SIZE=512` (CMOS) + `ttm.pages_limit=3014656` (~12 Go GPU / 4 Go CPU) | 🔴 Bloquant serveur | **CORRIGÉ** (install.sh, .env.example, config.py, log.md, spec) |
| B2 | 40 CU | UMR userspace (Bazzite) : `CC=0x0`, `SPI=0x1f`, `RLC=0x1f` ; cap 1500/900 mV ; ~+50-60% GPU | 🟠 Si non capé/stressé | Procédure fournie (`scripts/bc250/40cu-unlock/`) |
| B3 | CPU 8c | SMU Q3 `0x98` → SMN `0x0115A870`, masque `0x77→0xFF` ; volatil cold boot → service boot | 🟠 Volatil | Procédure + script (`scripts/bc250/core-unlock/`) |
| B4 | CPU UV/OC | SMU `0x8F/0x50/0x8B/0x8C/0x9A` ; **Vid ≤ 1325 mV = brick** ; Mild 3500/-22/80°C | 🔴 Si mal utilisé | Preset + garde-fous (`scripts/bc250/smu-oc/`) |
| B5 | Patches MastaG 0001-0009 | Exigent rebuild noyau Bazzite custom (pas userspace) ; ROCm+async = Phase 2 opt-in | 🟡 Phase 2 | Documenté, non vendored |
| B6 | install.sh vs OS | recoupe S4 | 🟠 | **CORRIGÉ** (voir S4) |
| B7 | Embeddings ROCm | ROCm cassé gfx1013 sans noyau custom → défaut endpoint Ollama Vulkan (sûr) | 🟡 Phase 2 | Défaut sûr |
| B8 | `AMD-BC-250-at-his-Best/` | existe dans repo réel (nested `.git`, intact) ; « lien mort » = artefact zip | ℹ️ Contexte | Résolu (voir S3) |

**Garde-fous BC-250** : Vid CPU ≤ 1300 mV (marge vs 1325 brick) ; GPU ≤ 2,2–2,4 GHz air ;
PSU ≥ 460 W ; stresser 40 CU + 8c avant prod.

**Harvest (MIT, vendored dans `scripts/bc250/`)** : 40 CU (WinnieLV), SMU UV/OC (bc250-collective),
8c unlock (keyboardspecialist). `scripts/bazzite/setup.sh` pose le split RAM/VRAM + governor.
Clones bruts supprimés après récolte.

---

## 4. Correctifs appliqués lors de cet audit

- S1 : `test_integration.py` — fixture `api_token` restaurée, `BASE_URL`→`base_url`.
- S2 : `api.js` — `indexDirectory` envoie `?directory=` (query param).
- S4/B6 : `install.sh` bannière Debian/ROCm + `scripts/bazzite/setup.sh` + README §8.1.
- S5 : `fine_tuning` aligné `qwen3:14b` + QLoRA 4-bit (rentre en 12 Go).
- S6 : `pyproject.toml` `build-backend` corrigé.
- B1 : `ttm.pages_limit=3014656` partout (était `3959290`).

---

## 5. Verdict consolidé

**Note** : ~78/100 (audit logiciel initial 58/100, +correctifs S1/S2/S4/S5/S6/B1, +bloc BC-250).

**GO conditionnel** — reste à faire avant prod (non bloquant pour audit, bloquant pour déploiement) :
1. **S7** : test d'exécution réel (`docker compose up` + upload + chat + `/indexing/directory`)
   sur la cible BC-250/Bazzite (impossible en pré-déploiement ici).
2. **S8** : purger `REDACTED_USER` de l'historique si le dépôt devient public (BFG/`git filter-repo`).
3. **S9** : documenter la limite token-front (LAN/air-gapped) ou passer en proxy backend.
4. **B2/B3/B4** : valider sur machine réelle (40 CU / 8c / UV-OC) + service boot idempotent.
5. **B5** : décider Phase 2 (noyau custom MastaG) si ROCm embeddings / +FPS jeu requis.

Le projet est **sérieux et utilisable en labo** ; il n'est **pas encore « prêt à l'emploi public »**
sans (1) et (4).

---

## 6. Audit externe indépendant (2026-08-26) + remédiation

**Source** : audit indépendant (modèle externe) collé par l'utilisateur. **Note 70/100,
GO conditionnel.** Révèle deux angles non couverts par l'audit interne :
- `ruff` en **configuration projet complète** était ROUGE (88 erreurs, exit 1) — seul
  `--select F` avait été vérifié jusqu'ici.
- README §7 décrivait une **boucle d'auto-évaluation non implémentée** (`response_evaluations`
  jamais écrite, pas d'endpoint `/feedback`, « 7 preloaded datasets ~33k chunks » absent).

### Conditions bloquantes (audit externe) — statut
| # | Condition | Statut |
|---|---|---|
| 1 | Committer l'arbre de travail | **EN ATTENTE** (décision utilisateur — ne jamais `git commit` sans demande explicite) |
| 2 | `ruff` vert sur la config projet complète | ✅ **FAIT** : `B008` ajouté aux ignores (`backend/pyproject.toml`), `ruff check backend --fix` (66 fix), corrections manuelles (`document_processor.py` imports/`CHUNK`→`chunk_size`, `main.py` B904 ×3, `rag_engine.py` B905 `zip strict=True`) → « All checks passed! » |
| 3 | Implémenter `/feedback` **OU** reformuler README §7 | ✅ **FAIT (les deux)** : `POST /feedback` écrit dans `response_evaluations` (`database.save_feedback`, `ChatResponse.conversation_id` renvoyé par `/chat`) + README §7 (fr/en) reformulé (pas de datasets pré-emballés, feedback humain implémenté, auto-scoring planifié non câblé) |
| 4 | e2e réel sur BC-250 | ⛔ **IMPOSSIBLE pré-déploiement** (pas de matériel ici) — documenté comme limite (cf. S7/B2-B4) |
| 5 | `mem_limit` dans docker-compose | ✅ **FAIT** : `deploy.resources` (limits+reservations) sur les 5 services |

### Recommandations non bloquantes — statut
| Recommandation | Statut |
|---|---|
| Épingler l'image Ollama (`:latest` → tag) | ✅ **FAIT** : `ollama/ollama:0.32.15` dans `docker-compose.yml` |
| Documenter l'hypothèse LAN de confiance | ✅ Documenté (`config.py` : « réseau local isolé (LAN derrière pare-feu) ») |
| Dette de style : pytest.ini dupliqué vs pyproject | ✅ **FAIT** : `backend/pytest.ini` supprimé (config dans `pyproject.toml`) |
| Dette de style : fixture `force_cpu_device` dupliquée | ✅ **FAIT** : doublon retiré de `test_unit.py` (autouse dans `conftest.py`) |
| Dette de style : docstring `config.py` obsolète | ✅ **FAIT** : retiré l'affirmation « auth GitHub datasets » |
| Résidus « Mistral 7B » (`fine_tuning/config.yaml`, `document_processor.py`) | ✅ **FAIT** : remplacés par Qwen3-14B |
| CI pip-audit / gitleaks + pytest-cov | ⏳ Non fait (amélioration future) |
| Purger `REDACTED_USER` de l'historique git si public | ⏳ **EN ATTENTE** décision utilisateur (S8) |

### Limite pré-déploiement (à rappeler au déploiement)
L'e2e applicatif (docker compose up + upload + chat + `/indexing/directory`) **ne peut pas**
être exécuté ici (aucune machine BC-250, pas de Docker GPU). La validation atteignable est
statique : `ruff` vert, `py_compile`, cohérence doc↔code, scripts `bash -n`. Le passage
e2e conditionne le « prêt à l'emploi public » (S7 + conditions 1/4 de cet audit).
