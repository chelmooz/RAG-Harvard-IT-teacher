# PROF IA v1.4 — Guide d'installation Debian 13 → BC-250

**Statut :** à valider par XZ · **Date :** 2026-10-06 · **Gate :** G1.1 (T03)
**Source de vérité :** `docs/architecture/PROF-IA-v1.4-master.md` · ADR-001 à ADR-004

> **⚠️ Conventions de statut** — Chaque étape porte un badge explicite :
>
> | Badge | Signification |
> |-------|---------------|
> | `VALIDÉ DEV` | Testé/validé sur la machine de développement actuelle |
> | `REQUIS CIBLE` | Exigence pour le BC-250, non validée sur la machine de dev |
> | `À VALIDER BC-250` | Doit être confirmé sur la cible physique BC-250 |
> | `NON VALIDÉ` | Non testé, hypothétique ou en attente de décision |
>
> **Aucune formulation du type "installation validée" n'est autorisée** sans la preuve sur la cible BC-250.

---

## 0. Contexte et architecture cible

Ce guide décrit l'installation de **PROF IA v1.4** sur **Debian 13 (trixie)** pour le matériel **BC-250 (AMD Cyan Skillfish / RDNA2 / gfx1013, 16 Go GDDR6 unifiée)**.

### Architecture v1.4 (normative)

| Composant | Choix | Référence |
|-----------|-------|-----------|
| **OS** | Debian 13 (trixie) | ADR-001 |
| **Moteur LLM** | `llama.cpp` Vulkan/RADV, **hors conteneur**, service systemd `profia-llama` | ADR-002 |
| **Réseau** | Réseau Docker dédié `profia-llama` (172.30.50.0/24), gateway `172.30.50.1`, `llama-host` via `extra_hosts` explicite | ADR-003 |
| **Modèle** | `Qwen2.5-7B-Instruct-Q6_K.gguf` (6,25 Go, SHA256 `489138dfed4f04cd6dea56e5a8423e4aa05a0318cce2a4a72250fe1278e97cf8`) | ADR-002 §4 |
| **Base de données** | PostgreSQL 18 + pgvector (conteneur `postgres`) | `docker-compose.yml` |
| **Embeddings / Reranker** | BGE-M3 (CPU, 1024 dims) | ADR-002 |
| **Réseau Docker** | `profia-llama` bridge, subnet `172.30.50.0/24`, gateway `172.30.50.1` | ADR-003 |
| **Endpoint LLM** | `LLAMA_SERVER_URL=http://llama-host:8081` (backend → `llama-host:8081` via `extra_hosts`) | ADR-003, T01 |
| **Pas d'Ollama** | **Remplacé par `llama.cpp`** — voir audit Ollama (T02) | OLLAMA-AUDIT.md |

> **⚠️ Incohérence architecturale résolue (T01/T05) :** Le dépôt contenait deux architectures simultanées (Ollama en conteneur actif dans `docker-compose.yml` + `llama.cpp` hôte dans ADR/systemd). **Le réseau est résolu (T01), la migration applicative Ollama→llama.cpp reste à faire (20 références `migrate` identifiées — OLLAMA-AUDIT.md).** Ce guide documente **uniquement** la cible `llama.cpp` hôte.

---

## Phase 1 — Prérequis système (machine cible BC-250)

| Composant | Exigence cible | Statut | Validation |
|-----------|----------------|--------|------------|
| **OS** | Debian 13 (trixie) minimal, à jour | `REQUIS CIBLE` | `cat /etc/os-release` |
| **Kernel** | **6.18 LTS** (éviter 6.15.0–6.15.6, 6.17.8–6.17.10) | `REQUIS CIBLE` | `uname -r` → 6.18.x ; boot sans écran noir |
| **Mesa / RADV** | **≥ 25.1** (Mesa 25.2.6+ recommandé via backports) | `REQUIS CIBLE` | `glxinfo \| grep Mesa` ≥ 25.1 ; `vulkaninfo` device RADV gfx1013 |
| **Vulkan ICD** | `radeon_icd.x86_64.json` (forcé via `VK_ICD_FILENAMES`) | `REQUIS CIBLE` | `VK_ICD_FILENAMES=... llava.cpp -lv 5` charge sans erreur |
| **40 CU unlock** | **Actif** (UMR runtime `bc250-cu-live-manager.sh` → `dmesg \| grep active_cu_number=40`) | `REQUIS CIBLE` | `dmesg \| grep active_cu_number=40` |
| **Split mémoire** | `UMA_SIZE=512 MiB` (CMOS `bc250memcfg`) + `ttm.pages_limit=3014656` (karg rpm-ostree) → split 12 Go GPU / 4 Go CPU | `REQUIS CIBLE` | `bc250memcfg` affiche 512 ; `cat /proc/cmdline` contient kargs ; `bc250-game-mode status` valide split 12/4 Go |
| **RAM/VRAM unifiée** | 16 Go GDDR6 unifiée (Cyan Skillfish / RDNA2 / gfx1013) | `REQUIS CIBLE` | `free -h` + `amdgpu.vram` cohérents ; `lspci -nn \| grep -i amd` → `1002:13fe` |
| **Utilisateur `llama`** | Existe, groupe `render`, `StateDirectory=profia-llama` | `REQUIS CIBLE` | `id llama` ; `getent group render` |

> **Source :** `docs/architecture/DEBIAN13-KERNEL-MESA-STRATEGY.md` (T04) — chaque valeur tracée à sa source (guide install BC-250, doc v6, audit B1, mesure dev/backports). **Aucune modification kernel/Mesa sur la machine de dev** (règle XZ).

---

## Phase 2 — Installation logicielle (sur la cible BC-250)

### 2.1 Docker & Docker Compose
```bash
# `VALIDÉ DEV` sur machine de dev (Docker 27.x, compose v2)
# `REQUIS CIBLE` sur BC-250
apt-get update && apt-get install -y docker.io docker-compose-plugin
systemctl enable --now docker
docker network create --driver bridge --subnet 172.30.50.0/24 --gateway 172.30.50.1 profia-llama
```
**Statut :** `REQUIS CIBLE` — à exécuter sur BC-250.

### 2.2 llama.cpp — build Vulkan (hôte, hors conteneur)
```bash
# `VALIDÉ DEV` (binaire testé sur machine de dev, commit f0c41e0)
# `REQUIS CIBLE` — build sur BC-250 (même commande)
cd /opt
git clone https://github.com/ggml-org/llama.cpp
cd llama.cpp
cmake -B build -DGGML_VULKAN=ON -DLLAMA_CURL=ON -DCMAKE_BUILD_TYPE=Release
cmake --build build --config Release -j$(nproc)
# Binaire : /opt/llama.cpp/build/bin/llama-server
```
**Statut :** `REQUIS CIBLE` — build sur BC-250 (même hardware, même kernel/Mesa). Ne pas copier le binaire de dev (kernel/Mesa différents).

### 2.3 Service systemd `profia-llama`
```bash
# Fichier : /etc/systemd/system/profia-llama.service
# (copier depuis deploy/systemd/profia-llama.service du dépôt)
# Vérifier : LLAMA_HOST_IP=172.30.50.1, MODEL_DIR=/var/lib/profia-llama/models, MODEL_FILE=Qwen2.5-7B-Instruct-Q6_K.gguf
systemctl daemon-reload
systemctl enable --now profia-llama
```
**Statut :** `REQUIS CIBLE` — service systemd sur BC-250, user `llama`, groupe `render`, `WorkingDirectory=/opt/llama.cpp/build/bin`.

### 2.4 Modèle Qwen2.5-7B-Instruct-Q6_K.gguf
```bash
# `VALIDÉ DEV` (téléchargé, SHA256 vérifié, campagne réelle GREEN)
# `REQUIS CIBLE` — même fichier, même SHA256
mkdir -p /var/lib/profia-llama/models
cd /var/lib/profia-llama/models
wget -O Qwen2.5-7B-Instruct-Q6_K.gguf \
  "https://huggingface.co/bartowski/Qwen2.5-7B-Instruct-GGUF/resolve/main/Qwen2.5-7B-Instruct-Q6_K.gguf"
sha256sum Qwen2.5-7B-Instruct-Q6_K.gguf
# Doit afficher : 489138dfed4f04cd6dea56e5a8423e4aa05a0318cce2a4a72250fe1278e97cf8
```
**Statut :** `REQUIS CIBLE` — même modèle, même SHA256, même taille (6 254 199 488 octets).

### 2.5 Réseau Docker dédié
```bash
# `VALIDÉ DEV` (réseau créé, gateway vérifiée)
# `REQUIS CIBLE`
docker network create --driver bridge \
  --subnet 172.30.50.0/24 --gateway 172.30.50.1 profia-llama
ip -4 addr show | grep -q "172.30.50.1/24" || { echo "Gateway absente"; exit 1; }
```
**Statut :** `REQUIS CIBLE` — réseau `profia-llama` doit exister avant démarrage systemd (vérifié par `ExecStartPre`).

### 2.6 Docker Compose (backend, postgres, frontend, nginx)
```bash
# `VALIDÉ DEV` (compose v6 testé, sans service ollama)
# `REQUIS CIBLE` — même compose, même .env
cd /opt/prof-ia-v1.4
cp .env.example .env
# Éditer .env : POSTGRES_PASSWORD, API_TOKEN, OLLAMA_MODEL (inchangé pour embeddings), LLAMA_SERVER_URL=http://llama-host:8081
docker compose up -d --build
```
**Statut :** `REQUIS CIBLE` — compose sans service `ollama`, backend avec `extra_hosts: llama-host:172.30.50.1` et `LLAMA_SERVER_URL=http://llama-host:8081` (T01 appliqué).

> **Note :** Le service `ollama` est **supprimé** du compose v1.4 (migration Ollama→llama.cpp en cours, 20 refs `migrate` — OLLAMA-AUDIT.md). Le backend utilise `LLAMA_SERVER_URL=http://llama-host:8081` (endpoint llama.cpp hôte via ADR-003).

---

## Phase 3 — Configuration (fichier `.env`)

Copier `.env.example` → `.env` et définir **uniquement** les variables obligatoires :

```bash
# Base de données (obligatoire)
POSTGRES_PASSWORD=<généré_sécurisé_32+_chars>

# Authentification API (obligatoire, identique côté frontend)
API_TOKEN=<token_urlsafe_32+_chars>
API_TOKEN_SOURCE=<source_aléatoire_32+_chars>

# LLM llama.cpp hôte (endpoint canonique — ADR-003)
LLAMA_SERVER_URL=http://llama-host:8081

# Embeddings (inchangé : BGE-M3 sur CPU/ROCm)
# EMBEDDING_MODEL=BAAI/bge-m3
# EMBEDDING_BATCH_SIZE=64

# CORS (origines frontend connues)
CORS_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

# Modèle Ollama (legacy, pour embeddings uniquement — migration séparée)
# OLLAMA_MODEL=qwen3:14b
```

| Variable | Statut | Note |
|----------|--------|------|
| `LLAMA_SERVER_URL` | `REQUIS CIBLE` | Endpoint canonique llama.cpp (T01) |
| `POSTGRES_PASSWORD` | `REQUIS CIBLE` | Générer `openssl rand -base64 32` |
| `API_TOKEN` / `API_TOKEN_SOURCE` | `REQUIS CIBLE` | Identiques frontend/backend (`openssl rand -url-safe 32`) |
| `OLLAMA_HOST` / `OLLAMA_MODEL` | `NON VALIDÉ` | **Legacy** — pour embeddings uniquement, migration séparée |

---

## Phase 4 — Validation post-installation (campagne de preuve)

### 4.1 Health checks (services Docker)
```bash
# Tous les services UP
docker compose ps
# → postgres: healthy, backend: healthy, frontend: healthy, nginx: healthy
```

### 4.2 Connectivité hôte ↔ conteneur (ADR-003)
```bash
# Depuis le conteneur backend → llama-host:8081
docker exec prof-ia-backend curl -sf http://llama-host:8081/health
# → {"status":"ok",...}

# Résolution DNS explicite (T01)
getent hosts llama-host
# → 172.30.50.1  llama-host
```

### 4.3 Service llama.cpp hôte
```bash
systemctl status profia-llama
# → active (running)

curl -sf http://172.30.50.1:8081/health
# → {"status":"ok",...}
```

### 4.4 Campagne T0.-1 réduite (instrumentation validée G1)
```bash
# Sur la cible BC-250 (si matériel disponible) ou machine de dev (preuve pré-déploiement)
cd /opt/prof-ia-v1.4/scripts/benchmark
FIT_LLAMA_BIN=/opt/llama.cpp/build/bin/llama-server \
FIT_MODEL_PATH=/var/lib/profia-llama/models/Qwen2.5-7B-Instruct-Q6_K.gguf \
FIT_LLAMA_SNAPSHOT=/tmp/load.log \
bash fit_campaign.sh \
  --label install_validation --ctx 4096 --kv q8_0 --ngl 999 --requests 2 \
  --port 18888
```
**Critères de succès (GREEN) :**
- `verdict: "GREEN"`
- `gpu_layers: 29` (ou `null` si CPU only, mais `ngl=999` doit offloader sur RADV)
- `offload_backend: "GPU"`
- `device_buffer_mib` ≈ 5532, `host_buffer_mib` ≈ 426, `model_buffer_mib` ≈ 5958
- `model_sha256: "489138dfed4f04cd6dea56e5a8423e4aa05a0318cce2a4a72250fe1278e97cf8"`

> **Statut :** `À VALIDER BC-250` — cette campagne est la **preuve pré-déploiement**. Elle ne garantit pas la viabilité thermique/mémoire sous charge prolongée (gate G2+).

---

## Annexe A — Section Références Ollama (issue de T02)

> **Source :** `docs/project/OLLAMA-AUDIT.md` (audit T02, 35 fichiers classés)

| Catégorie | Fichiers | Action |
|-----------|----------|--------|
| **Migrate** (20) | Chemin d'exécution complet : `docker-compose.yml`, `config.py`, `dependencies.py`, `rag_engine.py`, `main.py`, `evaluation.py`, `schemas.py`, `nginx.conf`, `.env.example`, `Dashboard.js`, `Terminal.js`, `conftest.py`, `test_unit.py`, `test_evaluation.py`, `bc250-game-mode.sh`, `setup.sh`, `bc250/README.md`, `config.yaml`, `train.py`, `README.md` (experimental) | Migration Ollama → llama.cpp (protocole `LLMClient` déjà abstrait) |
| **Legacy** (5) | `BC-250-INSTALL-GUIDE.md`, `BC-250-INSTALL-GUIDE-EN.md`, `Prof-IA-v6-Documentation-BC250.md`, `BACKLOG.md`, `fait.md` | Bandeau legacy + renvoi vers `INSTALLATION.md` |
| **Keep** (10) | ADR-002, ADR-004, `PROF-IA-v1.4-master.md`, `knowledge/AGENTS.md`, `vault/AGENTS.md` (bandeau caduc), `vault/docs/superpowers/*`, `vault/log.md`, `G1.1-SPEC.md` | Patrimoine/historique déjà marqué ou documentant le remplacement |

> **Action post-installation (T05) :** Marquer les 5 fichiers `legacy` avec bandeau, retirer/migrer les 20 `migrate`, valider que le dépôt ne raconte plus deux architectures.

---

## Annexe B — Dépannage courant

| Symptôme | Cause probable | Action |
|----------|----------------|--------|
| `llama-host` ne résout pas | Réseau `profia-llama` absent ou `extra_hosts` manquant | `docker network inspect profia-llama` ; `extra_hosts` dans compose |
| `llama-server` ne démarre pas | `VK_ICD_FILENAMES` absent, Vulkan ICD absent, kernel < 6.18 | Vérifier `VK_ICD_FILENAMES`, `vulkaninfo`, kernel 6.18+ |
| Modèle non trouvé | Chemin `MODEL_DIR/MODEL_FILE` incorrect | Vérifier `MODEL_DIR=/var/lib/profia-llama/models`, fichier présent |
| OOM / VRAM saturée | Split mémoire incorrect, 40 CU non unlock | `bc250memcfg UMA_SIZE 512`, karg `ttm.pages_limit=3014656`, UMR unlock 40 CU |
| Backend ne rejoint pas llama.cpp | `LLAMA_SERVER_URL` absent ou `extra_hosts` manquant | Vérifier `.env` + `docker-compose.yml` backend `extra_hosts` |

---

## Annexe C — Références

- `docs/architecture/PROF-IA-v1.4-master.md` — source de vérité unique
- `docs/architecture/adr/ADR-001` à `ADR-004`
- `docs/architecture/DEBIAN13-KERNEL-MESA-STRATEGY.md` (T04)
- `docs/project/OLLAMA-AUDIT.md` (T02)
- `docs/project/G1.1-SPEC.md` (spécification G1.1)
- `deploy/systemd/profia-llama.service` — service systemd officiel
- `docker-compose.yml` — compose v1.4 (sans Ollama, avec `extra_hosts` + `LLAMA_SERVER_URL`)
- `deploy/systemd/profia-llama.service` — `ExecStartPre` vérifie réseau + gateway + modèle
- `scripts/benchmark/fit_campaign.sh` — instrument G1 (T0.-1 promu, 116/116 tests verts)

---

**Fin du guide.** Ce document ne remplace pas la campagne de qualification sur BC-250 (gates G2+). Il documente **ce qui est requis, ce qui est validé sur dev, et ce qui reste à prouver sur la cible**.