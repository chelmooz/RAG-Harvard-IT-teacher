# BACKLOG — RAG-Harvard-IT-teacher (Prof-IA + Vault LLM Wiki)

Journal des décisions et traces de session. Modèle local FREE uniquement, **aucun Claude/cloud**.

## 2026-08-26 — Session audit + remédiation + docs

### Contexte
- Projet = `chelmooz/RAG-Harvard-IT-teacher` (Prof-IA v6.0) + vault LLM Wiki (Modèle 3 + OKF v0.2).
- Cible = AMD BC-250 sous Bazzite, modèles locaux FREE (Ollama `:11436` hôte / `:11434` docker).

### Décisions
1. **Modèle** : `qwen3:14b` (Qwen3-14B, Q4_K_M, ~9,3 Go, GPU plein sans offload).
   `num_ctx` 1024 / 8192.
2. **BC-250** : source de vérité = `elektricm/amd-bc250-docs` + `akandr/bc250`. Doc interne
   `Prof-IA-v5-Documentation-BC250.md` **non touchée**. OS = Bazzite.

### Travail effectué
- **Plan A — bugs backend (P0–P2) corrigés et vérifiés contre le code** :
  - `backend/api/database.py` : P0-1 + P0-2 → callback `init=_init_connection` (register_vector
    par connexion + codec jsonb). Racine des crashs démarrage/upload/`/chat` + historique muet.
  - `backend/api/main.py` : P0-3 `DELETE … RETURNING id` + `len(rows)` ; P1 `_bg_tasks` set.
  - `backend/api/config.py` : P2 `num_gpu=99` (comment) ; P1 `CORS_ORIGINS` localhost.
  - `docker-compose.yml` : P2 `OLLAMA_MODEL:-qwen3:14b`.
  - `backend/tests/test_integration.py` : P0-4 codec jsonb+vector dans fixture pool.
  - *Non testé à l'exécution (pré-déploiement : pas de Postgres/Ollama).*
- **Plan C — docs mises à jour** : `README.md`, `README.fr.md`, `vault/AGENTS.md`
  (modèle aligné sur `qwen3:14b`, suppression offload partiel / `num_ctx 75000` ;
  ajout réfs communautaires BC-250).
  `docker-compose.yml` déjà aligné (Plan A).
- **Persistance** : specs `vault/docs/superpowers/specs/2026-08-26-{backend-audit-remediation,bc250-bazzite-deployment}.md`
  + entrées `vault/log.md`.

### Fichiers modifiés (cette session)
- `backend/api/database.py`
- `backend/api/main.py`
- `backend/api/config.py`
- `docker-compose.yml`
- `backend/tests/test_integration.py`
- `README.md`, `README.fr.md`
- `vault/AGENTS.md`, `vault/log.md`
- `vault/docs/superpowers/specs/2026-08-26-backend-audit-remediation.md` (nouveau)
- `vault/docs/superpowers/specs/2026-08-26-bc250-bazzite-deployment.md` (nouveau)
- `BACKLOG.md` (nouveau, repo root)

### Bloqueurs / à suivre
- `AMD-BC-250-at-his-Best/` = nested `.git` → vendor vs submodule avant `git add`.
- Embeddings ROCm cassé gfx1013 → fallback CPU ou endpoint embedding Ollama (à confirmer).
- Aucun `git commit` fait (utilisateur n'a pas demandé de commit).

## 2026-08-26 — Analyse profonde optimisation BC-250 (hybride jeu + RAG)

- **Demande** : meilleure config BC-250 en assemblant les meilleurs morceaux de chaque repo,
  machine hybride (station de jeu + serveur RAG Prof-IA/Ollama). Approuvé : clone + analyse + spec.
- **Clones** (lecture seule, dans `bc250-sources/`, gitignoré) : MastaG/linux-cachyos-bc250,
  rpf16rj/bc250-steamos-real-toolkit, keyboardspecialist/bc250-steamos,
  WinnieLV/bc250-cu-live-manager, bc250-collective/bc250_smu_oc.
- **Article pausehardware (Linux 6.19 AMDGPU) = NON APPLICABLE** : concerne GCN 1.0/1.1,
  pas RDNA2/gfx1013 (BC-250 utilise déjà AMDGPU).
- **Séquences exactes extraites** (spec `2026-08-26-bc250-bazzite-deployment.md`) :
  - 40 CU : `mmCC_GC_SHADER_ARRAY_CONFIG=0x0`, `mmSPI_PG_ENABLE_STATIC_WGP_MASK=0x1f`,
    `mmRLC_PG_ALWAYS_ON_WGP_MASK=0x1f` via UMR (Bazzite, sans rebuild noyau), cap 1500/900 mV.
  - CPU 8 cœurs : SMU Q3 `0x98` → SMN `0x0115A870`, masque `0x77→0xFF` (volatile cold boot).
  - CPU UV/OC : SMU `0x8F/0x50/0x8B/0x8C/0x9A` ; plafond **Vid ≤ 1325 mV** (brick sinon) ;
    profil « Mild » 3500 MHz / scale −22 / 80 °C.
  - RAM/VRAM : `UMA_SIZE=512` (CMOS) + `ttm.pages_limit=3014656` (Bazzite : `rpm-ostree kargs`).
- **Correction TTM** : `3959290` (~15 Go) → `3014656` (~12 Go GPU / 4 Go CPU) dans
  `install.sh`, `.env.example`, `backend/api/config.py`, `vault/log.md`.
- **Plan en 2 phases** : Phase 1 (userspace, aucun rebuild) couvre 100 % serveur RAG + jeu de base ;
  Phase 2 (opt-in) = noyau Bazzite custom (patches MastaG 0001-0009) + Mesa async pour ROCm/embeddings
  et +10-15 FPS jeu.
- `AMD-BC-250-at-his-Best/` non touché (nested .git respecté).

## Statut
Prêt pour **soumission à audit** : corrections tracées, justifiées par le code, docs cohérentes.

## 2026-08-26 — Remédiation audit logiciel + bloc BC-250 consolidé

- **Audit logiciel** fourni par l'utilisateur ; manquait le bloc BC-250 → complété dans
  `vault/docs/superpowers/audit/2026-08-26-audit-consolidated.md` (note consolidée ~78/100).
- **Correctifs applicatifs (S1–S6, B1)** :
  - S1 `test_integration.py` : fixture `api_token` restaurée, `BASE_URL`→`base_url` (collect OK).
  - S2 `frontend/src/services/api.js` : `indexDirectory` → query param `?directory=`.
  - S4/B6 `install.sh` : bannière Debian/ROCm + `scripts/bazzite/setup.sh` + README §8.1 (2 chemins).
  - S5 `fine_tuning` : `Qwen/Qwen3-14B` + QLoRA 4-bit (rentre 12 Go) + `target_modules` Qwen3.
  - S6 `backend/pyproject.toml` : `build-backend` → `setuptools.build_meta`.
  - B1 TTM `3959290`→`3014656` (déjà fait, confirmé sans valeur live résiduelle).
- **Harvest BC-250 (MIT)** : `scripts/bc250/` (40cu WMVieLV, smu-oc bc250-collective,
  8c keyboardspecialist) + `scripts/bazzite/setup.sh`. Clones `bc250-sources/` supprimés.
  `CREDITS.md` + remerciements README §10.
- **Vérif** : py_compile backend + scripts OK ; pytest collect 7 tests OK ; grep `pages_limit=3959290`
  ne reste que dans doc interne (non touchée) + notes de correction.
- **Non levables (pré-déploiement)** : S7 exécution réelle, S8 purge historique `REDACTED_USER`,
  S9 limite token-front, B2/B3/B4 validation machine réelle, B5 Phase 2 noyau.
- Aucun `git commit` (non demandé).

## 2026-08-26 — Ménage + revue de code (clean-code)

- **Nettoyage** : `bc250-sources/` confirmé supprimé ; aucune référence stray ; `git status`
  propre (édits + nouveaux fichiers attendus : BACKLOG, CREDITS, README.fr, scripts/, vault/).
- **Revue backend** (database/main/rag_engine/document_processor/config) :
  - Aucun code commenté, aucun `TODO`/`FIXME` périmé (ruff + grep).
  - ruff `--select F` : 0 import mort / variable morte / nom indéfini.
  - Toutes les fonctions/helpers sont câblés à un endpoint ou caller.
- **Code mort retiré** :
  - `rag_engine.py` : `check_chroma_health` (alias trompeur — ChromaDB supprimé en v5).
  - `config.py` : champ `AMD_ZEN2_CORES` (défini, jamais lu nulle part).
- **Vérif post-retrait** : ruff F OK + py_compile OK.
- Hors périmètre revue : `scripts/bc250/` (vendored MIT tiers, exclus), `frontend/` (léger, non audité en profondeur), `vault/` (LLM wiki).

## 2026-08-26 — Audit externe + remédiation BC-250 (gaps critiques)

- **Audit externe** (modèle indépendant, 70/100 GO conditionnel) : ruff rouge (config complète),
  README §7 auto-éval non implémentée, `mem_limit` docker absent, image Ollama `:latest`,
  dette style. -> Tout corrigé (commit `d0cfd89` + `git filter-repo` purge `user:user`,
  remote `origin` ré-ajouté). Force-push requis si push (historique réécrit).
- **Comparaison vs référentiel `AMD-BC-250-at-his-Best` (bc250-beast, modules 00-09)** :
  révèle gaps dans nos `scripts/bc250` :
  - 🔴 **BUG critique** : `apply_phase1.sh` invoquait les outils vendored SANS sous-commande
    (CU→menu interactif, cores→RuntimeError, OC→no-op) → aucune optimisation réellement appliquée.
    CORRIGÉ : `enable all`+`write-service-table` (CU), `apply` (cores), `bc250_detect --frequency/--vid/--temp -c` → `bc250_apply --apply` (OC), avec valeurs par défaut 3850 MHz/1150 mV (env-overridable).
  - ⚠️ **zswap + swapfile Btrfs 32G + mitigations=off** ajoutés dans `scripts/bazzite/setup.sh`
    (module 07) — critique pour les 4 Go CPU du serveur RAG (anti-OOM).
  - ⚠️ **config.toml du governor** généré (`/etc/cyan-skillfish-governor/config.toml`, safe-points 350→2000 MHz).
  - ⚠️ **`validate.sh`** créé (équivalent module 09) : CU/cœurs/VRAM/temp/**tension ≤1300 mV
    (FAIL dur)/services + score + stress optionnel.
  - 🟡 `health-check.sh` étendu (VRAM BIOS, services, garde-fou tension en warning ; exit sur CU+cœurs).
- **Vérif** : `bash -n` OK sur apply_phase1/health-check/validate/setup.
- **Non fait (optionnel)** : vendoriser `bc250-uefi-menu` (BIOS flash 8c persistant), extras
  (NullVRS/Turing), checklist module 01, preflight module 00.
- Non commité (le « go » visait l'implémentation, pas le commit).
