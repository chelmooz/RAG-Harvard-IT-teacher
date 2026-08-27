# BC-250 Install Guide — Gaming Station + RAG Server (Bazzite)

**Easy**, copy-paste guide from power-on to service verification. For the technical "why", see `vault/docs/superpowers/specs/2026-08-26-bc250-bazzite-deployment.md`.

> OS chosen: **Bazzite** (Fedora immutable, `rpm-ostree`). Everything is **local / FREE**, no cloud. The BC-250 = AMD Cyan Skillfish / RDNA2 / **gfx1013** (PCI `1002:13fe`).

---

## 0. Prerequisites & Warnings

**Hardware**
- PSU **≥ 460 W** properly wired. The **8-pin PCIe** connector must be wired with correct polarity (12V vs GND) — reversal **destroys the card permanently**.
- **DisplayPort 1.4** cable (the BC-250 has **no HDMI** — use DP→HDMI adapter if needed).
- (Optional) **Bluetooth USB dongle** for audio (BlueZ/PipeWire native, no drivers).
- (Recommended for safety) **CH347 programmer** to backup/restore BIOS SPI.

**Risks (read before flashing)**
- ⚠️ **CPU Vid > 1325 mV = hardware brick.** We stay under 1300 mV (Mild profile).
- ⚠️ **Bad BIOS flash = bricked card.** The `bc250_memcfg` method (Step 2) avoids flashing for VRAM split. Flash is only useful for chipset menus / 8-core unlock via BIOS.
- ⚠️ **IOMMU must stay Disabled** (breaks display on BC-250).
- ⚠️ Avoid kernels **6.15.0–6.15.6** and **6.17.8–6.17.10** (broken display). Prefer 6.18 LTS or 6.17.11+.

---

## Step 1 — BIOS Flash (Optional)

> **Do this ONLY if** you want unlocked chipset menus or "clean" 8-core unlock.
> For VRAM split only, skip to Step 2 (method `bc250_memcfg`, no flash).

1. **Backup (CH347)** — read SPI chip with `flashrom -p ch347_spi -r backup_stock.bin`,
   then `diff backup_stock.bin backup_verify.bin` to confirm.
2. **Download** EFI flash kit + modded BIOS. Community references:
   - `BC250_3.00_CHIPSETMENU.ROM` (modded P3.00, VRAM + chipset, **recommended**) — sha256
     `48fbe5d366e6a56e2fdffdca848426216ba1f083610dab63db89d2f4e6c940b5`
   - `Robin5.00` (stock P5.00) — sha256
     `0d6f136cb120cf3b2de26d5c4d7f255604fdbf4b9442af5ba55419b95b89aa82`
3. **FAT32 USB key** (≤32 GB): put EFI kit + `.ROM` on it.
4. **Flash in EFI Shell** (BIOS → boot from USB):
   ```bash
   # from EFI Shell prompt, on key volume (fs0:)
   fs0:
   cd \<tools_folder>
   # flash modded BIOS (exact command depends on tool provided in EFI kit)
   <flash_tool> BC250_3.00_CHIPSETMENU.ROM
   ```
   ⚠️ If flash "hangs" mid-way → **do not reboot**, wait 15 min.
5. **Clear CMOS** (jumper 20s or remove battery) → reset to defaults, applies split.
6. Reboot, **Del** to enter BIOS → continue to Step 2.

---

## Step 2 — BIOS Settings (Do Even Without Flash)

Enter BIOS (**Del** at boot). Navigate **Chipset → GFX Configuration** and **Advanced → CPU Configuration**.

| Setting | Value | Why |
|---|---|---|
| Integrated Graphics Controller | **Forces** | Enables iGPU |
| UMA Mode | **UMA_SPECIFIED** | Allows manual VRAM split |
| **UMA Frame Buffer Size** | **512MB** (dynamic) | ⚠️ **Keep 512 MB**, do NOT switch to 4/12 GB preset (real ceiling is karg `ttm.pages_limit` set at Step 4) |
| IOMMU | **Disabled** | Mandatory (else black screen) |
| Boot Mode | **UEFI** | Standard |

> The real 12 GB GPU / 4 GB CPU split is enforced by OS (karg), not this menu. 512 MB = the
> *minimum* reserved; GPU grows dynamically up to the karg ceiling.

**If stock BIOS (not flashed)** and you want to change VRAM size from Linux without flashing:
```bash
git clone https://github.com/fanoush/bc250_memcfg && cd bc250_memcfg && make
sudo ./bc250memcfg UMA_SIZE 512      # 512 = 512 MB dynamic (recommended)
```

**F10** (Save & Exit).

---

## Step 3 — Install Bazzite

1. Download **Bazzite Desktop (AMD, Stable)** from bazzite.gg.
2. Flash USB key:
   ```bash
   # from a Linux machine; or Fedora Media Writer / balenaEtcher on Windows
   sudo dd if=bazzite.iso of=/dev/sdX bs=4M status=progress oflag=sync
   ```
3. Boot from key, run installer, install to disk (wipe recommended).
4. Reboot, create user account, open terminal.

---

## Step 4 — Drivers & Provisioning (Our Script)

The script `scripts/bazzite/setup.sh` configures **everything**: VRAM kargs, SMU governor, ROCm env vars,
dependencies (`umr`, `python3`), optimizations service install, JEU⇄RAG swapper, and monitoring.

```bash
# Get project repo (or copy scripts/ folder to machine)
git clone <project-repo> bc250-deploy && cd bc250-deploy
# or: copy scripts/ via USB key

cd scripts/bazzite
./setup.sh
```

> **Note**: the `.sh` scripts don't need manual `chmod +x` —
> `setup.sh` handles it automatically (`chmod +x` on `/opt/bc250/*.sh` and installs
> `bc250-game-mode` to `/usr/local/bin`). If you must run them outside `setup.sh`:
> ```bash
> chmod +x scripts/bc250/*.sh
> sudo cp scripts/bc250/bc250-game-mode.sh /usr/local/bin/bc250-game-mode
> sudo chmod +x /usr/local/bin/bc250-game-mode
> ```

The script does, in order:
1. `rpm-ostree kargs --append-if-missing="ttm.pages_limit=3014656"` → 12/4 GB split.
2. Install governor `cyan-skillfish-governor-smu` (COPR `filippor/bazzite`).
3. Export `HSA_OVERRIDE_GFX_VERSION=10.1.3` + `RADV_DEBUG=nohiz` (ROCm/Mesa).
4. Install `umr` + `python3` (dependencies for SMU/UMR scripts).
5. Copy `scripts/bc250/` → `/opt/bc250`, install + enable `bc250-optimizations.service`.
16. Install `bc250-game-mode` to `/usr/local/bin`.
17. Monitoring: `btop htop amdgpu_top mangohud` + `bc250-gpu-fix` (fix 655 % GPU util bug).

> **Reboot mandatory** after (kargs + rpm-ostree packages).

### If COPR Governor Missing
Script warns; install manually from `https://copr.fedorainfracloud.org/coprs/filippor/bazzite/`
or leave default (40 CU scripts work without governor, which mainly handles limits).

---

## Step 5 — Service Verification (Roles & Dependencies)

After reboot, verify each brick. **Roles** and **dependencies**:

| Service / Tool | Role | Depends On | Verification |
|---|---|---|---|
| `bc250-optimizations.service` | Orchestrates 40 CU + 8 cores + UV/OC at boot | `umr`, `python3`, `bc250_smu` | `systemctl status bc250-optimizations` → `active` |
| `apply_phase1.sh` | Chains 3 steps + health-check | 3 scripts below | `sudo /opt/bc250/health-check.sh` → `OK` |
| `bc250-cu-live-manager.sh` | **40 CU** via UMR (gfx1013 registers) | `umr` | `sudo dmesg | grep active_cu_number` → `40` |
| `bc250-unlock-cores.py` | **8 cores** Zen2 via SMU | `python3` | `nproc` → `16` (8c/16t) |
| `bc250_apply.py` | **UV/OC CPU** (Mild profile) | `python3` + `bc250_smu/` | `sudo dmesg | grep -i smu` (no error) |
| `bc250-game-mode` | JEU⇄RAG swap (free/reserve VRAM) | Ollama | `bc250-game-mode status` |
| `bc250-gpu-fix.service` | Fixes GPU util stuck at 655 % | rust (build) or binary | `systemctl status bc250-gpu-fix` + `btop` shows real % |
| `validate.sh` | Validation battery (CU/cores/VRAM/temp/**voltage ≤1300 mV**/services + score) | tools above | `sudo /opt/bc250/validate.sh` → score 100% |

**Verification commands (copy-paste):**
```bash
# Optimization service (40 CU / 8c / UV-OC)
systemctl status bc250-optimizations --no-pager
sudo /opt/bc250/health-check.sh
sudo dmesg | grep -i "active_cu_number" | tail -3
nproc                      # expected 16

# GPU / monitoring
amdgpu_top                 # CU util, clocks, temp, power (Ctrl+C to quit)
btop                       # global view (after fix: correct GPU %)

# Memory swapper
bc250-game-mode status     # shows Ollama + memory + active ttm karg
```

> If `health-check.sh` fails → service **retries** (Restart=on-failure, max 3/2 min) then
> exits cleanly (no bootloop). Typical cause: silicon/VRM refuses OC → adjust profile.

---

## Step 6 — RAG Server (Prof-IA)

Main RAG deployment (FastAPI backend + Ollama + Postgres/pgvector) lives at repo root
(see `README.md`). Summary on BC-250:
```bash
# at project root (after Step 4)
docker compose up -d
ollama pull qwen3:14b      # ~9.3 GB, fits in VRAM (12 GB)
# verify model runs on GPU:
amdgpu_top                 # VRAM line should jump ~9 GB after first query
```

> **Auto-evaluation (Judge + Devil's Advocate).** The same `qwen3:14b` model
> serves both RAG **and** auto-evaluation (sequential, `AUTO_EVALUATE=false` by
> default). To enable: set `AUTO_EVALUATE=true` in `docker-compose.yml`, then
> `docker compose up -d`. Calibrate on 20 golden samples (Pearson r ≥ 0.7)
> before prod. Quality-first settings: `EVAL_TIMEOUT_S=15`, `EVAL_NUM_PREDICT=150`,
> `EVAL_NUM_CTX=2048`, `EVAL_SAMPLE_RATE=1.0`.

---

## Step 7 — Stress Test & Final Validation (MANDATORY before prod)

```bash
# Automated validation (score + hard voltage guard 1300 mV):
sudo /opt/bc250/validate.sh
# -> checks 8c/40CU/VRAM 512MB/services/temp/voltage, offers stress-ng + FurMark

# Manual stress supplement:
stress-ng --cpu 16 --timeout 300s
# GPU 40 CU (Vulkan) — e.g. llama-bench or Steam/Proton game
amdgpu_top
```
Watch `dmesg` for any SMU/AMDGPU errors. If crash/unstable → lower UV/OC profile
(`bc250_apply.py` → edit `frequency`/`scale`) and reboot.

---

## Quick Troubleshooting

- **Black screen on boot** → avoid kernels 6.15.0–6.15.6 / 6.17.8–6.17.10; boot 6.18 LTS.
- **Slow/crackling DP audio** → known DP clock bug; for now **Bluetooth + speaker**
  (chosen). DP 5.1 deferred (kernel patch `DCCG_AUDIO_DTO1_MODULE=6000000`).
- **Ollama OOM / out of VRAM** → verify `ttm.pages_limit=3014656` (`bc250-game-mode status`) and
  profile is "rag" (`bc250-game-mode rag`).
- **40 CU not applied** → `umr` installed? `systemctl restart bc250-optimizations`.

---

## Dependency Summary

```
setup.sh
 ├─ kargs ttm.pages_limit=3014656   (12/4 GB split)
 ├─ kargs zswap.enabled=1 + mitigations=off   (anti-crash RAM/VRAM, reboot required)
 ├─ swapfile Btrfs 32G (/var/swap) + vm.swappiness=120
 ├─ governor cyan-skillfish (COPR)  (GPU limits) + /etc/cyan-skillfish-governor/config.toml
 ├─ umr          ─────────────────► 40 CU (bc250-cu-live-manager.sh : enable all + write-service-table)
 ├─ python3 + bc250_smu ──────────► 8 cores (bc250-unlock-cores.py apply)
 │                                 └► UV/OC  (bc250_detect.py -> bc250_apply.py --apply)
 ├─ bc250-optimizations.service ──► apply_phase1.sh → health-check.sh
 ├─ validate.sh (validation battery + score)
 ├─ bc250-game-mode (usr/local/bin)
 └─ monitoring: btop htop amdgpu_top mangohud + bc250-gpu-fix + lm_sensors
```

---

## Step 8 — RAG Docker Stack (Prof-IA v6.0)

### 8.1 Docker Prerequisites

```bash
# On Bazzite: Docker + compose-plugin already included
# Verify:
docker --version
docker compose version
```

### 8.2 `.env` Configuration (MANDATORY)

```bash
cd <project-root>
cp .env.example .env

# Generate secrets (once):
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24))" >> .env
python3 -c "import secrets; print('API_TOKEN=' + secrets.token_urlsafe(32))" >> .env

# Check content:
cat .env
# Must contain POSTGRES_PASSWORD=... and API_TOKEN=... (non-empty)
```

> **⚠️ Without these two values, `docker compose up` fails** (no weak fallback anymore).

**Auto-evaluation (Judge + Devil's Advocate) — optional variables:**

```bash
# Local auto-evaluation (disabled by default, see docker-compose.yml)
# These values are already set by default in docker-compose.yml;
# add to .env only to override.
echo "AUTO_EVALUATE=false"    >> .env
echo "EVAL_TIMEOUT_S=15"      >> .env
echo "EVAL_NUM_PREDICT=150"   >> .env
echo "EVAL_NUM_CTX=2048"      >> .env
echo "EVAL_SAMPLE_RATE=1.0"   >> .env
```

> **Quality settings** (latency tolerated, everything scored on single `qwen3:14b`):
> `AUTO_EVALUATE=false` → off (prod-safe); `true` → enables sequential auto-evaluation (Judge + Devil's Advocate). `EVAL_SAMPLE_RATE=1.0` scores 100% of responses; `EVAL_TIMEOUT_S=15` caps each judge call.

### 8.3 Container Architecture

| Service | Image | Exposed Ports | Role |
|---------|-------|---------------|------|
| `postgres` | `pgvector/pgvector:pg18` | `127.0.0.1:5432` (loopback) | Vector store + metadata |
| `ollama` | `ollama/ollama:0.32.15` | `127.0.0.1:11434` + `:11436` (loopback) | Local LLM (Vulkan/RADV) |
| `backend` | Local build `./backend/Dockerfile` | `0.0.0.0:8001` | FastAPI RAG engine |
| `frontend` | Local build `./frontend/Dockerfile` | `0.0.0.0:3000` | React UI (3 designs) |
| `nginx` | `nginx:alpine` | `0.0.0.0:8080` | Unified reverse proxy |

**Network**: `prof-ia-network` (isolated Docker bridge). Only nginx, frontend, backend are LAN-accessible. Postgres and Ollama stay on loopback.

### 8.4 Launching the Stack

```bash
# From project root (where docker-compose.yml is)
docker compose up -d

# Follow logs:
docker compose logs -f
```

### 8.5 Service Verification

```bash
# Global health
docker compose ps
# All should be "Up" / "healthy"

# Individual health checks
curl http://localhost:8001/health          # Backend
curl http://localhost:8080/health          # Via nginx
curl http://localhost:11436/api/tags       # Ollama (API tags)
docker exec prof-ia-postgres-v6.0 pg_isready -U user -d prof_ia_v5

# Auto-evaluation (if AUTO_EVALUATE=true)
curl -s http://localhost:8001/health | jq .auto_evaluate
#   → true/false per docker-compose.yml
```

### 8.6 Pull LLM Models (Ollama) + Embeddings (BGE-M3)

```bash
# Main model (qwen3:14b Q4_K_M ~9.3 GB) — fits in BC-250 12 GB VRAM
ollama pull qwen3:14b

# Alternative: via API (from container)
docker exec prof-ia-ollama-vulkan ollama pull qwen3:14b

# Light / fallback model (if VRAM saturated)
ollama pull qwen3:8b

# Verify models present:
ollama list
# Should show qwen3:14b (and qwen3:8b if pulled)

# Verify model loaded in GPU VRAM after first query:
amdgpu_top
# VRAM should jump ~9 GB for qwen3:14b
```

> **Auto-evaluation (Judge + Devil's Advocate).** The same `qwen3:14b` model
> serves both RAG **and** auto-evaluation (sequential, no parallel load). To
> enable: set `AUTO_EVALUATE=true` in `docker-compose.yml` (or `.env`), then
> `docker compose up -d`. Disabled by default — calibrate on 20 golden samples
> (Pearson r ≥ 0.7) before enabling in prod.

**Recommended models for BC-250 (12 GB VRAM available):**

| Model | Size | Usage | Command |
|--------|--------|-------|----------|
| `qwen3:14b` | 9.3 GB | Main (chat + RAG) | `ollama pull qwen3:14b` |
| `qwen3:8b` | 5.2 GB | Light / fallback | `ollama pull qwen3:8b` |

> **Important note — Embeddings (BGE-M3) ≠ ChromaDB**:
> The project uses **pgvector (PostgreSQL)** as vector store, **not ChromaDB**.
> The `BAAI/bge-m3` embeddings (1024-dim, ~1.2 GB) are downloaded **automatically by the backend** via `SentenceTransformers` on first use (first upload/document/indexing), **not via Ollama**.
> They run on **CPU or ROCm** (per `DEVICE` in `rag_engine.py`), not on Ollama's Vulkan GPU.

**Force pre-download of embeddings (optional, avoids first-upload latency):**
```bash
# From backend container (after docker compose up -d)
docker exec prof-ia-backend-v6.0 python3 -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('BAAI/bge-m3', device='cuda' if __import__('torch').cuda.is_available() else 'cpu')
print('Embeddings BGE-M3 loaded:', model.get_sentence_embedding_dimension(), 'dim')
"
```

### 8.6b — PostgreSQL + pgvector (Vector Store)

The `postgres` service (image `pgvector/pgvector:pg18`) is the **only** vector store. No ChromaDB, no Milvus, no Qdrant.

```bash
# Verify PostgreSQL is healthy
docker exec prof-ia-postgres-v6.0 pg_isready -U user -d prof_ia_v5

# Verify pgvector extension
docker exec prof-ia-postgres-v6.0 psql -U user -d prof_ia_v5 -c "SELECT * FROM pg_extension WHERE extname='vector';"

# Verify chunks table (created at first indexing)
docker exec prof-ia-postgres-v6.0 psql -U user -d prof_ia_v5 -c "\dt"
# Should show: rag_chunks, rag_documents, response_evaluations, etc.

# Count indexed chunks
docker exec prof-ia-postgres-v6.0 psql -U user -d prof_ia_v5 -c "SELECT count(*) FROM rag_chunks;"

# Test a vector search (after indexing at least 1 doc)
docker exec prof-ia-postgres-v6.0 psql -U user -d prof_ia_v5 -c "
SELECT chunk_text, 1 - (embedding <=> (SELECT embedding FROM rag_chunks LIMIT 1)) AS similarity
FROM rag_chunks ORDER BY embedding <=> (SELECT embedding FROM rag_chunks LIMIT 1) LIMIT 3;
"
```

**pgvector config (in docker-compose.yml):**
- `shared_buffers=2GB`, `effective_cache_size=6GB`, `work_mem=256MB`
- `max_parallel_workers_per_gather=3`, `wal_compression=zstd`
- `scram-sha-256` auth (no `trust`)

### 8.6c — Embedding Model, Chunking & Ingestion Flow (OKF + Modèle 3)

#### Model used: **BAAI/bge-m3** (1024 dimensions)

| Aspect | Detail |
|--------|--------|
| **Model** | `BAAI/bge-m3` (multilingual, MTEB #1 French) |
| **Dimensions** | 1024 |
| **Size** | ~1.2 GB (auto-downloaded by `SentenceTransformers` on first use) |
| **Device** | CPU or ROCm (per `DEVICE` in `rag_engine.py`) — **not Vulkan/Ollama** |
| **Chunking** | `CHUNK_SIZE=400`, `CHUNK_OVERLAP=80` (config `.env` / `docker-compose.yml`) |
| **Vector store** | **pgvector (PostgreSQL)** — **NO ChromaDB, NO Milvus, NO Qdrant** |
| **Table** | `rag_chunks` (embedding `vector(1024)`, HNSW index) |

> **OKF precision**: OKF v0.2 spec (§4-5) **does not prescribe** an embedding model nor chunking. It defines the **knowledge format** (YAML frontmatter + Markdown body + `sources` + `generated`/`verified` + `status`/`stale_after`). The Prof-IA RAG (vector access layer) uses `bge-m3` to index **both** raw sources (`vault/raw/`, uploads) **AND** compiled wiki pages (`vault/wiki/**/*.md`) — this is the **Modèle 3: LLM Wiki + RAG**.

#### Full ingestion flow (sources → wiki → RAG)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     MODÈLE 3 FLOW — LLM WIKI + RAG                          │
└─────────────────────────────────────────────────────────────────────────────┘

   1. RAW SOURCES (human drop / PIPE)
      └─> vault/raw/                           # PDF, MD, TXT, DOCX, audio, video
          └─> (optional) upload via UI /api/documents/upload

   2. LLM WIKI CONSOLIDATION (karpathywiki plugin OR OpenCode)
      ├─> Ingest / Consolidate
      │     Reads vault/raw/ + Prof-IA corpus
      │     Extracts entities + concepts + sources
      │     Writes vault/wiki/{sources,entities,concepts}/*.md
      │     OKF v0.2 frontmatter + `statut` (Modèle 3 extension)
      │     `[[wiki-links]]` for PPR graph
      │
      ├─> okf-enforcer (Obsidian plugin, MartinForReal, v0.6.1, Apache-2.0)
      │     Validates/auto-fixes OKF frontmatter on save
      │     Hard rule: `type` non-empty; v0.2: `generated`/`verified`,
      │     `status`, `stale_after`, `sources` (objects `uri`/`author`/`last_modified`)
      │
      └─> Lint + Smart Fix All
            Scan: duplicates, dead links, empty/orphan pages,
            missing aliases, contradictions, expired `stale_after`
            → Repair in causal order

   3. VECTOR RAG INDEXING (Prof-IA backend)
      ├─> Indexes: vault/wiki/**/*.md  +  vault/raw/**  +  Prof-IA uploads
      ├─> Chunking: 400 tokens / overlap 80 (configurable)
      ├─> Embedding: bge-m3 (1024-dim) via SentenceTransformers
      └─> Storage: PostgreSQL + pgvector (table `rag_chunks`, HNSW index)

   4. RAG QUERY (Modèle 3: hybrid retrieval)
      ├─> User query → bge-m3 embedding
      ├─> pgvector vector search (top-k, MMR, multi-query per mode)
      ├─> Context + prompt → Ollama (qwen3:14b, Vulkan/RADV)
      └─> Cited response (source chunks + wiki pages)

   5. FEEDBACK LOOP (Human-in-the-loop)
      ├─> /chat returns `conversation_id`
      ├─> POST /feedback {conversation_id, human_rating 1-5, human_feedback, is_golden}
      ├─> `is_golden=true` → SFT dataset (fine_tuning/train.py LoRA)
      └─> New custom Ollama model → closed loop
```

#### Where to drop source documents

| Origin | Location | How it reaches wiki + RAG |
|---------|-------------|--------------------------------------|
| **Human (local files)** | `vault/raw/` (copy-paste / drag-drop) | `karpathywiki` Ingest from folder → `wiki/` + RAG indexes |
| **Prof-IA UI upload** | `POST /api/documents/upload` → `backend/data/uploads/` | RAG indexes direct + `karpathywiki` Ingest (if configured) |
| **PIPE / scripts** | `vault/raw/` via script | Same path |
| **Obsidian (vault open)** | Anywhere in vault (root or `raw/`) | Plugin reads in place, writes to `wiki/` |

> **Important**: The `karpathywiki` plugin **never modifies** your source notes. It reads, extracts, and writes **only** to `wiki/{sources,entities,concepts}/`. Your sources stay intact.

#### karpathywiki Workflow (Obsidian) — Main Commands

Once the vault is open in Obsidian with the `karpathywiki` plugin configured (endpoint `http://127.0.0.1:11436/v1`, `WIKI_API_KEY=unused`):

| Command (command palette) | Action | Result |
|----------------------------------|--------|----------|
| **LLM Wiki: Ingest single source** | Consolidate 1 file | Create/Update pages in `wiki/sources/`, `wiki/entities/`, `wiki/concepts/` |
| **LLM Wiki: Ingest from folder** | Consolidate all `vault/raw/` (recursive) | Full batch, merge duplicates, report contradictions |
| **LLM Wiki: Query wiki** | Chat grounded in wiki | PPR retrieval over `[[wiki-links]]` graph (5 tiers) |
| **LLM Wiki: Lint wiki** | Health scan | Report: duplicates, dead links, orphans, aliases, contradictions, stale |
| **LLM Wiki: Smart Fix All** | Auto-repair | Applies fixes in causal order |
| **LLM Wiki: Regenerate index** | Rebuild `wiki/index.md` | Up-to-date root synthesis |

#### okf-enforcer plugin (Obsidian) — Continuous OKF v0.2 Validation

- **Repo**: `MartinForReal/okf-enforcer` (Obsidian Community Plugins, v0.6.1, Apache-2.0)
- **Spec implemented**: OKF v0.2 (Google Cloud, `knowledge-catalog/okf/SPEC.md`)
- **Role**: Validates and **auto-fixes** frontmatter on save (on-save hooks)
- **Hard rules**:
  - `type` **non-empty** (OKF required)
  - v0.2 fields: `generated`/`verified` (actor convention), `status` (`draft`/`stable`/`deprecated`), `stale_after` (ISO 8601), `sources[]` (objects `uri`, `author`, `last_modified`, `id` for per-claim attribution)
- **Install**: In Obsidian → Community Plugins → search "OKF Enforcer" → Install → Enable
- **Works with**: `karpathywiki` (native coexistence, same Markdown + frontmatter + `[[wiki-links]]` format)

#### OpenCode Workflow (alternative to Obsidian plugin)

OpenCode operates directly on the vault filesystem following `vault/AGENTS.md` (The Schema):

```bash
# From repo root (OpenCode opened on the project)
# Consolidate (ingest): reads raw/, generates/updates wiki/
opencode run "Consolidate vault/raw/ into vault/wiki/ per AGENTS.md"

# Query: reads wiki/, follows [[wiki-links]], answers grounded
opencode run "Answer question X grounded on vault/wiki/"

# Lint: scan dead links, inconsistent frontmatter, duplicates, orphans, stale_after
opencode run "Lint the wiki vault per AGENTS.md and OKF v0.2"
```

> Both executors (`karpathywiki` plugin + OpenCode) produce/consume the **same format** → interchangeable and coexisting.

### 8.12 — systemctl Diagnostics & Service Status (BC-250 + Docker)

#### 8.12.1 BC-250 system services (host)

```bash
# Global status of BC-250 services
systemctl status bc250-optimizations.service --no-pager
systemctl status cyan-skillfish-governor-smu.service --no-pager
systemctl status bc250-gpu-fix.service --no-pager

# Verify they are enabled (auto-start at boot)
systemctl is-enabled bc250-optimizations.service
systemctl is-enabled cyan-skillfish-governor-smu.service
systemctl is-enabled bc250-gpu-fix.service

# Detailed logs (last 50 lines)
journalctl -u bc250-optimizations.service -n 50 --no-pager
journalctl -u cyan-skillfish-governor-smu.service -n 50 --no-pager
journalctl -u bc250-gpu-fix.service -n 50 --no-pager

# Force restart a service (if health-check fails)
sudo systemctl restart bc250-optimizations.service
sudo systemctl restart cyan-skillfish-governor-smu.service

# Verify manual health-check
sudo /opt/bc250/health-check.sh
# Should output: "✅ Health-check OK" + exit 0
```

#### 8.12.2 Docker services (RAG stack)

```bash
# Global stack status
docker compose ps
# All should be "Up" / "healthy" (backend has healthcheck on /health)

# Real-time logs (all services)
docker compose logs -f

# Logs of a specific service
docker compose logs -f backend
docker compose logs -f ollama
docker compose logs -f postgres
docker compose logs -f nginx

# Restart a Docker service
docker compose restart backend
docker compose restart ollama

# Full stack restart
docker compose down && docker compose up -d

# Individual health checks
curl -s http://localhost:8001/health | jq .          # Backend (FastAPI)
curl -s http://localhost:8080/health | jq .          # Via nginx
curl -s http://localhost:11436/api/tags | jq .       # Ollama
docker exec prof-ia-postgres-v6.0 pg_isready -U user -d prof_ia_v5
```

#### 8.12.3 Combined diagnostic commands (full check)

```bash
#!/usr/bin/env bash
# check-all.sh — Full BC-250 + RAG diagnostic
# Save to /usr/local/bin/check-all && chmod +x

echo "=== BC-250 HOST SERVICES ==="
for svc in bc250-optimizations cyan-skillfish-governor-smu bc250-gpu-fix; do
    printf "%-40s " "$svc:"
    systemctl is-active --quiet "$svc" && echo "✅ active" || echo "❌ inactive"
done

echo -e "\n=== GPU / VRAM ==="
bc250-game-mode status
amdgpu_top -b -n 1 | head -30

echo -e "\n=== DOCKER STACK ==="
docker compose ps --format "table {{.Name}}\t{{.Status}}\t{{.Health}}"

echo -e "\n=== HEALTH CHECKS ==="
curl -sf http://localhost:8001/health >/dev/null && echo "✅ Backend healthy" || echo "❌ Backend unhealthy"
curl -sf http://localhost:8080/health >/dev/null && echo "✅ Nginx healthy" || echo "❌ Nginx unhealthy"
curl -sf http://localhost:11436/api/tags >/dev/null && echo "✅ Ollama healthy" || echo "❌ Ollama unhealthy"
docker exec prof-ia-postgres-v6.0 pg_isready -U user -d prof_ia_v5 >/dev/null && echo "✅ Postgres healthy" || echo "❌ Postgres unhealthy"

echo -e "\n=== MODELS ==="
ollama list

echo -e "\n=== AUTO-EVAL ==="
curl -sf http://localhost:8001/health | jq -r '.auto_evaluate // "n/a"' 2>/dev/null \
  && echo "→ AUTO_EVALUATE read from /health" \
  || echo "AUTO_EVALUATE=$(grep -i '^AUTO_EVALUATE' .env 2>/dev/null | cut -d= -f2 || echo 'undefined')"

echo -e "\n=== VRAM USAGE ==="
grep -i vram /proc/meminfo 2>/dev/null || echo "see amdgpu_top above"
```

### 8.13 — Full Install Simulation (Step-by-step Checklist)

Execute in order, **validate each step before moving to the next**:

| # | Action | Command | Expected validation |
|---|--------|----------|---------------------|
| 1 | **BIOS**: UMA 512M, IOMMU Disabled, UEFI | (BIOS menu) | Boot OK, no black screen |
| 2 | **Bazzite**: Install + user + reboot | `dd if=bazzite.iso...` | Bazzite desktop, terminal accessible |
| 3 | **BC-250 Setup**: kargs, governor, deps, services | `cd scripts/bazzite && ./setup.sh` | `rpm-ostree kargs` applied, COPR installed, `/opt/bc250` created |
| 4 | **Mandatory reboot** | `systemctl reboot` | Clean boot, kargs active |
| 5 | **Host verify**: 40 CU, 8c, VRAM split | `sudo /opt/bc250/health-check.sh` | `✅ Health-check OK` |
| 6 | **Full validation** | `sudo /opt/bc250/validate.sh` | Score 100% (or ≥90% without stress) |
| 7 | **Config .env** | `cp .env.example .env && python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24))" >> .env && python3 -c "import secrets; print('API_TOKEN=' + secrets.token_urlsafe(32))" >> .env` | `.env` contains the 2 non-empty secrets |
| 8 | **Docker stack up** | `docker compose up -d` | `docker compose ps` → all Up/healthy |
| 9 | **Pull LLM models** | `ollama pull qwen3:14b && ollama pull qwen3:8b` | `ollama list` shows both models |
| 10 | **Test embeddings** | `docker exec prof-ia-backend-v6.0 python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"` | "Embeddings BGE-M3 loaded: 1024 dim" |
| 11 | **Full RAG test** | Upload 1 PDF via UI `http://IP:8080` → ask for a summary | Coherent response, chunks in DB |
| 12 | **Switch to GAME mode** | `bc250-game-mode game` | Ollama stopped, VRAM freed |
| 13 | **Switch to RAG mode** | `bc250-game-mode rag` | Ollama restarted, model reloaded |
| 14 | **Final diagnostic** | `/usr/local/bin/check-all` | All ✅ |

> **If a step fails**: do not move on. Check logs (`journalctl`, `docker compose logs`), fix, **re-validate the step**.

### 8.7 Nginx Configuration (Reverse Proxy)

The `config/nginx.conf` file is mounted read-only in the nginx container.

**Flow:**
```
Browser → :8080 (nginx)
    ├── /api/*     → backend:8000  (FastAPI, rewrite /api/ → /)
    ├── /health    → backend:8000/health
    ├── /docs      → backend:8000/docs (Swagger)
    └── /*         → frontend:3000 (React SPA)
```

**Critical timeouts for Ollama (BC-250):**
```nginx
proxy_send_timeout     200s;   # Ollama can take up to 180s
proxy_read_timeout     200s;
```

**Security headers**: `X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`, `Referrer-Policy`.

**Max upload**: `client_max_body_size 100M` (for large PDF/audio).

### 8.8 Interface Access

| Interface | URL | Description |
|-----------|-----|-------------|
| Frontend (React) | `http://<IP-BC250>:8080` | Via nginx (recommended) |
| Frontend direct | `http://<IP-BC250>:3000` | Dev / debug |
| Backend API | `http://<IP-BC250>:8001` | Direct (CORS allowed) |
| Backend via nginx | `http://<IP-BC250>:8080/api` | Production |
| Ollama API | `http://<IP-BC250>:11436` | LAN tools / vault |
| Swagger docs | `http://<IP-BC250>:8080/docs` | Dev only |

### 8.9 Stop / Restart / Update

```bash
# Clean stop
docker compose down

# Restart
docker compose up -d

# Update images + rebuild
docker compose pull
docker compose build --no-cache
docker compose up -d

# Wipe volumes (⚠️ DATA LOSS)
docker compose down -v
```

### 8.10 Docker Troubleshooting

| Symptom | Probable cause | Solution |
|----------|----------------|----------|
| `POSTGRES_PASSWORD missing` | `.env` incomplete | Re-copy `.env.example` → `.env` + generate secrets |
| `API_TOKEN missing` | Same | See 8.2 |
| Backend `unhealthy` | Ollama not ready / PG not ready | `docker compose logs backend`; wait for healthchecks |
| Ollama `connection refused` | Vulkan/RADV not available | Check `/dev/dri` + `video`/`render` groups; `HSA_OVERRIDE_GFX_VERSION=10.1.3` |
| VRAM saturated (OOM) | Model too big / no split | `bc250-game-mode rag`; check `ttm.pages_limit=3014656` |
| Nginx 502 | Backend down | `docker compose logs backend`; `systemctl status bc250-optimizations` |

### 8.11 Integration with BC-250 Optimizations

```bash
# Switch to RAG mode (reserve VRAM for Ollama)
bc250-game-mode rag

# Switch to GAME mode (free VRAM)
bc250-game-mode game

# Verify memory state + kargs
bc250-game-mode status
# Should show ttm.pages_limit=3014656 (12 GB GPU)
```

The `bc250-optimizations.service` (Step 4) handles the VRAM split at boot via `rpm-ostree kargs`. The Ollama container uses `/dev/dri` (Vulkan/RADV) — **not ROCm** (gfx1013 not supported by rocBLAS).

---

*Guide generated for BC-250 (Cyan Skillfish / RDNA2 / gfx1013) — Bazzite immutable OS.  
All local, FREE models (Ollama), no cloud. See spec for deep dive.*