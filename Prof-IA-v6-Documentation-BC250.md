# Prof IA v6 — Documentation Technique Bazzite-First

**Cible** : AMD BC-250 (Cyan Skillfish / RDNA2 / gfx1013) · Bazzite (Fedora immuable, rpm-ostree)
**Modèle LLM** : `qwen3:14b` (Q4_K_M, ~9.3 Go) — 100 % VRAM, 0 offload
**Embeddings** : `BAAI/bge-m3` (1024 dims) · ROCm 7.2 ou repli CPU auto
**Vault LLM Wiki** : Modèle 3 (OKF + Karpathy Wiki) · executor-agnostic (Obsidian plugin / OpenCode)

---

## 1. Stack Matérielle & Système — BC-250 sur Bazzite

| Composant | Spécification v6 | Note |
|-----------|------------------|------|
| **APU** | AMD BC-250 — Cyan Skillfish (gfx1013) | RDNA2, 24→40 CU déblocables |
| **CPU** | 6 cœurs Zen 2 @ 3.0 GHz (base) → 8c/16t après unlock SMU | Persistant via systemd `bc250-core-unlock.service` |
| **GPU** | 24 CU stock → **40 CU** via UMR (`bc250-cu-live-manager.sh`) | Pas de rebuild noyau, "on the fly" |
| **VRAM** | 16 Go GDDR6 unifiée | Split serveur 12 Go GPU / 4 Go CPU |
| **OS** | **Bazzite** (Fedora 41+ immutable, rpm-ostree) | First-class, pas de Debian |
| **Kernel** | Fedora kernel (6.10+) + kargs rpm-ostree | `amdgpu.gttsize=14750 ttm.pages_limit=3014656 ttm.page_pool_size=3014656` |
| **Pilotes** | Mesa 25+ / RADV Vulkan / ROCm 7.2 (overlay COPR) | ROCm pour embeddings, Vulkan pour Ollama |
| **Containerisation** | Podman/Docker + Compose v2 | SELinux-friendly sur Bazzite |

### 1.1 Budget VRAM — Split Serveur (12 Go GPU / 4 Go CPU)

Le BC-250 partage 16 Go GDDR6 entre CPU et GPU. La configuration validée :

```
# rpm-ostree kargs (persistant, reboot requis)
amdgpu.gttsize=14750 ttm.pages_limit=3014656 ttm.page_pool_size=3014656

# UMA_SIZE CMOS (bc250memcfg)
UMA_SIZE=512  # 512 Mo réservés CPU / firmware

# Config appli (backend/api/config.py)
AMD_GTT_SIZE_MB=12288   # 12 Go budget logique appli
AMD_RDNA2_CUS=24        # 24 stock, 40 si déblocage validé (dmesg active_cu_number=40)
```

> **Pourquoi 3014656 pages ?** ~12 Go GTT (3014656 × 4 KiB ≈ 12 GiB). Le triplet kargs DOIT être posé ensemble — `gttsize` seul ne suffit pas, le plafond `ttm` par défaut est atteint avant et fait planter le driver.

### 1.2 Variables d'environnement critiques (backend uniquement)

| Variable | Valeur | Rôle |
|----------|--------|------|
| `HSA_OVERRIDE_GFX_VERSION` | `10.1.3` | Force reconnaissance gfx1013 par ROCm (embeddings) |
| `ROCR_VISIBLE_DEVICES` | `0` | Cible le BC-250 unique |
| `PYTORCH_HIP_ALLOC_CONF` | `max_split_size_mb:512` | Limite fragmentation GDDR6 |
| `OLLAMA_NUM_PARALLEL` | `1` | Évite saturation VRAM (1 requête LLM à la fois) |
| `OLLAMA_NUM_GPU` | `99` | Convention Ollama = "toutes les layers sur GPU" (pas nb CUs) |
| `AUTO_EVALUATE` | `false` | Auto-éval Judge+Devil's Advocate (opt-in après calibration) |

> **Important** : ces variables ne s'appliquent QU'au service `backend` (embeddings ROCm). Le service `ollama` tourne en Vulkan/RADV — ni ROCm, ni `HSA_OVERRIDE_GFX_VERSION`.

---

## 2. Architecture Modèle 3 — RAG + LLM Wiki (OKF)

```
┌─────────────────────────────────────────────────────────────────────┐
│                      LAYER A — Prof-IA RAG                          │
│  ┌─────────┐   ┌─────────┐   ┌──────────┐   ┌──────────────────┐   │
│  │ React   │──▶│ Nginx   │──▶│ FastAPI  │◀──│ PostgreSQL+pgvector│   │
│  │ :3000   │   │ :8080   │   │ :8001    │   │ :5432 (HNSW)     │   │
│  └─────────┘   └─────────┘   └────┬─────┘   └──────────────────┘   │
│                                   │                                  │
│                    ┌──────────────┴──────────────┐                  │
│                    │       Ollama :11434         │                  │
│                    │  qwen3:14b (Vulkan/RADV)    │                  │
│                    └──────────────┬──────────────┘                  │
│                                   │                                  │
│                    ┌──────────────┴──────────────┐                  │
│                    │    Auto-Eval (seq.)         │                  │
│                    │  Judge + Devil's Advocate   │                  │
│                    └──────────────┬──────────────┘                  │
└───────────────────────────────────│─────────────────────────────────┘
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────┐
│                      LAYER B — LLM Wiki Vault                       │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐     │
│  │ vault/raw/  │───▶│ Ingest      │───▶│ vault/wiki/         │     │
│  │ (sources)   │    │ (Karpathy   │    │ index/sources/      │     │
│  └─────────────┘    │  Wiki /     │    │ entities/concepts/  │     │
│                     │  OpenCode)  │    │ (Markdown + OKF FM) │     │
│                     └──────┬──────┘    └─────────────────────┘     │
│                            │                                        │
│                     ┌──────┴──────┐                                 │
│                     │ Query +     │                                 │
│                     │ Lint (PPR)  │                                 │
│                     └─────────────┘                                 │
└─────────────────────────────────────────────────────────────────────┘
```

**Modèle 3 = RAG indexe aussi `vault/wiki/**` + `vault/raw/**`**  
Chaque note Wiki = Markdown + front-matter OKF (`type`, `title`, `statut`, `sources`, `[[wiki-links]]`).

---

## 3. Services Docker Compose (Stack v6)

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg18
    environment:
      POSTGRES_DB: prof_ia_v5
      POSTGRES_USER: user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}  # requis, pas de défaut
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck: pg_isready -U user -d prof_ia_v5

  ollama:
    image: ollama/ollama:latest
    # Vulkan/RADV auto (pas ROCm) — device GPU via --gpus all
    environment:
      - OLLAMA_NUM_PARALLEL=1
      - OLLAMA_NUM_GPU=99
    volumes:
      - ollama:/root/.ollama
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia  # ou amd pour RADV
              count: 1
              capabilities: [gpu]

  backend:
    build: ./backend
    environment:
      - DATABASE_URL=postgresql://user:${POSTGRES_PASSWORD}@postgres:5432/prof_ia_v5
      - API_TOKEN=${API_TOKEN}
      - OLLAMA_HOST=http://ollama:11434
      - AUTO_EVALUATE=false
      - HSA_OVERRIDE_GFX_VERSION=10.1.3
      - ROCR_VISIBLE_DEVICES=0
      - PYTORCH_HIP_ALLOC_CONF=max_split_size_mb:512
    depends_on:
      postgres: { condition: service_healthy }
      ollama: { condition: service_started }

  frontend:
    build: ./frontend
    environment:
      - REACT_APP_API_URL=http://localhost:8080/api
    depends_on: [backend]

  nginx:
    image: nginx:alpine
    ports: ["8080:80"]
    volumes:
      - ./config/nginx.conf:/etc/nginx/nginx.conf:ro
    depends_on: [frontend, backend]
```

**Secrets obligatoires** (`.env` à la racine) :
```
POSTGRES_PASSWORD=<token-urlsafe-24>
API_TOKEN=<token-urlsafe-32>
```

---

## 4. Déblocage 40 CU — UMR "Live Manager" (Bazzite, sans rebuild noyau)

Le BC-250 sort avec 24/40 CU actives. Le déblocage communautaire (**WinnieLV / bc250-cu-live-manager**) écrit les registres matériels via UMR au runtime — **aucun module noyau hors-arbre, aucun rebuild, réversible à chaud**.

| Registre | Stock (24 CU) | Débloqué (40 CU) |
|----------|---------------|------------------|
| `CC_GC_SHADER_ARRAY_CONFIG` | `0xfff80000` | `0xffe00000` |
| `SPI_PG_ENABLE_STATIC_WGP_MASK` | `0x07` | `0x1F` |

**Gain mesuré** (`llama-bench pp512`, 1500 MHz) : **230 → 371 tok/s (1.61×)**, +30 W, +4°C.  
> Gain **compute** (inférence/embeddings), pas gaming (fill-rate bound).

### Scripts Bazzite (dans `scripts/bc250/`)

| Script | Rôle | Exécution |
|--------|------|-----------|
| `40cu-unlock/bc250-cu-live-manager.sh` | Déblocage 40 CU via UMR (détecte pattern harvest, health-check WGP) | `sudo ./bc250-cu-live-manager.sh` |
| `core-unlock/bc250-unlock-cores.py` | Unlock 8c/16t via SMU (registre PPTABLE) | `sudo python3 bc250-unlock-cores.py` |
| `smu-oc/bc250_apply.py` | UV/OC SMU (courbes tension/fréquence) | `sudo python3 bc250_apply.py --profile balanced` |
| `mem-oc/mem_oc.sh` | OC mémoire GDDR6 (optionnel, avancé) | `sudo ./mem_oc.sh` |
| `apply_phase1.sh` | Orchestrateur Phase 1 (split RAM/VRAM + services systemd) | `sudo ./apply_phase1.sh` |
| `validate.sh` | Validation post-setup (VRAM, CUs, cores, santé WGP) | `sudo ./validate.sh` |

**Services systemd créés** (persistants via `apply_phase1.sh`) :
- `bc250-40cu.service` — live-manager au boot
- `bc250-core-unlock.service` — 8c unlock
- `bc250-smu-oc.service` — UV/OC
- `bc250-health-check.timer` — surveillance quotidienne

---

## 5. ROCm (Embeddings) vs Vulkan (LLM) — Deux Backends GPU

| Composant | Backend | Rationale |
|-----------|---------|-----------|
| **Embeddings** (`rag_engine.py` · `SentenceTransformer` · PyTorch) | **ROCm 7.2** si dispo, sinon **repli CPU auto** | Pas d'alternative Vulkan mûre pour PyTorch ; batch embeddings tolère CPU |
| **LLM Ollama** (`qwen3:14b`) | **Vulkan (RADV)** | ROCm instable sur gfx1013 pour inférence LLM ; Ollama bascule auto sur Vulkan |

**Vérification Ollama backend** :
```bash
docker compose logs ollama | grep -i "vulkan\|rocm\|gfx1013"
# doit afficher : library=Vulkan ... description="AMD BC-250 (RADV GFX1013)"
```

---

## 6. Pipeline RAG — Modèles & Modes

| Élément | Choix v6 | Justification |
|---------|----------|---------------|
| **Embeddings** | `BAAI/bge-m3` (1024d) | Meilleur local FR (MTEB 2026), multilingue, dense+sparse+colbert |
| **LLM principal** | `qwen3:14b` Q4_K_M (~9.3 Go) | Tient entièrement dans 12 Go VRAM, 0 offload, reasoning fort |
| **Context window** | `num_ctx=8192` (RAG profond) / `1024` (vault quick) | Pin via Modelfile si besoin |
| **RAG modes** | `precise` (top-5), `explore` (MMR top-12), `synthesis` (multi-query top-20) | Selon besoin précision/couverture |
| **Chunking** | `langchain-text-splitters` (recursive, 512/100 overlap) | Défaut robuste |
| **Vector store** | pgvector + HNSW (`ivfflat` fallback) | `CREATE INDEX ... USING hnsw (embedding vector_cosine_ops)` |

**Formats supportés** : PDF, DOCX, PPTX, XLSX, TXT, MD, CSV, audio/vidéo (Whisper `base` fp16 ROCm).

---

## 7. Auto-Évaluation — Judge + Devil's Advocate (Séquentiel)

Après chaque réponse `/chat` (si `AUTO_EVALUATE=true`), exécution **séquentielle** sur le **même** `qwen3:14b` chargé :

1. **Judge** — JSON : `faithfulness` (0–1), `relevance` (0–1), `verdict` (`good`/`needs_improvement`/`bad`)
2. **Devil's Advocate** — JSON : liste `claims` non sourcées dans le contexte récupéré

**Persistance** : `response_evaluations` (UPSERT idempotent clé `evaluation_run_id`) + `response_issues` (UNIQUE `conversation_id`+`run_id`+`issue_type`+`claim_hash`).

**Paramètres qualité** :
```
EVAL_TIMEOUT_S=15
EVAL_NUM_PREDICT=150
EVAL_NUM_CTX=2048
EVAL_SAMPLE_RATE=1.0   # tout est scoré, latence acceptée
```

**Activation production** = commit isolé + tag `v6.1-auto-eval` **après** calibration sur 20 échantillons golden (Pearson r ≥ 0.7 Judge vs humain).

---

## 8. Fine-Tuning LoRA — Golden Dataset Interne

Pas de dataset externe figé. Le corpus d'entraînement se construit **automatiquement** à partir des conversations réelles :

```
Conversation (/chat) → Auto-Éval (score ≥ 0.85) → is_golden=true
      ↓
Formateur valide (note ≥ 4/5 optionnel)
      ↓
Export SFT Alpaca (Instruction / Input RAG / Réponse idéale) → JSONL
      ↓
LoRA fp16 r=16 α=32 target_modules=q_proj,v_proj grad_accum=8 batch=1 seq=2048
      ↓
Conversion GGUF → ollama create prof-ia-tssr -f Modelfile
```

**Arrêt Ollama requis** avant fine-tuning (libère ~4.5 Go VRAM) — `train.py` le vérifie.

---

## 9. Monitoring & Opérabilité

| Outil | Cible | Métriques clés |
|-------|-------|----------------|
| **Prometheus** | `/metrics` (backend) + `/nginx_status` | Latence RAG p50/p95, tokens/s, GPU usage, queue depth |
| **Logs** | Loguru JSON → `/app/data/logs` | Corrélation `X-Request-ID` Nginx ↔ FastAPI |
| **Health** | `GET /health` | PostgreSQL, Ollama, pgvector, disk, VRAM |
| **VRAM** | `rocm-smi` / `/sys/class/drm/card0/device/mem_info_vram_used` | Alerting si > 11.5 Go (marge 0.5 Go) |

---

## 10. Sécurité — Modèle de Menace Local (LAN / Air-Gapped)

- **Aucune télémétrie, aucune API externe, aucun modèle cloud**
- **CORS** : `CORS_ORIGINS=localhost` par défaut (configurable via `.env`)
- **Auth API** : Bearer token obligatoire (`API_TOKEN` dans `.env`, validé au startup)
- **Comparaison token** : `secrets.compare_digest` (temps constant)
- **Injection SQL** : asyncpg paramétré (`$1,$2…`) partout
- **Rate limiting Nginx** : 30 req/min par IP sur `/api/*`
- **Headers sécurité** : CSP, X-Frame-Options, X-Content-Type-Options, Referrer-Policy, Permissions-Policy
- **Network Docker** : `prof-ia-network` bridge ; seul Nginx exposé LAN (8080) ; PostgreSQL/Ollama loopback uniquement

---

## 11. Déploiement — Procédure Bazzite (First-Class)

```bash
# 1. Bazzite installé (rpm-ostree), Secure Boot désactivé
# 2. kargs VRAM (persistant, reboot)
rpm-ostree kargs --append-if-missing="amdgpu.gttsize=14750 ttm.pages_limit=3014656 ttm.page_pool_size=3014656"
# 3. UMA_SIZE CMOS (bc250memcfg) → 512
# 4. Reboot
# 5. Setup Bazzite (rpm-ostree kargs, governor COPR, env ROCm, services systemd)
sudo ./scripts/bazzite/setup.sh
# 6. Optimisations userspace BC-250 (40 CU UMR, 8c SMU, UV/OC)
sudo ./scripts/bc250/apply_phase1.sh
sudo ./scripts/bc250/validate.sh
# 7. Secrets
cp .env.example .env
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24))" >> .env
python3 -c "import secrets; print('API_TOKEN=' + secrets.token_urlsafe(32))" >> .env
# 8. Modèle LLM
ollama pull qwen3:14b
# 9. Stack
docker compose up -d
# 10. Santé
curl http://localhost:8001/health
# UI → http://localhost:3000  (ou proxy http://localhost:8080)
```

**Rollback** : `git revert <commit> && docker compose up -d` (images versionnées).

---

## 12. Références & Crédits Communautaires BC-250

| Auteur / Projet | Contribution | Licence |
|-----------------|--------------|---------|
| **WinnieLV** | `bc250-cu-live-manager` — 40 CU via UMR | MIT |
| **bc250-collective** | `bc250_smu_oc` — CPU UV/OC via SMU | MIT |
| **keyboardspecialist** | `bc250-steamos` — 8-core unlock + RAM/VRAM split | MIT |
| **rpf16rj** | `bc250-steamos-real-toolkit` — SMU toolkit reference | MIT |
| **MastaG** | `linux-cachyos-bc250` — kernel patches (Phase 2 opt-in) | GPL-2.0 |
| **elektricm** | amd-bc250-docs — documentation communautaire centrale | CC-BY-SA |
| **akandr** | `bc250` — Ollama + Vulkan server guide | MIT |
| **chelmooz** | `AMD-BC-250-at-his-Best` — bc250-beast toolkit (vendored) | MIT |

Voir [`CREDITS.md`](CREDITS.md) pour la table complète.

---

## 13. Sécurité Matérielle — Garde-Fous Non Négociables

| Paramètre | Limite dure | Risque si dépassé |
|-----------|-------------|-------------------|
| **CPU VID** | ≤ **1300 mV** | Brick confirmé (défaut SIL irreversibile) |
| **GPU Clock** | ≤ 2.2–2.4 GHz (air) | Throttle 89–107°C → instabilité |
| **GPU Clock** | ≤ 2.6–2.8 GHz (water + power mod) | Uniquement avec watercooling + alimentation renforcée |
| **VRAM Used** | < 11.5 Go / 12 Go budget | OOM driver → crash backend |
| **Secure Boot** | **Désactivé** ou module signé | Module amdgpu non chargé |

**Toujours** stress-test les CUs/cœurs débloqués (`validate.sh`, `bc250-cu-health-test.sh`) avant de dépendre de la config en production.

---

*Document généré le 27 Août 2026 — Prof IA v6.0 pour AMD BC-250 (Cyan Skillfish / RDNA2) sur Bazzite (Fedora immuable, rpm-ostree).  
Stack : Bazzite · Kernel Fedora 6.10+ · Mesa 25+ · ROCm 7.2 · PyTorch 2.5+ · PostgreSQL 18 + pgvector 0.8 · qwen3:14b · BGE-M3.*