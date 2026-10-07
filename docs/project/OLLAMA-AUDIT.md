# Audit exhaustif des références Ollama actives

**Statut :** à valider par XZ · **Date :** 2026-10-06 · **Ticket :** G1.1 / T02
**Périmètre :** audit documentaire. Aucune modification de code, aucune modification système.

---

## 1. Méthodologie

- Recherche exhaustive `grep -rin "ollama"` sur tout le dépôt, **hors** `docs/legacy/`,
  `.git/`, `node_modules/`, `.venv/`, `__pycache__/`, `.scratch/`, `build/`, `dist/`.
- Recherche croisée des références **indirectes** : ports `11434`/`11436`, service
  `systemctl ollama`, volume `ollama_data`, healthcheck `/api/tags` — pour attraper
  le câblage Ollama qui ne prononce pas son nom.
- Résultat : **35 fichiers** contiennent au moins une occurrence. Chacun est classé
  ci-dessous. Aucune occurrence n'est restée non catégorisée.

## 2. Constat central

**Le dépôt raconte encore deux architectures simultanément.**

Le chemin d'exécution applicatif est intégralement câblé sur Ollama :

```
docker-compose.yml (service ollama)
  → backend/api/config.py (OLLAMA_HOST, OLLAMA_MODEL, OLLAMA_*)
    → backend/api/dependencies.py (OllamaLLMClient = SEULE impl. du protocole LLMClient)
      → backend/api/rag_engine.py (RAGEngine prend ollama_host, check_ollama_health)
        → backend/api/main.py (/health rapporte ollama_status, /chat)
          → backend/api/evaluation.py (call_ollama_evaluator)
            → backend/api/schemas.py (champ Health.ollama)
              → frontend (affiche health.ollama)
                → backend/tests/* (mockent OllamaLLMClient)
```

Pendant que la couche normative (ADR-002, ADR-003, maître v1.4, service systemd
`profia-llama`) prescrit llama.cpp **hors conteneur** avec
`LLAMA_SERVER_URL=http://llama-host:8081` (câblé en T01, mais **consommé par
personne** : aucun code backend ne lit encore `LLAMA_SERVER_URL`).

**Aucune occurrence qui maintient Ollama dans le chemin d'exécution cible n'est
classée `keep`.** Toutes sont classées `migrate` ou `legacy`.

## 3. Synthèse de classification

| Décision | Fichiers | Lecture |
|----------|----------|---------|
| **migrate** | 20 | Câblent activement Ollama dans l'exécution, les tests ou l'inférence. Doivent basculer vers llama.cpp / protocole `LLMClient`. |
| **legacy** | 5 | Documents racine de l'ère v6, sans bandeau, qui prescrivent l'ancienne architecture. À marquer legacy (action T05). |
| **keep** | 10 | Patrimoine historique déjà daté/marqué, ou docs v1.4 qui documentent Ollama **comme remplacé**. Ne prescrivent jamais Ollama comme cible. |
| **Total** | **35** | Exhaustivité vérifiée en §7. |

## 4. Le chemin d'exécution cible encore câblé sur Ollama (migrate)

L'ordre ci-dessous est l'ordre de dépendance réelle de la migration.

### 4.1 Infrastructure

| Fichier | Occurrences | Rôle | Classification & justification |
|----------|--------------|------|-------------------------------|
| `docker-compose.yml` | l.63–113 (service `ollama` : image `ollama/ollama:0.32.15`, devices `/dev/dri`, volume `ollama_data`, ports `127.0.0.1:11434/11436`, healthcheck `/api/tags`), l.147 (`OLLAMA_HOST: http://ollama:11434`), l.175–181 (`depends_on: ollama`), l.259 (volume `ollama_data`) | Définit et démarre Ollama en conteneur ; le backend en dépend au démarrage | **migrate** — Le service `ollama` entier contredit ADR-002 (llama.cpp hors conteneur). Action : supprimer le service `ollama`, son volume, ses ports, le `depends_on` du backend et `OLLAMA_HOST` ; raccorder le backend au réseau `profia-llama` ; `LLAMA_SERVER_URL` (ajouté en T01) devient la seule URL LLM. |
| `config/nginx.conf` | l.40, 42 (commentaires : « timeouts généreux pour les requêtes Ollama », « Ollama peut mettre jusqu'à 180s ») | Commentaires de configuration | **migrate** (mineur) — Aucune dépendance d'exécution, mais le commentaire raconte l'ancienne architecture. Action : reformuler (« requêtes LLM », « le LLM peut mettre jusqu'à 180s ») ; les valeurs de timeout restent pertinentes pour llama.cpp. |
| `.env.example` | l.19–21 (`# Ollama (défaut : http://localhost:11434)`, `# OLLAMA_HOST=`, `# OLLAMA_MODEL=`) | Exemple de configuration | **migrate** — Doit exposer `LLAMA_SERVER_URL=http://llama-host:8081` comme variable cible et retirer/marquer les `OLLAMA_*`. |

### 4.2 Backend — configuration

| Fichier | Occurrences | Rôle | Classification & justification |
|----------|--------------|------|-------------------------------|
| `backend/api/config.py` | l.50–70 (section `OLLAMA_HOST`, `OLLAMA_MODEL` + 8 options `OLLAMA_TEMPERATURE/TOP_P/TOP_K/NUM_PREDICT/NUM_CTX/NUM_THREAD/NUM_GPU/F16_KV`), l.120 (commentaire `OLLAMA_NUM_PARALLEL=1`) | Source de vérité de la configuration LLM | **migrate** — Toutes les options de génération sont au format Ollama (`num_predict`, `num_ctx`, `f16_kv`…). Action : porter les options au format llama.cpp (API OpenAI-compatible : `max_tokens`, contexte géré côté serveur, température/top_p/top_k transposables) ; `LLAMA_SERVER_URL` (T01) devient actif. Les valeurs calibrées BC-250 (temp 0.3, top_p 0.9…) sont **reportables**, mais restent des points de départ à mesurer, pas des acquis. |

### 4.3 Backend — racine de composition (le point critique)

| Fichier | Occurrences | Rôle | Classification & justification |
|----------|--------------|------|-------------------------------|
| `backend/api/dependencies.py` | l.24–60 (`class OllamaLLMClient` : POST `/api/generate`, healthcheck GET `/api/tags`), l.339–351 (`get_llm_client()` → construit `OllamaLLMClient` avec les options OLLAMA_*), l.354–369 (`get_rag_engine()` → passe `ollama_host`, `model_name`) | **Racine de composition** : `OllamaLLMClient` est l'unique implémentation du protocole `LLMClient` | **migrate** — C'est ici que la contradiction devient fonctionnelle : tout `/chat` passe par Ollama. Action : implémenter un client llama.cpp (API OpenAI-compatible `/v1/chat/completions` sur `LLAMA_SERVER_URL`) respectant le protocole `LLMClient`, et le câbler dans `get_llm_client()`. Le protocole (`protocols.py`, 0 occurrence) est **déjà abstrait** : la migration est une nouvelle implémentation + recâblage, pas une refonte. |

### 4.4 Backend — moteur et endpoints

| Fichier | Occurrences | Rôle | Classification & justification |
|----------|--------------|------|-------------------------------|
| `backend/api/rag_engine.py` | l.18, 360 (docstrings « génération LLM (Ollama) »), l.429–433 (`RAGEngine.__init__` accepte `ollama_host`, fallback `settings.OLLAMA_HOST`), l.452–468 (startup : `check_ollama_health()`, log « Ollama opérationnel »), l.509, 519 (`check_ollama_health`, close) | Moteur RAG : consomme le client injecté mais **nomme** Ollama partout | **migrate** — Le moteur reçoit déjà le `LLMClient` par injection ; il faut retirer le paramètre `ollama_host`, renommer `check_ollama_health` → `check_llm_health` (délégué au protocole), reformuler docstrings/logs. |
| `backend/api/main.py` | l.128 (docstring « Ollama (Vulkan) »), l.139–144 (startup : `check_ollama_health()`, `ollama_status = ok/unavailable (OLLAMA_MODEL)`), l.159 (`ollama=ollama_status`), l.293 (docstring « Génération Ollama »), l.324 (`model_name=settings.OLLAMA_MODEL`) | Endpoints : `/health` expose l'état Ollama, `/chat` génère | **migrate** — `/health` doit tester le LLM cible via le protocole ; le champ renommé suit `schemas.py`. |
| `backend/api/evaluation.py` | l.4 (docstring), l.104–137 (`call_ollama_evaluator` : POST `{OLLAMA_HOST}/api/generate` format=json), l.160, 190 (appels juge/avocat) | Auto-évaluation LLM (juge + avocat du diable) | **migrate** — Portage vers l'API llama.cpp. Note : `format: json` est natif Ollama ; llama.cpp exige soit `response_format` (si supporté), soit un parsing JSON strict du contenu — à qualifier, pas à supposer. |
| `backend/api/schemas.py` | l.65 (`ollama: str` dans le schéma `Health`) | Contrat de l'API `/health` | **migrate** — Renommer le champ (ex. `llm`) ; contrat consommé par le frontend (§4.6) : renommage coordonné obligatoire. |

### 4.5 Backend — tests

| Fichier | Occurrences | Rôle | Classification & justification |
|----------|--------------|------|-------------------------------|
| `backend/tests/conftest.py` | l.9 (`setdefault OLLAMA_HOST`), l.86–96 (mock de `OllamaLLMClient._client`, réponse « Mocked Ollama response »), l.134 (mock `check_ollama_health`) | Harnais de test | **migrate** — Les tests doivent mocker le **protocole** `LLMClient` (seam publique), pas l'implémentation `OllamaLLMClient` (détail interne). Mocker l'implémentation casserait à la migration alors que le comportement est inchangé. |
| `backend/tests/test_unit.py` | l.70–102 (`TestOllamaOptions` : vérifie que les options OLLAMA_* matchent les valeurs calibrées) + docstrings | Tests unitaires des options calibrées | **migrate** — Porter sur les options llama.cpp équivalentes. Les valeurs calibrées restent des points de départ à mesurer (le test épingle la config, il ne prouve pas la performance). |
| `backend/tests/test_evaluation.py` | l.4 (docstring « client Ollama mocké ») | Tests d'évaluation | **migrate** — Suit `evaluation.py`. |

### 4.6 Frontend

| Fichier | Occurrences | Rôle | Classification & justification |
|----------|--------------|------|-------------------------------|
| `frontend/src/pages/Dashboard.js` | l.125 (`health?.ollama` → « ⚡ Modèle »), l.262 (fallback `'qwen3:14b'`) | Affiche l'état du LLM | **migrate** — Suit le renommage du contrat `/health` (`ollama` → `llm`) ; le fallback codé en dur `qwen3:14b` doit disparaître avec Ollama. |
| `frontend/src/pages/Terminal.js` | l.50 (`health?.ollama || 'qwen3:14b'`) | Affiche l'état du LLM | **migrate** — Idem. |

### 4.7 Scripts et expérimental

| Fichier | Occurrences | Rôle | Classification & justification |
|----------|--------------|------|-------------------------------|
| `scripts/bc250/bc250-game-mode.sh` | l.24–32 (mode RAG : `ollama stop/pull/run`, `systemctl --user start ollama`), l.47 (`ollama ps` dans le statut) | Bascule JEU/RAG : libère/réserve la VRAM via Ollama | **migrate** — La VRAM du serveur LLM sera détenue par `profia-llama` (systemd, système), pas par Ollama (`--user`). Le script doit arrêter/démarrer `profia-llama.service` et interroger llama-server (`/health`), pas la CLI `ollama`. Cible Bazzite v6 → à porter pour Debian 13 (ADR-001). |
| `scripts/bazzite/setup.sh` | l.12, 101 (commentaires « libération VRAM Ollama », « fait planter Ollama/Postgres ») | Script d'installation v6 Bazzite | **migrate** (commentaires) — Cohérence documentaire ; le script lui-même est v6/Bazzite, hors cible v1.4 Debian 13. |
| `scripts/bc250/README.md` | l.19 (tableau : « libère/réserve VRAM Ollama ») | Doc du game-mode | **migrate** — Suit le script. |
| `experimental/fine_tuning/config.yaml` | l.5, 17 (« arrêter Ollama avant », « IMPORTANT : arrêter Ollama ») | Prérequis VRAM du fine-tuning | **migrate** — Le prérequis devient « arrêter `profia-llama` ». |
| `experimental/fine_tuning/train.py` | l.4 (« même modèle que servi en prod par Ollama ») | Doc du fine-tuning | **migrate** — Le modèle de base référencé (Qwen3-14B) est lui-même legacy vs le candidat Qwen2.5-7B : à aligner au moment de la migration. |
| `experimental/README.md` | l.28 (« arrêter Ollama (`systemctl stop ollama`) ») | Doc expérimentale | **migrate** — Idem. |

## 5. Documents racine de l'ère v6 sans bandeau (legacy)

Ces fichiers ne s'exécutent pas, mais ils **prescrivent** l'ancienne architecture à la
racine du dépôt, sans marquage — c'est la contradiction documentaire active.

| Fichier | Occurrences | Contenu | Classification & justification |
|----------|--------------|---------|-------------------------------|
| `BC-250-INSTALL-GUIDE.md` | 35 | Guide d'installation v6 **Bazzite + Ollama** (`ollama pull`, ports 11434/11436, `bc250-game-mode` pour Ollama) | **legacy** — Prescrit l'architecture remplacée par ADR-001 (Debian 13) et ADR-002 (llama.cpp). Action recommandée (T05) : bandeau legacy + renvoi vers `INSTALLATION.md` (T03) qui le remplacera. |
| `BC-250-INSTALL-GUIDE-EN.md` | 36 | Version anglaise du même guide | **legacy** — Idem. |
| `Prof-IA-v6-Documentation-BC250.md` | 21 | Doc technique v6 : « Serveur d'inférence Ollama », `qwen3:14b`, Bazzite, kargs | **legacy** — Idem : bandeau legacy. Le contenu technique BC-250 utile (kargs, UMA, 40 CU) est déjà re-tracé dans `DEBIAN13-KERNEL-MESA-STRATEGY.md` (T04). |
| `BACKLOG.md` | 6 | Journal v6 : « Cible = BC-250 sous Bazzite, modèles locaux FREE (Ollama) » | **legacy** — Journal historique daté (2026-08-26) mais **non marqué** et son énoncé de cible contredit v1.4. Action : bandeau « journal historique v6, remplacé par docs/project/CHANGELOG.md ». |
| `fait.md` | 4 | Rapport de correction v5.4 (27/07/2026) : system prompt Ollama, etc. | **legacy** — Rapport historique antérieur à v1.4, non marqué. Action : bandeau legacy (le contenu utile est déjà migré dans `docs/project/`). |

## 6. Occurrences correctes (keep) — patrimoine ou documentation du remplacement

Aucune de ces occurrences ne prescrit Ollama comme cible v1.4.

| Fichier | Occurrences | Pourquoi c'est correct |
|----------|--------------|----------------------|
| `docs/architecture/adr/ADR-002-llama-cpp-vulkan.md` | l.3 (« Remplace : Ollama en conteneur, Qwen3-14B »), l.11 (contexte historique) | L'ADR **documente ce qu'elle remplace**. C'est le rôle d'une ADR. |
| `docs/architecture/adr/ADR-004-laya-okf.md` | l.27, 68 (signale que l'AGENTS.md du plugin prescrit Ollama et que ce n'est **pas** la cible) | Marque explicitement Ollama comme hors cible. |
| `docs/architecture/PROF-IA-v1.4-master.md` | l.21 (tableau « Ollama en conteneur → llama.cpp hors conteneur »), l.157 (« dans le legacy, Ollama/Qwen3/Bazzite n'apparaissent que comme la genèse ») | Source de vérité : documente la transition. |
| `knowledge/AGENTS.md` | l.61 (« patrimoine mais n'est pas la cible : il prescrit Ollama et Qwen3-14B ») | Identifie correctement le legacy. |
| `docs/project/G1.1-SPEC.md` | 15 | La spec de ce chantier : décrit le problème audité. |
| `vault/AGENTS.md` | 10 (dont l.2 : « Il prescrit Ollama et qwen3:14b : c'est **caduc** ») | Patrimoine du vault, **déjà marqué caduc** en tête de fichier. |
| `vault/docs/superpowers/audit/2026-08-26-audit-consolidated.md` | 5 | Historique daté (2026-08-26). |
| `vault/docs/superpowers/specs/2026-08-26-backend-audit-remediation.md` | 8 | Historique daté. |
| `vault/docs/superpowers/specs/2026-08-26-bc250-bazzite-deployment.md` | 8 | Historique daté. |
| `vault/log.md` | 4 | Journal historique du vault. |

## 7. Vérification d'exhaustivité

- Recherche principale : `grep -rin "ollama"` hors `docs/legacy/`, `.git/`,
  `node_modules/`, `.venv/`, `__pycache__/`, `.scratch/` → **35 fichiers**, tous
  classés aux §4–§6.
- Recherche indirecte : ports `11434`/`11436` → ne révèle **aucun fichier
  supplémentaire** (toutes les occurrences vivent dans des fichiers déjà classés).
- Fichiers à zéro occurrence vérifiés au passage : `README.md`, `AGENTS.md`,
  `deploy/systemd/profia-llama.service`, `scripts/benchmark/fit_campaign.sh`,
  `scripts/benchmark/run_matrix.sh`, `.github/workflows/ci.yml`, Dockerfiles —
  la couche v1.4 (normes, instrumentation, CI) est déjà propre.

## 8. Conséquences pour les tickets suivants

1. **La migration applicative Ollama → llama.cpp est un chantier à part entière**
   (20 fichiers `migrate`), au-delà de G1.1. Le protocole `LLMClient` existe déjà :
   c'est une nouvelle implémentation + un recâblage, pas une refonte. À spécifier
   dans un chantier dédié post-G1.1 (avec `improve-codebase-architecture` si le
   recâblage révèle une refonte nécessaire).
2. **T03 (INSTALLATION.md)** doit intégrer : la section « références Ollama »
   (cet audit), le remplacement des guides v6 racine, et ne documenter que la
   chaîne llama.cpp comme chemin d'installation.
3. **T05 (incohérence architecturale)** exécute les actions documentaires de cet
   audit : bandeaux legacy sur les 5 fichiers racine, reformulation des
   commentaires (nginx, setup.sh), et constate que le dépôt ne raconte plus
   qu'une histoire **au niveau documentaire** — le code, lui, migre au chantier
   suivant.
4. **Critère de sortie T05, formulation stricte** : ADR-003/architecture ne peut
   être déclaré cohérent que lorsque la documentation/configuration active ne
   présente plus Ollama et llama.cpp **simultanément comme backend cible**. Après
   T05, Ollama ne doit plus apparaître que comme : remplacé (ADRs, master),
   patrimoine daté (vault, legacy marqués) ou audit (ce document).

## 9. Règles respectées

- Aucune modification de code (audit uniquement).
- Aucune modification système.
- Aucun push.
- Aucune occurrence active classée `keep` pour « faire passer le ticket » :
  chaque `keep` est justifié (remplacé/patrimoine daté/marqué caduc).
