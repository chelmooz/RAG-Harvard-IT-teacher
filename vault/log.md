# Log de maintenance — Vault LLM Wiki (Modèle 3)

Format OKF : `## YYYY-MM-DD — action`.

## 2026-08-26 — Initialisation du scaffold (Modèle 3 : LLM Wiki + RAG)
- Création du vault de connaissances compilées `vault/` selon le concept **LLM Wiki (Karpathy)**
  (réf. lucasastorian/llmwiki), le **Modèle 3 (LLM Wiki + RAG)** et les principes **OKF**.
  Exécuteur = plugin Obsidian **karpathywiki** (green-dalii) sur **Ollama** (modèles locaux FREE).
- Structure : `vault/raw/` (sources brutes, lues en place) + `vault/wiki/` (connaissances
  compilées générées par le plugin : `index.md` + `concepts/entities/sources`). Le cache vit
  dans `.obsidian/plugins/karpathywiki/`.
- The Schema = `vault/AGENTS.md`. Log = `vault/log.md` (PROTÉGÉ).
- Positionnement : ce vault est la couche de représentation compilée ; le RAG Prof-IA
  (racine du repo) est la couche d'accès et doit indexer aussi `vault/wiki/**/*.md`.
- Aucun contenu réel ingesté (v1 = scaffold seul).

## 2026-08-26 — Exécuteur agnostique : OpenCode ajouté comme option
- Le vault peut être maintenu par le plugin **karpathywiki** OU par **OpenCode** (les deux
  locaux, modèles FREE). Format agnostique (Markdown + frontmatter + `[[liens]]`) = contrat
  commun aux deux exécuteurs → interchangeables et cohabitables.
  - Ajout de `vault/.gitignore` (`.obsidian/`, caches OS).

## 2026-08-26 — Alignement OKF (Google Cloud Open Knowledge Format)
- Le schéma de page (`vault/AGENTS.md`) et la spec sont alignés sur l'OKF réel : Markdown +
  frontmatter YAML (champs `type`, `title`, `description`, `resource`, `status`,
  `stale_after`, `tags`, `generated`, `verified`, `sources` en objets `uri/author/last_modified`).
- `sources` devient une liste d'objets (provenance structurée) ; `genere_le`/`verifie` →
  `generated`/`verified` (objets by/at). `statut` (confiance) conservé en extension.
- Liens `[[wiki-links]]` = graphe de connaissances (équivalent aux liens Markdown OKF).

## 2026-08-26 — Plugin `okf-enforcer` ajouté (exécuteur OKF)
- Le vault sera maintenu par **`karpathywiki`** (génération : Ingest/Query/Lint) **+ `okf-enforcer`**
  (MartinForReal, v0.6.1, Apache-2.0) qui valide/corrige le frontmatter OKF v0.2 en continu
  (auto-fix `type`/`title`/`generated`, hooks on-save, rapport vault, `index.md`/`log.md`).
- OKF passe de « déclaré par convention » à « **appliqué par outil** ». `status` aligné sur
  le vocabulaire OKF (`draft`/`stable`/`deprecated` ; notre `statut` de confiance reste en extension).
- `okf_version: "0.2"` déclaré dans `wiki/index.md`.

## 2026-08-26 — Décision modèle : `qwen3:14b`
- Modèle retenu : **`qwen3:14b`** (Qwen3-14B, Q4_K_M, ~9,3 Go) — **tient intégralement en VRAM**
  sur le BC-250 (~12 Go budget) → **GPU plein, sans offload partiel**. `num_ctx` : 1024
  (ops vault légères) / 8192 (RAG profond).
- Impact docs : `README.md`, `README.fr.md`, `vault/AGENTS.md`, `docker-compose.yml`
  (`OLLAMA_MODEL: qwen3:14b`). Voir `vault/docs/superpowers/specs/`.

## 2026-08-26 — Audit backend + correction des bugs (Plan A, P0–P2)
- Audit vérifié contre le code (pas d'affirmation non prouvée). 2 P0, 2 P1, 2 P2 corrigés
  dans `backend/api/{database,main,config}.py`, `docker-compose.yml`, `tests/test_integration.py`.
- Racine commune P0-1/P0-2 : `init_db()` appelait `register_vector(pool)` (API asyncpg
  erronée) et n'enregistrait PAS le codec JSONB → crashs au démarrage, upload 500, `/chat`
  500, et historique de conversation **muet** (jsonb non décodé). Correction : callback
  `init=_init_connection` par connexion (vector + jsonb).
- Détail + preuves dans `vault/docs/superpowers/specs/2026-08-26-backend-audit-remediation.md`.
- Non testé à l'exécution (pré-déploiement : pas de Postgres/Ollama dispo).

## 2026-08-26 — BC-250 : repos communautaires comme source de vérité
- Source de vérité matériel = docs communautaires `elektricm/amd-bc250-docs`
  (<https://elektricm.github.io/amd-bc250-docs/>) + serveur Ollama+Vulkan `akandr/bc250`
  (<https://github.com/akandr/bc250>). Notre doc interne `Prof-IA-v5-Documentation-BC250.md`
  **non touchée** (décision).
- OS cible : **Bazzite** (Desktop). BIOS P3.00 / 512 Mo VRAM dynamique / IOMMU OFF fait.
  Governor `cyan-skillfish-governor-smu` (COPR filippor/bazzite), `RADV_DEBUG=nohiz`,
  TTM `pages_limit=3014656` (split serveur 12 Go GPU / 4 Go CPU ; le précédent
  `3959290` ≈15 Go était erroné — il aurait pigé la RAM CPU sur 16 Go unifiés).
- Détail dans `vault/docs/superpowers/specs/2026-08-26-bc250-bazzite-deployment.md`.

## 2026-08-26 — Analyse profonde optimisation BC-250 (hybride jeu + RAG)
- Clones des 5 repos communautaires dans `bc250-sources/` (gitignoré) ; extraction des séquences
  registres/SMU exactes + portabilité noyau. Spec consolidée `2026-08-26-bc250-bazzite-deployment.md`
  (phases 1/2, corrections, sécurité). 40 CU via UMR (pas de rebuild), CPU 8c + UV/OC via SMU,
  split RAM/VRAM corrigé (ci-dessus). Article 6.19 = non applicable (GCN, pas RDNA2).
- `install.sh` / `.env.example` / `backend/api/config.py` corrigés : `ttm.pages_limit=3014656`
  (ancien `3959290` ≈15 Go erroné supprimé).

## 2026-08-26 — Remédiation audit logiciel + bloc BC-250 consolidé
- Audit logiciel (fourni) complété du bloc BC-250 → `vault/docs/superpowers/audit/2026-08-26-audit-consolidated.md`.
- S1 `test_integration.py` (BASE_URL→base_url, fixture api_token) ; S2 `api.js` query param directory ;
  S4/B6 `install.sh` bannière + `scripts/bazzite/setup.sh` + README §8.1 ; S5 `fine_tuning` Qwen3-14B QLoRA 4-bit ;
  S6 `pyproject.toml` build-backend. Vérif : py_compile OK, pytest collect 7 tests OK.
- Harvest MIT `scripts/bc250/` (WinnieLV 40cu, bc250-collective smu-oc, keyboardspecialist 8c) ; clones
  `bc250-sources/` supprimés ; `CREDITS.md` + README §10 remerciements.
