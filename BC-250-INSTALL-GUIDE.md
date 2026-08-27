# Guide d'installation BC-250 — Station de jeu + serveur RAG (Bazzite)

Guide **facile**, copier-coller, de la mise sous tension jusqu'à la vérification des
services. Pour le « pourquoi » technique, voir `vault/docs/superpowers/specs/2026-08-26-bc250-bazzite-deployment.md`.

> OS retenu : **Bazzite** (Fedora immutable, `rpm-ostree`). Tout est **local / FREE**,
> aucun cloud. Le BC-250 = AMD Cyan Skillfish / RDNA2 / **gfx1013** (PCI `1002:13fe`).

---

## 0. Prérequis & avertissements

**Matériel**
- Alim **≥ 460 W** correctement câblée. Le connecteur **8-pin PCIe** doit être câblé avec la
  bonne polarité (12V vs GND) — une inversion **détruit la carte définitivement**.
- Câble **DisplayPort 1.4** (le BC-250 n'a **pas** de HDMI — utiliser adaptateur DP→HDMI si besoin).
- (Optionnel) Dongle **Bluetooth USB** pour le son (BlueZ/PipeWire natifs, aucun driver).
- (Recommandé sécurité) Programmateur **CH347** pour sauvegarder/restaurer le BIOS SPI.

**Risques (lire avant de flasher)**
- ⚠️ **Vid CPU > 1325 mV = brick matériel.** On reste sous 1300 mV (profil « Mild »).
- ⚠️ **Flashage BIOS** mal fait = carte brickée. La méthode `bc250_memcfg` (Étape 2) évite le flash
  pour le split VRAM. Le flash n'est utile que pour les menus chipset / 8 cœurs via BIOS.
- ⚠️ **IOMMU** doit rester **désactivé** (casse l'affichage sur BC-250).
- ⚠️ Éviter les noyaux **6.15.0–6.15.6** et **6.17.8–6.17.10** (affichage cassé). Préférer 6.18 LTS
  ou 6.17.11+.

---

## Étape 1 — Flashage du BIOS (optionnel)

> **À faire seulement si** tu veux les menus chipset débloqués ou le déblocage 8 cœurs « propre ».
> Pour le seul split VRAM, passe à l'Étape 2 (méthode `bc250_memcfg`, aucun flash).

1. **Sauvegarde (CH347)** — lire la puce SPI avec `flashrom -p ch347_spi -r backup_stock.bin`,
   puis `diff backup_stock.bin backup_verify.bin` pour confirmer.
2. **Télécharger** l'EFI kit (utilitaires de flash) + le BIOS moddé. Références communautaires :
   - `BC250_3.00_CHIPSETMENU.ROM` (moddé P3.00, VRAM + chipset, **recommandé**) — sha256
     `48fbe5d366e6a56e2fdffdca848426216ba1f083610dab63db89d2f4e6c940b5`
   - `Robin5.00` (stock P5.00) — sha256
     `0d6f136cb120cf3b2de26d5c4d7f255604fdbf4b9442af5ba55419b95b89aa82`
3. **Clé USB FAT32** (≤32 Go) : y mettre l'EFI kit + le `.ROM`.
4. **Flash en EFI Shell** ( BIOS → boot sur la clé) :
   ```bash
   # depuis l'invite EFI Shell, sur le volume de la clé (fs0:)
   fs0:
   cd \<dossier_outils>
   # flash du BIOS moddé (commande exacte selon l'outil fourni dans l'EFI kit)
   <outil_flash> BC250_3.00_CHIPSETMENU.ROM
   ```
   ⚠️ Si le flash « hang » en cours → **ne pas rebooter**, attendre 15 min.
5. **Clear CMOS** (jumper 20 s ou batterie) → reset aux défauts, applique bien le split.
6. Reboot, **Del** pour entrer dans le BIOS → passe à l'Étape 2.

---

## Étape 2 — Réglages BIOS (à faire même sans flash)

Entre dans le BIOS (**Del** au boot). Navigue **Chipset → GFX Configuration** et **Advanced → CPU Configuration**.

| Réglage | Valeur | Pourquoi |
|---|---|---|
| Integrated Graphics Controller | **Forces** | Active l'iGPU |
| UMA Mode | **UMA_SPECIFIED** | Autorise le split VRAM manuel |
| **UMA Frame Buffer Size** | **512MB** (dynamique) | ⚠️ **Garde 512 Mo**, ne passe PAS au preset 4/12 Go (le vrai plafond est le karg `ttm.pages_limit`, posé à l'Étape 4) |
| IOMMU | **Disabled** | Obligatoire (sinon écran noir) |
| Boot Mode | **UEFI** | Standard |

> Le split réel 12 Go GPU / 4 Go CPU est imposé par l'OS (karg), pas par ce menu. 512 Mo = le
> *minimum* réservé ; le GPU grossit jusqu'au plafond dynamiquement.

**Si BIOS stock (pas flashé)** et que tu veux changer la taille VRAM depuis Linux sans flasher :
```bash
git clone https://github.com/fanoush/bc250_memcfg && cd bc250_memcfg && make
sudo ./bc250memcfg UMA_SIZE 512      # 512 = 512 Mo dynamique (recommandé)
```

**F10** (Save & Exit).

---

## Étape 3 — Installation de Bazzite

1. Télécharger **Bazzite Desktop (AMD, Stable)** depuis bazzite.gg.
2. Graver la clé USB :
   ```bash
   # depuis une machine Linux ; ou Fedora Media Writer / balenaEtcher sur Windows
   sudo dd if=bazzite.iso of=/dev/sdX bs=4M status=progress oflag=sync
   ```
3. Booter sur la clé, lancer l'installateur, installer sur le disque (effacement conseillé).
4. Reboot, créer le compte utilisateur, ouvrir un terminal.

---

## Étape 4 — Drivers & provisioning (notre script)

Le script `scripts/bazzite/setup.sh` configure **tout** : kargs VRAM, governor SMU, variables ROCm,
dépendances (`umr`, `python3`), install du service d'optimisations, swapper JEU⇄RAG, et monitoring.

```bash
# Récupérer le dépôt du projet (ou copier le dossier scripts/ sur la machine)
git clone <repo-projet> bc250-deploy && cd bc250-deploy
# ou : copier scripts/ via clé USB

cd scripts/bazzite
./setup.sh
```

> **Note** : les scripts `.sh` n'ont pas besoin d'être rendus exécutables manuellement —
> `setup.sh` s'en charge automatiquement (`chmod +x` sur `/opt/bc250/*.sh` et installation
> de `bc250-game-mode` dans `/usr/local/bin`). Si tu dois les lancer hors `setup.sh` :
> ```bash
> chmod +x scripts/bc250/*.sh
> sudo cp scripts/bc250/bc250-game-mode.sh /usr/local/bin/bc250-game-mode
> sudo chmod +x /usr/local/bin/bc250-game-mode
> ```

Le script fait, dans l'ordre :
1. `rpm-ostree kargs --append-if-missing="ttm.pages_limit=3014656"` → split 12/4 Go.
2. Install governor `cyan-skillfish-governor-smu` (COPR `filippor/bazzite`).
3. Export `HSA_OVERRIDE_GFX_VERSION=10.1.3` + `RADV_DEBUG=nohiz` (ROCm/Mesa).
4. Install `umr` + `python3` (dépendances des scripts SMU/UMR).
5. Copie `scripts/bc250/` → `/opt/bc250`, install + enable `bc250-optimizations.service`.
6. Installe `bc250-game-mode` dans `/usr/local/bin`.
7. Monitoring : `btop htop amdgpu_top mangohud` + `bc250-gpu-fix` (fix util GPU 655 %).

> **Reboot obligatoire** après (kargs + paquets rpm-ostree).

### Si le COPR governor est absent
Le script warning ; installe manuellement depuis `https://copr.fedorainfracloud.org/coprs/filippor/bazzite/`
ou laisse le défaut (les scripts 40 CU fonctionnent sans le governor, qui sert surtout aux limites).

---

## Étape 5 — Vérification des services (rôles & dépendances)

Après reboot, vérifie chaque brique. **Rôles** et **dépendances** :

| Service / outil | Rôle | Dépend de | Vérification |
|---|---|---|---|
| `bc250-optimizations.service` | Orchestre 40 CU + 8 cœurs + UV/OC au boot | `umr`, `python3`, `bc250_smu` | `systemctl status bc250-optimizations` → `active` |
| `apply_phase1.sh` | Enchaîne les 3 étapes + health-check | les 3 scripts ci-dessous | `sudo /opt/bc250/health-check.sh` → `OK` |
| `bc250-cu-live-manager.sh` | **40 CU** via UMR (registres gfx1013) | `umr` | `sudo dmesg | grep active_cu_number` → `40` |
| `bc250-unlock-cores.py` | **8 cœurs** Zen2 via SMU | `python3` | `nproc` → `16` (8c/16t) |
| `bc250_apply.py` | **UV/OC CPU** (profil Mild) | `python3` + `bc250_smu/` | `sudo dmesg | grep -i smu` (pas d'erreur) |
| `bc250-game-mode` | Bascule JEU⇄RAG (libère/réserve VRAM) | Ollama | `bc250-game-mode status` |
| `bc250-gpu-fix.service` | Corrige util GPU bloquée à 655 % | rust (build) ou binaire | `systemctl status bc250-gpu-fix` + `btop` affiche % réel |
| `validate.sh` | Batterie de validation (CU/cœurs/VRAM/temp/**tension ≤1300 mV**/services + score) | outils ci-dessus | `sudo /opt/bc250/validate.sh` → score 100% |

**Commandes de vérif (copier-coller) :**
```bash
# Service d'optimisations (40 CU / 8c / UV-OC)
systemctl status bc250-optimizations --no-pager
sudo /opt/bc250/health-check.sh
sudo dmesg | grep -i "active_cu_number" | tail -3
nproc                      # attendu 16

# GPU / monitoring
amdgpu_top                 # util CU, clocks, temp, power (Ctrl+C pour quitter)
btop                       # vue globale (après fix : % GPU correct)

# Swapper mémoire
bc250-game-mode status     # montre Ollama + mémoire + karg ttm actif
```

> Si `health-check.sh` échoue → le service **retente** (Restart=on-failure, max 3/2 min) puis
> lâche proprement (pas de bootloop). Cause typique : silicon/VRM refuse l'OC → revoir le profil.

---

## Étape 6 — Serveur RAG (Prof-IA)

Le déploiement RAG principal (backend FastAPI + Ollama + Postgres/pgvector) est géré à la racine
du dépôt (voir `README.md`). En résumé sur le BC-250 :
```bash
# à la racine du projet (après Étape 4)
docker compose up -d
ollama pull qwen3:14b      # ~9,3 Go, tient en VRAM (12 Go)
# vérifier que le modèle est en GPU :
amdgpu_top                 # la ligne VRAM doit monter ~9 Go après un premier query
```

> **Auto-évaluation (Juge + Avocat du Diable).** Le même modèle `qwen3:14b`
> sert au RAG **et** à l'auto-évaluation (séquentiel, `AUTO_EVALUATE=false` par
> défaut). Pour l'activer : `AUTO_EVALUATE=true` dans `docker-compose.yml`, puis
> `docker compose up -d`. Calibrer sur 20 golden (Pearson r ≥ 0,7) avant prod.

---

## Étape 7 — Stress test & validation finale (OBLIGATOIRE avant prod)

```bash
# Validation automatisée (score + garde-fou tension dur 1300 mV) :
sudo /opt/bc250/validate.sh
# -> vérifie 8c/40CU/VRAM 512Mo/services/temp/tension, propose stress-ng + FurMark

# Stress manuel complémentaire :
stress-ng --cpu 16 --timeout 300s
# GPU 40 CU (Vulkan) — ex. llama-bench ou un jeu Steam/Proton
amdgpu_top
```
Surveille `dmesg` pour toute erreur SMU/AMDGPU. Si crash/instable → réduire le profil UV/OC
(`bc250_apply.py` → éditer `frequency`/`scale`) et reboote.

---

## Dépannage rapide

- **Écran noir au boot** → kernel à éviter (6.15.0–6.15.6 / 6.17.8–6.17.10) ; boot sur 6.18 LTS.
- **Audio DP lent/crachouillant** → bug horloge DP connu ; pour l'instant **Bluetooth + enceinte**
  (choix retenu). Audio DP 5.1 différé (patch noyau `DCCG_AUDIO_DTO1_MODULE=6000000`).
- **Ollama hors VRAM** → vérifier `ttm.pages_limit=3014656` (`bc250-game-mode status`) et que le
  profil est bien « rag » (`bc250-game-mode rag`).
- **40 CU non pris** → `umr` installé ? `systemctl restart bc250-optimizations`.

---

## Résumé des dépendances

```
setup.sh
  ├─ kargs ttm.pages_limit=3014656   (split 12/4 Go)
  ├─ kargs zswap.enabled=1 + mitigations=off   (anti-crash RAM/VRAM, reboot requis)
  ├─ swapfile Btrfs 32G (/var/swap) + vm.swappiness=120
  ├─ governor cyan-skillfish (COPR)  (limites GPU) + /etc/cyan-skillfish-governor/config.toml
  ├─ umr          ─────────────────► 40 CU (bc250-cu-live-manager.sh : enable all + write-service-table)
  ├─ python3 + bc250_smu ──────────► 8 cœurs (bc250-unlock-cores.py apply)
  │                                 └► UV/OC  (bc250_detect.py -> bc250_apply.py --apply)
  ├─ bc250-optimizations.service ──► apply_phase1.sh → health-check.sh
  ├─ validate.sh (batterie de validation + score)
  ├─ bc250-game-mode (usr/local/bin)
  └─ monitoring: btop htop amdgpu_top mangohud + bc250-gpu-fix + lm_sensors
```

---

## Étape 8 — Stack Docker RAG (Prof-IA v6.0)

### 8.1 Prérequis Docker

```bash
# Sur Bazzite : Docker + compose-plugin déjà inclus
# Vérification :
docker --version
docker compose version
```

### 8.2 Configuration `.env` (OBLIGATOIRE)

```bash
cd <racine-du-projet>
cp .env.example .env

# Générer les secrets (une seule fois) :
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24))" >> .env
python3 -c "import secrets; print('API_TOKEN=' + secrets.token_urlsafe(32))" >> .env

# Vérifier le contenu :
cat .env
# Doit contenir POSTGRES_PASSWORD=... et API_TOKEN=... (non vides)
```

> **⚠️ Sans ces deux valeurs, `docker compose up` échoue** (plus de fallback faible).

**Auto-évaluation (Juge + Avocat du Diable) — variables optionnelles :**

```bash
# Auto-évaluation locale (désactivée par défaut, voir docker-compose.yml)
# Ces valeurs sont déjà posées par défaut dans docker-compose.yml ;
# ne les ajoute au .env que pour override.
echo "AUTO_EVALUATE=false"    >> .env
echo "EVAL_TIMEOUT_S=15"      >> .env
echo "EVAL_NUM_PREDICT=150"   >> .env
echo "EVAL_NUM_CTX=2048"      >> .env
echo "EVAL_SAMPLE_RATE=1.0"   >> .env
```

> **Réglages qualité** (latence tolérée, tout est scoré sur `qwen3:14b` unique) :
> `AUTO_EVALUATE=false` → off (sûr en prod) ; `true` → active l'auto-évaluation
> séquentielle (Juge + Avocat du Diable). `EVAL_SAMPLE_RATE=1.0` score 100 % des
> réponses ; `EVAL_TIMEOUT_S=15` plafonne chaque appel juge.

### 8.3 Architecture des conteneurs

| Service | Image | Ports exposés | Rôle |
|---------|-------|---------------|------|
| `postgres` | `pgvector/pgvector:pg18` | `127.0.0.1:5432` (loopback) | Vector store + métadonnées |
| `ollama` | `ollama/ollama:0.32.15` | `127.0.0.1:11434` + `:11436` (loopback) | LLM local (Vulkan/RADV) |
| `backend` | Build local `./backend/Dockerfile` | `0.0.0.0:8001` | FastAPI RAG engine |
| `frontend` | Build local `./frontend/Dockerfile` | `0.0.0.0:3000` | React UI (3 designs) |
| `nginx` | `nginx:alpine` | `0.0.0.0:8080` | Reverse proxy unifié |

**Réseau** : `prof-ia-network` (bridge Docker isolé). Seuls nginx, frontend, backend sont accessibles LAN. Postgres et Ollama restent en loopback.

### 8.4 Lancement de la stack

```bash
# À la racine du projet (où est docker-compose.yml)
docker compose up -d

# Suivre les logs :
docker compose logs -f
```

### 8.5 Vérification des services

```bash
# Santé globale
docker compose ps
# Tous doivent être "Up" / "healthy"

# Health checks individuels
curl http://localhost:8001/health          # Backend
curl http://localhost:8080/health          # Via nginx
curl http://localhost:11436/api/tags       # Ollama (API tags)
docker exec prof-ia-postgres-v6.0 pg_isready -U user -d prof_ia_v5

# Auto-évaluation (si AUTO_EVALUATE=true)
curl -s http://localhost:8001/health | jq .auto_evaluate
#   → true/false selon docker-compose.yml
```

### 8.6 Pull des modèles LLM (Ollama) + Embeddings (BGE-M3)

```bash
# Modèle principal (qwen3:14b Q4_K_M ~9,3 Go) — tient en VRAM 12 Go BC-250
ollama pull qwen3:14b

# Alternative : via l'API (depuis le conteneur)
docker exec prof-ia-ollama-vulkan ollama pull qwen3:14b

# Modèle léger / fallback (si VRAM saturée)
ollama pull qwen3:8b

# Vérifier que les modèles sont présents :
ollama list
# Doit afficher qwen3:14b (et qwen3:8b si pullé)

# Vérifier que le modèle est chargé en VRAM GPU après premier query :
amdgpu_top
# La VRAM doit monter ~9 Go pour qwen3:14b
```

> **Auto-évaluation (Juge + Avocat du Diable).** Le même modèle `qwen3:14b`
> sert au RAG **et** à l'auto-évaluation (séquentiel, pas de chargement
> parallèle). Pour l'activer : poser `AUTO_EVALUATE=true` dans
> `docker-compose.yml` (ou `.env`), puis `docker compose up -d`. Désactivé par
> défaut — calibrer sur 20 golden (Pearson r ≥ 0,7) avant activation en prod.

**Modèles recommandés pour BC-250 (12 Go VRAM dispo) :**

| Modèle | Taille | Usage | Commande |
|--------|--------|-------|----------|
| `qwen3:14b` | 9,3 Go | Principal (chat + RAG) | `ollama pull qwen3:14b` |
| `qwen3:8b` | 5,2 Go | Léger / fallback | `ollama pull qwen3:8b` |

> **Note importante — Embeddings (BGE-M3) ≠ ChromaDB** :  
> Le projet utilise **pgvector (PostgreSQL)** comme vector store, **pas ChromaDB**.  
> Les embeddings `BAAI/bge-m3` (1024-dim, ~1,2 Go) sont téléchargés **automatiquement par le backend** via `SentenceTransformers` au premier usage (premier upload/document/indexation), **pas via Ollama**.  
> Ils s'exécutent sur **CPU ou ROCm** (selon `DEVICE` dans `rag_engine.py`), pas sur le GPU Vulkan d'Ollama.

**Forcer le pré-téléchargement des embeddings (optionnel, évite la latence du 1er upload) :**
```bash
# Depuis le conteneur backend (après docker compose up -d)
docker exec prof-ia-backend-v6.0 python3 -c "
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('BAAI/bge-m3', device='cuda' if __import__('torch').cuda.is_available() else 'cpu')
print('Embeddings BGE-M3 chargés :', model.get_sentence_embedding_dimension(), 'dim')
"
```

### 8.6b — PostgreSQL + pgvector (Vector Store)

Le service `postgres` (image `pgvector/pgvector:pg18`) est le **seul** vector store. Pas de ChromaDB, pas de Milvus, pas de Qdrant.

```bash
# Vérifier que PostgreSQL est healthy
docker exec prof-ia-postgres-v6.0 pg_isready -U user -d prof_ia_v5

# Vérifier l'extension pgvector
docker exec prof-ia-postgres-v6.0 psql -U user -d prof_ia_v5 -c "SELECT * FROM pg_extension WHERE extname='vector';"

# Vérifier la table de chunks (créée au premier indexing)
docker exec prof-ia-postgres-v6.0 psql -U user -d prof_ia_v5 -c "\dt"
# Doit afficher : rag_chunks, rag_documents, response_evaluations, etc.

# Compter les chunks indexés
docker exec prof-ia-postgres-v6.0 psql -U user -d prof_ia_v5 -c "SELECT count(*) FROM rag_chunks;"

# Tester une recherche vectorielle (après avoir indexé au moins 1 doc)
docker exec prof-ia-postgres-v6.0 psql -U user -d prof_ia_v5 -c "
SELECT chunk_text, 1 - (embedding <=> (SELECT embedding FROM rag_chunks LIMIT 1)) AS similarity
FROM rag_chunks ORDER BY embedding <=> (SELECT embedding FROM rag_chunks LIMIT 1) LIMIT 3;
"
```

**Configuration pgvector (dans docker-compose.yml) :**
- `shared_buffers=2GB`, `effective_cache_size=6GB`, `work_mem=256MB`
- `max_parallel_workers_per_gather=3`, `wal_compression=zstd`
- Authentification `scram-sha-256` (pas de `trust`)

### 8.6c — Modèle d'embedding, chunking & flux d'ingestion (OKF + Modèle 3)

#### Modèle utilisé : **BAAI/bge-m3** (1024 dimensions)

| Aspect | Détail |
|--------|--------|
| **Modèle** | `BAAI/bge-m3` (multilingue, MTEB #1 français) |
| **Dimensions** | 1024 |
| **Taille** | ~1,2 Go (téléchargé auto par `SentenceTransformers` au 1er usage) |
| **Device** | CPU ou ROCm (selon `DEVICE` dans `rag_engine.py`) — **pas Vulkan/Ollama** |
| **Chunking** | `CHUNK_SIZE=400`, `CHUNK_OVERLAP=80` (config `.env` / `docker-compose.yml`) |
| **Vector store** | **pgvector (PostgreSQL)** — **PAS ChromaDB, PAS Milvus, PAS Qdrant** |
| **Table** | `rag_chunks` (embedding `vector(1024)`, HNSW index) |

> **Précision OKF** : La spec OKF v0.2 (§4-5) **ne prescrit pas** de modèle d'embedding ni de chunking. Elle définit le **format de connaissance** (frontmatter YAML + body Markdown + `sources` + `generated`/`verified` + `status`/`stale_after`). Le RAG Prof-IA (couche d'accès vectoriel) utilise `bge-m3` pour indexer **à la fois** les sources brutes (`vault/raw/`, uploads) **ET** les pages wiki compilées (`vault/wiki/**/*.md`) — c'est le **Modèle 3 : LLM Wiki + RAG**.

#### Flux d'ingestion complet (sources → wiki → RAG)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        FLUX MODÈLE 3 — LLM WIKI + RAG                       │
└─────────────────────────────────────────────────────────────────────────────┘

  1. SOURCES BRUTES (dépôt humain / PIPE)
     └─> vault/raw/                           # PDF, MD, TXT, DOCX, audio, vidéo
         └─> (optionnel) upload via UI /api/documents/upload

  2. CONSOLIDATION LLM WIKI (plugin karpathywiki OU OpenCode)
     ├─> Ingest / Consolidate
     │     Lit vault/raw/ + corpus Prof-IA
     │     Extrait entités + concepts + sources
     │     Écrit vault/wiki/{sources,entities,concepts}/*.md
     │     Frontmatter OKF v0.2 + `statut` (extension Modèle 3)
     │     Liens `[[wiki-links]]` pour graphe PPR
     │
     ├─> okf-enforcer (plugin Obsidian, MartinForReal, v0.6.1, Apache-2.0)
     │     Valide/auto-fixe le frontmatter OKF à la sauvegarde
     │     Règle dure : `type` non vide ; v0.2 : `generated`/`verified`,
     │     `status`, `stale_after`, `sources` (objets `uri`/`author`/`last_modified`)
     │
     └─> Lint + Smart Fix All
           Scan : doublons, liens morts, pages vides/orphelines,
           aliases manquants, contradictions, `stale_after` dépassé
           → Réparation en ordre causal

  3. INDEXATION RAG VECTORIEL (backend Prof-IA)
     ├─> Indexe : vault/wiki/**/*.md  +  vault/raw/**  +  uploads Prof-IA
     ├─> Chunking : 400 tokens / overlap 80 (configurable)
     ├─> Embedding : bge-m3 (1024-dim) via SentenceTransformers
     └─> Stockage : PostgreSQL + pgvector (table `rag_chunks`, index HNSW)

  4. REQUÊTE RAG (Modèle 3 : retrieval hybride)
     ├─> Query utilisateur → embedding bge-m3
     ├─> Recherche vectorielle pgvector (top-k, MMR, multi-query selon mode)
     ├─> Contexte + prompt → Ollama (qwen3:14b, Vulkan/RADV)
     └─> Réponse citée (chunks sources + pages wiki)

  5. BOUCLE DE RÉTROACTION (Human-in-the-loop)
     ├─> /chat retourne `conversation_id`
     ├─> POST /feedback {conversation_id, human_rating 1-5, human_feedback, is_golden}
     ├─> `is_golden=true` → jeu de données SFT (fine_tuning/train.py LoRA)
     └─> Nouveau modèle Ollama personnalisé → boucle fermée
```

#### Où déposer les documents sources

| Origine | Emplacement | Comment ça arrive dans le wiki + RAG |
|---------|-------------|--------------------------------------|
| **Humain (fichiers locaux)** | `vault/raw/` (copier-coller / glisser-déposer) | `karpathywiki` Ingest from folder → `wiki/` + RAG indexe |
| **Upload UI Prof-IA** | `POST /api/documents/upload` → `backend/data/uploads/` | RAG indexe direct + `karpathywiki` Ingest (si configuré) |
| **PIPE / scripts** | `vault/raw/` via script | Même chemin |
| **Obsidian (vault ouvert)** | N'importe où dans le vault (racine ou `raw/`) | Plugin lit en place, écrit dans `wiki/` |

> **Important** : Le plugin `karpathywiki` **ne modifie jamais** vos notes sources. Il lit, extrait, et écrit **uniquement** dans `wiki/{sources,entities,concepts}/`. Vos sources restent intactes.

#### Workflow karpathywiki (Obsidian) — Commandes principales

Une fois le vault ouvert dans Obsidian avec le plugin `karpathywiki` configuré (endpoint `http://127.0.0.1:11436/v1`, `WIKI_API_KEY=unused`) :

| Commande (palette de commandes) | Action | Résultat |
|----------------------------------|--------|----------|
| **LLM Wiki: Ingest single source** | Consolidate 1 fichier | Crée/MAJ pages dans `wiki/sources/`, `wiki/entities/`, `wiki/concepts/` |
| **LLM Wiki: Ingest from folder** | Consolidate tout `vault/raw/` (récursif) | Batch complet, fusion doublons, signale contradictions |
| **LLM Wiki: Query wiki** | Chat grounded dans le wiki | Retrieval PPR sur graphe `[[wiki-links]]` (5 étages) |
| **LLM Wiki: Lint wiki** | Scan santé | Rapport : doublons, liens morts, orphelins, aliases, contradictions, stale |
| **LLM Wiki: Smart Fix All** | Réparation auto | Applique les fixes dans l'ordre causal |
| **LLM Wiki: Regenerate index** | Reconstruit `wiki/index.md` | Synthèse racine à jour |

#### Plugin okf-enforcer (Obsidian) — Validation continue OKF v0.2

- **Repo** : `MartinForReal/okf-enforcer` (Obsidian Community Plugins, v0.6.1, Apache-2.0)
- **Spec implémentée** : OKF v0.2 (Google Cloud, `knowledge-catalog/okf/SPEC.md`)
- **Rôle** : Valide et **auto-corrig** le frontmatter à la sauvegarde (hooks on-save)
- **Règles dures** :
  - `type` **non vide** (requis OKF)
  - Champs v0.2 : `generated`/`verified` (actor convention), `status` (`draft`/`stable`/`deprecated`), `stale_after` (ISO 8601), `sources[]` (objets `uri`, `author`, `last_modified`, `id` pour attribution per-claim)
- **Installation** : Dans Obsidian → Community Plugins → chercher "OKF Enforcer" → Installer → Activer
- **Fonctionne avec** : `karpathywiki` (cohabitation native, même format Markdown + frontmatter + `[[wiki-links]]`)

#### Workflow OpenCode (alternative au plugin Obsidian)

OpenCode opère directement sur le filesystem du vault en suivant `vault/AGENTS.md` (The Schema) :

```bash
# Depuis la racine du repo (OpenCode ouvert sur le projet)
# Consolidate (ingest) : lit raw/, génère/maj wiki/
opencode run "Consolide vault/raw/ vers vault/wiki/ selon AGENTS.md"

# Query : lit wiki/, suit les [[wiki-links]], répond grounded
opencode run "Répond à la question X en t'appuyant sur vault/wiki/"

# Lint : scan liens morts, frontmatter incohérent, doublons, orphelins, stale_after
opencode run "Lint le vault wiki selon AGENTS.md et OKF v0.2"
```

> Les deux exécuteurs (`karpathywiki` plugin + OpenCode) produisent/consomment le **même format** → interchangeables et cohabitables.

### 8.12 — Diagnostics systemctl & Statut des services (BC-250 + Docker)

#### 8.12.1 Services système BC-250 (host)

```bash
# État global des services BC-250
systemctl status bc250-optimizations.service --no-pager
systemctl status cyan-skillfish-governor-smu.service --no-pager
systemctl status bc250-gpu-fix.service --no-pager

# Vérifier qu'ils sont enabled (démarrage auto au boot)
systemctl is-enabled bc250-optimizations.service
systemctl is-enabled cyan-skillfish-governor-smu.service
systemctl is-enabled bc250-gpu-fix.service

# Logs détaillés (derniers 50 lignes)
journalctl -u bc250-optimizations.service -n 50 --no-pager
journalctl -u cyan-skillfish-governor-smu.service -n 50 --no-pager
journalctl -u bc250-gpu-fix.service -n 50 --no-pager

# Redémarrage forcé d'un service (si健康检查 échoue)
sudo systemctl restart bc250-optimizations.service
sudo systemctl restart cyan-skillfish-governor-smu.service

# Vérifier le health-check manuel
sudo /opt/bc250/health-check.sh
# Doit sortir : "✅ Health-check OK" + exit 0
```

#### 8.12.2 Services Docker (stack RAG)

```bash
# État global de la stack
docker compose ps
# Tous doivent être "Up" / "healthy" (backend a healthcheck sur /health)

# Logs en temps réel (tous services)
docker compose logs -f

# Logs d'un service spécifique
docker compose logs -f backend
docker compose logs -f ollama
docker compose logs -f postgres
docker compose logs -f nginx

# Redémarrage d'un service Docker
docker compose restart backend
docker compose restart ollama

# Redémarrage complet de la stack
docker compose down && docker compose up -d

# Health checks individuels
curl -s http://localhost:8001/health | jq .          # Backend (FastAPI)
curl -s http://localhost:8080/health | jq .          # Via nginx
curl -s http://localhost:11436/api/tags | jq .       # Ollama
docker exec prof-ia-postgres-v6.0 pg_isready -U user -d prof_ia_v5
```

#### 8.12.3 Commandes de diagnostic combinées (check complet)

```bash
#!/usr/bin/env bash
# check-all.sh — Diagnostic complet BC-250 + RAG
# À sauvegarder sous /usr/local/bin/check-all && chmod +x

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
  && echo "→ AUTO_EVALUATE lu depuis /health" \
  || echo "AUTO_EVALUATE=$(grep -i '^AUTO_EVALUATE' .env 2>/dev/null | cut -d= -f2 || echo 'non défini')"

echo -e "\n=== VRAM USAGE ==="
grep -i vram /proc/meminfo 2>/dev/null || echo "voir amdgpu_top ci-dessus"
```

### 8.13 — Simulation d'installation complète (Checklist pas-à-pas)

Exécute dans l'ordre, **valide chaque étape avant de passer à la suivante** :

| # | Action | Commande | Validation attendue |
|---|--------|----------|---------------------|
| 1 | **BIOS** : UMA 512M, IOMMU Disabled, UEFI | (BIOS menu) | Boot OK, pas d'écran noir |
| 2 | **Bazzite** : Install + user + reboot | `dd if=bazzite.iso...` | Bureau Bazzite, terminal accessible |
| 3 | **Setup BC-250** : kargs, governor, deps, services | `cd scripts/bazzite && ./setup.sh` | `rpm-ostree kargs` appliqués, COPR installé, `/opt/bc250` créé |
| 4 | **Reboot obligatoire** | `systemctl reboot` | Boot propre, kargs actifs |
| 5 | **Vérif host** : 40 CU, 8c, VRAM split | `sudo /opt/bc250/health-check.sh` | `✅ Health-check OK` |
| 6 | **Validation complète** | `sudo /opt/bc250/validate.sh` | Score 100% (ou ≥90% sans stress) |
| 7 | **Config .env** | `cp .env.example .env && python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24))" >> .env && python3 -c "import secrets; print('API_TOKEN=' + secrets.token_urlsafe(32))" >> .env` | `.env` contient les 2 secrets non vides |
| 8 | **Docker stack up** | `docker compose up -d` | `docker compose ps` → tous Up/healthy |
| 9 | **Pull modèles LLM** | `ollama pull qwen3:14b && ollama pull qwen3:8b` | `ollama list` affiche les 2 modèles |
| 10 | **Test embeddings** | `docker exec prof-ia-backend-v6.0 python3 -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('BAAI/bge-m3')"` | "Embeddings BGE-M3 chargés : 1024 dim" |
| 11 | **Test RAG complet** | Upload 1 PDF via UI `http://IP:8080` → demander un résumé | Réponse cohérente, chunks en base |
| 12 | **Basculer mode JEU** | `bc250-game-mode game` | Ollama stoppé, VRAM libérée |
| 13 | **Basculer mode RAG** | `bc250-game-mode rag` | Ollama redémarré, modèle rechargé |
| 14 | **Diagnostic final** | `/usr/local/bin/check-all` | Tout ✅ |

> **Si une étape échoue** : ne passe pas à la suivante. Consulte les logs (`journalctl`, `docker compose logs`), corrige, **revalide l'étape**.

### 8.7 Configuration Nginx (Reverse Proxy)

Le fichier `config/nginx.conf` est monté en read-only dans le conteneur nginx.

**Flux :**
```
Browser → :8080 (nginx)
    ├── /api/*     → backend:8000  (FastAPI, rewrite /api/ → /)
    ├── /health    → backend:8000/health
    ├── /docs      → backend:8000/docs (Swagger)
    └── /*         → frontend:3000 (React SPA)
```

**Timeouts critiques pour Ollama (BC-250) :**
```nginx
proxy_send_timeout     200s;   # Ollama peut mettre jusqu'à 180s
proxy_read_timeout     200s;
```

**Headers de sécurité** : `X-Frame-Options`, `X-Content-Type-Options`, `X-XSS-Protection`, `Referrer-Policy`.

**Upload max** : `client_max_body_size 100M` (pour PDF/audio volumineux).

### 8.8 Accès aux interfaces

| Interface | URL | Description |
|-----------|-----|-------------|
| Frontend (React) | `http://<IP-BC250>:8080` | Via nginx (recommandé) |
| Frontend direct | `http://<IP-BC250>:3000` | Dev / debug |
| Backend API | `http://<IP-BC250>:8001` | Direct (CORS autorisé) |
| Backend via nginx | `http://<IP-BC250>:8080/api` | Production |
| Ollama API | `http://<IP-BC250>:11436` | LAN tools / vault |
| Swagger docs | `http://<IP-BC250>:8080/docs` | Dev uniquement |

### 8.9 Arrêt / Redémarrage / Mise à jour

```bash
# Arrêt propre
docker compose down

# Redémarrage
docker compose up -d

# Mise à jour images + rebuild
docker compose pull
docker compose build --no-cache
docker compose up -d

# Vider les volumes (⚠️ PERTE DE DONNÉES)
docker compose down -v
```

### 8.10 Dépannage Docker

| Symptôme | Cause probable | Solution |
|----------|----------------|----------|
| `POSTGRES_PASSWORD manquant` | `.env` incomplet | Recopier `.env.example` → `.env` + générer secrets |
| `API_TOKEN manquant` | Idem | Voir 8.2 |
| Backend `unhealthy` | Ollama pas prêt / PG pas ready | `docker compose logs backend` ; attendre healthchecks |
| Ollama `connection refused` | Vulkan/RADV pas dispo | Vérifier `/dev/dri` + groups `video`/`render` ; `HSA_OVERRIDE_GFX_VERSION=10.1.3` |
| VRAM saturée (OOM) | Modèle trop gros / pas de split | `bc250-game-mode rag` ; vérifier `ttm.pages_limit=3014656` |
| Nginx 502 | Backend down | `docker compose logs backend` ; `systemctl status bc250-optimizations` |

### 8.11 Intégration avec les optimisations BC-250

```bash
# Basculer en mode RAG (réserve VRAM pour Ollama)
bc250-game-mode rag

# Basculer en mode JEU (libère VRAM)
bc250-game-mode game

# Vérifier l'état mémoire + kargs
bc250-game-mode status
# Doit afficher ttm.pages_limit=3014656 (12 Go GPU)
```

Le service `bc250-optimizations.service` (Étape 4) gère le split VRAM au boot via `rpm-ostree kargs`. Le conteneur Ollama utilise `/dev/dri` (Vulkan/RADV) — **pas ROCm** (gfx1013 non supporté par rocBLAS).
