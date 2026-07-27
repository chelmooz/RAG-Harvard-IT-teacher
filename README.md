# Prof IA v6.0 — RAG Engine (pgvector)
## Documentation Technique

**AMD BC-250 · Cyan Skillfish (RDNA2) · ROCm 7.2**  
*À destination des Web Designers · DevOps · Administrateurs Système · Étudiants TSSR / AIS / DevOps*

> **Baseline active : v6.0 (PROJET GITHUB/)** — Backend vectoriel PostgreSQL + pgvector.  
> Versions antérieures archivées dans `_archive/` (v5.5, v5.8.3 ChromaDB).

---

## Déploiement rapide

```bash
# 1. Prérequis : Docker Compose, GPU AMD BC-250 avec ROCm
# 2. Configuration — OBLIGATOIRE (docker compose refuse de démarrer sans ça)
cp .env.example .env
python3 -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(24))" >> .env
python3 -c "import secrets; print('API_TOKEN=' + secrets.token_urlsafe(32))" >> .env

# 3. Lancer la stack complète
docker compose up -d

# 4. Vérifier l'état
curl http://localhost:8001/health

# 5. Tester le chat RAG (remplacer <token> par votre API_TOKEN)
curl -X POST http://localhost:8001/chat \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"query":"Qu'\''est-ce que TCP/IP ?","metier":"TSSR"}'

# 6. Build avec GPU ROCm (défaut) ou CPU uniquement
docker compose build --build-arg USE_ROCM=false backend
```

**Accès :**
- Frontend : http://localhost:3000
- API Backend : http://localhost:8001
- Proxy Nginx : http://localhost:8080

---

## Table des matières

1. [Caractéristiques de la Stack v6.0](#1-caractéristiques-de-la-stack-v60)
   - [1.4 Déblocage 40 CU RDNA2 (optionnel)](#14-déblocage-40-cu-rdna2-optionnel)
   - [1.5 BIOS modifié (prérequis IOMMU / VRAM avancé)](#15-bios-modifié-prérequis-iommu--vram-avancé)
2. [Paquets Installés et Versions](#2-paquets-installés-et-versions)
3. [Architecture — PostgreSQL + pgvector HNSW](#3-architecture--postgresql--pgvector-hnsw)
4. [Formats de Fichiers Supportés](#4-formats-de-fichiers-supportés)
5. [RAG — Modes de Requête](#5-rag--modes-de-requête)
6. [Datasets & Fine-Tuning LoRA](#6-datasets--fine-tuning-lora)
7. [Guide par Profil Utilisateur](#7-guide-par-profil-utilisateur)
8. [Architecture Globale — Vue d'ensemble](#8-architecture-globale--vue-densemble)

---

## 1. Caractéristiques de la Stack v6.0

### 1.1 Matériel — AMD BC-250 (Cyan Skillfish)

| Composant | Spécification | Impact v5.8.3 |
|---|---|---|
| APU | AMD BC-250 — Cyan Skillfish (gfx1013) | Cible d'optimisation principale |
| Architecture CPU | 6 cœurs × Zen 2 @ ~3,0 GHz | asyncio TaskGroup Python 3.13 |
| Architecture GPU | 24 Compute Units RDNA2 (40 CU débloquables — [voir §1.4](#14-déblocage-40-cu-rdna2-optionnel)) | Batch embeddings, inference Ollama |
| Mémoire | 16 Go GDDR6 unifiée (partagée CPU+GPU) | Zéro copie PCIe, accès direct |
| VRAM allouée | 12 Go budget appli (kernel : gttsize=14750+ttm.*, cf. §1.3) | LLM + embeddings simultanés |
| Stockage principal | SSD NVMe interne | OS, Docker, modèles Ollama |
| Stockage documents | SSD USB 3.0 externe | Corpus RAG, uploads, backups |
| Réseau | 1 GbE / Wi-Fi selon config | API REST locale — réseau 192.168.1.x |

### 1.2 Stack Logicielle

| Couche | Technologie | Version | Rôle |
|---|---|---|---|
| OS | Debian GNU/Linux 13.3 (Trixie) | 13.3 | Système de base |
| Kernel | Linux AMD | 6.18+ | Pilote amdgpu intégré |
| Pilotes GPU | Mesa / RADV Vulkan | 26.0.0 | Rendu + compute ROCm |
| Framework IA | PyTorch + ROCm | 2.11+ / 7.2 | Calcul GPU natif RDNA2 |
| Python | CPython | 3.13 | asyncio TaskGroup natif |
| LLM Runtime | Ollama (image standard, backend Vulkan/RADV) | Latest Vulkan | Inference Qwen3-14B / DeepSeek R1 |
| Base vectorielle | PostgreSQL + pgvector | 18.2 | Table `rag_chunks`, index HNSW |
| Embeddings | BAAI/bge-m3 | sentence-transformers 3.0.1 | 1024 dimensions — meilleur choix local pour le FR (MTEB 2026) |
| API Backend | FastAPI + Uvicorn | 0.115.0 / 0.30.0 | REST API async |
| Frontend | React | 18.x | Interface utilisateur (5 designs) |
| Base relationnelle | PostgreSQL | 18.2 | Conversations, ratings, fine-tuning |
| Containerisation | Docker + Compose | 26.x / 2.x | Orchestration services |

> **⚠ Changement majeur v5.8.3 vs v5.0** : Nginx **supprimé** de l'architecture. Le frontend est accessible directement sur le port **3000**, le backend sur le port **8000**. Plus simple pour un usage sur réseau local isolé.

> **Note** : cette section a un temps décrit une architecture ChromaDB (expérimentation v5.8.3, voir `_archive/`) qui n'a jamais été celle du code actif — le projet utilise PostgreSQL + pgvector depuis v6.0 (`database.py`, table `rag_chunks`), corrigé ci-dessus pour refléter le code réel.

### 1.3 Variables d'environnement critiques ROCm

Ces variables doivent être définies avant tout import PyTorch sous peine de fallback silencieux en mode CPU.

| Variable | Valeur | Pourquoi critique |
|---|---|---|
| `HSA_OVERRIDE_GFX_VERSION` | `10.1.3` | Force la reconnaissance du Cyan Skillfish (gfx1013) par ROCm |
| `ROCR_VISIBLE_DEVICES` | `0` | Cible le seul GPU BC-250 |
| `PYTORCH_HIP_ALLOC_CONF` | `max_split_size_mb:512` | Limite la fragmentation mémoire GDDR6 |
| `amdgpu.gttsize` + `ttm.pages_limit` + `ttm.page_pool_size` | `14750` / `3959290` / `3959290` (GRUB) | Alloue jusqu'à ~14,5-14,75 Go de GTT — les 3 ensemble, gttsize seul ne suffit pas (plafond ttm par défaut atteint avant, crash driver) |
| `OLLAMA_NUM_PARALLEL` | `1` | Évite la saturation mémoire (1 seule requête LLM à la fois) |
| `OLLAMA_NUM_GPU` | `99` | Nombre de *layers* du modèle chargées sur GPU (PAS le nombre de CUs — 99 = convention Ollama pour "toutes les layers") |
| `OLLAMA_KEEP_ALIVE` | `24h` | Maintient le modèle en VRAM 24h sans rechargement |
| `CORS_ORIGINS` | Configurable `.env` | Origines autorisées — modifiable sans rebuild |

### 1.4 Déblocage 40 CU RDNA2 (optionnel)

Le BC-250 sort d'usine avec **24 des 40 Compute Units RDNA2 actifs** — les 16
restants ne sont pas endommagés, ils sont fusionnés (fused off) en firmware.
Un déblocage communautaire existe (crédit **duggasco**,
[bc250-40cu-unlock](https://github.com/duggasco/bc250-40cu-unlock)), documenté
sur [elektricm.github.io/amd-bc250-docs/system/40cu-unlock](https://elektricm.github.io/amd-bc250-docs/system/40cu-unlock/).

- **Gain mesuré** : ~1.61x en calcul (Vulkan `llama-bench pp512`), gain marginal
  en 3D (déblocage compute, pas gaming).
- **Dans ce projet** : `scripts/unlock-40cu.sh` clone le dépôt communautaire,
  vérifie le *harvest pattern* de la carte, lance l'installeur, vérifie le
  résultat (`dmesg | grep active_cu_number`), et met à jour `.env`
  (`AMD_RDNA2_CUS=40`, `AMD_CU_UNLOCK_APPLIED=true`).
- Proposé comme étape **9/9 optionnelle** dans `install.sh` (confirmation
  demandée avant exécution).
- ⚠️ Pas garanti sur toutes les cartes (harvest pattern dispersé = CUs
  potentiellement défectueux), reconstruit le module `amdgpu` hors-arbre (à
  refaire après chaque MAJ noyau), nécessite un plafond gouverneur à 1500 MHz
  en sustained load pour rester dans une enveloppe thermique raisonnable.
  Réversible via `scripts/unlock-40cu.sh disable` / `restore`.

```bash
./scripts/unlock-40cu.sh          # lance le déblocage (interactif)
./scripts/unlock-40cu.sh verify   # vérifie après reboot
./scripts/unlock-40cu.sh disable  # revient au stock 24 CU
```

### 1.5 BIOS modifié (prérequis IOMMU / VRAM avancé)

Le déblocage `IOMMU=Disabled` (§1.3) et les configurations VRAM au-delà des
3 presets stock (8Go/8Go, 12Go/4Go, 512Mo dynamique) nécessitent le **menu
Chipset étendu**, absent du BIOS stock. Il faut flasher un BIOS communautaire
modifié — documentation complète :
[elektricm.github.io/amd-bc250-docs/bios/flashing](https://elektricm.github.io/amd-bc250-docs/bios/flashing/).

> ⚠️ **Opération à risque de brick.** Une coupure de courant pendant l'écriture
> peut rendre la carte inutilisable sans programmateur matériel (CH347/Pi
> Pico) pour la récupérer. Vérifier le hash SHA256 du fichier avant de flasher,
> et **toujours** clear le CMOS après flash (batterie CR2032 retirée 60s, ou
> cavalier CMOS) — sans quoi les réglages VRAM ne s'appliquent pas.

**Fichier recommandé (99% des cas)** : `BC250_3.00_CHIPSETMENU.ROM`
(SHA256 `48fbe5d366e6a56e2fdffdca848426216ba1f083610dab63db89d2f4e6c940b5`,
sources multiples vérifiées — voir la doc). Ne pas utiliser `P5.00_clv`
(débloque tout, y compris des réglages de debug dangereux) sauf usage avancé
assumé.

**Procédure résumée (méthode USB / EFI Shell — recommandée)** :
1. Clé USB FAT32 ≤32 Go, écran en DisplayPort direct (les adaptateurs HDMI
   actifs/passifs peuvent donner un écran noir au menu BIOS).
2. Télécharger l'outil de flash EFI (`4U12G BIOS Update.zip`, contient
   `AfuEfix64.efi` + `Flash.nsh`) et le ROM modifié ci-dessus.
3. Copier le contenu de `BIOS EFI` à la racine de la clé, renommer le ROM
   modifié en `Robin5.00` (sans extension), garder l'ancien `Robin5.00`
   (BIOS stock) de côté comme sauvegarde.
4. Débrancher tous les disques/SSD, insérer la clé, démarrer — la carte doit
   tomber automatiquement dans l'EFI Shell.
5. Au prompt `Shell>` : `blk0:` (avec l'espace après `:`) puis Entrée,
   `Flash.nsh` puis Entrée. **Ne pas toucher au clavier ni couper
   l'alimentation** — en cas de blocage pendant l'écriture, attendre au
   moins 15 minutes avant toute action.
6. Une fois le flash terminé, éteindre immédiatement et retirer la clé USB.
7. **Clear CMOS** (étape critique, cf. avertissement ci-dessus).
8. Entrer dans le BIOS (touche `Suppr` au démarrage) et configurer :
   `Chipset → GFX Configuration → Integrated Graphics Controller = Forces`,
   `UMA Mode = UMA_SPECIFIED`, `UMA Frame Buffer Size = 512Mo`, puis
   `Advanced → CPU Configuration → IOMMU = Disabled`. `F10` pour sauver.

Récupération en cas de brick : programmateur SPI (WCH CH347 recommandé —
**pas** de programmateur CH341A à PCB noir, sortie 5V qui peut griller la
puce 3,3V), cible le chip `BIOS_A1` (16 Mo, **jamais** `SIO1_R` 512 Ko qui
gère les ventilateurs/capteurs). Détail complet (pinout J4004, commandes
`flashrom`) dans la doc liée ci-dessus, section *Method 2: Hardware
Programmer*.

### 1.6 ROCm (embeddings) vs Vulkan (LLM)

Le gfx1013 n'a pas de binaires rocBLAS officiels — ROCm y est expérimental.
Ce projet utilise donc deux backends GPU différents, par choix :

- **Embeddings** (`backend/api/rag_engine.py`, SentenceTransformer/PyTorch) :
  ROCm si disponible, repli CPU automatique sinon.
- **LLM** (Ollama, Mistral 7B) : **Vulkan (RADV)** — image `ollama/ollama:latest`
  (pas `:rocm`). Ollama tente ROCm au démarrage, échoue proprement sur
  gfx1013, et bascule automatiquement sur Vulkan.

`HSA_OVERRIDE_GFX_VERSION` / `ROCR_VISIBLE_DEVICES` ne sont donc définis que
pour le service `backend`, plus pour `ollama`. Vérifier le backend réel :
```bash
docker compose logs ollama | grep -i "vulkan\|rocm\|gfx1013"
# attendu : library=Vulkan ... description="AMD BC-250 (RADV GFX1013)"
```

---

## 2. Paquets Installés et Versions

### 2.1 Paquets Python Backend (requirements.txt v5.8.3)

| Paquet | Version | Catégorie | Changement vs v5.0 |
|---|---|---|---|
| fastapi | 0.115.0 | API Web | — |
| uvicorn[standard] | 0.30.0 | ASGI Server | — |
| asyncpg | 0.29.0 | PostgreSQL async | Maintenu |
| **chromadb** | **0.4.22** | **Base vectorielle** | **Remplace pgvector** |
| sentence-transformers | 3.0.1 | Embeddings GPU | Modèle changé → BAAI/bge-m3 (1024d) |
| transformers | 4.43.0 | HuggingFace | — |
| torch (ROCm 7.2) | 2.11+ | GPU RDNA2 | — |
| langchain-text-splitters | 0.2.4 | Chunking | CHUNK_SIZE=400, OVERLAP=80 |
| accelerate | 0.33.0 | Entraînement | — |
| peft | 0.12.0 | LoRA adapters | — |
| trl | 0.10.0 | SFTTrainer | — |
| httpx | 0.27.0 | Client HTTP async | — |
| aiofiles | 24.1.0 | I/O async | — |
| pydantic | 2.8.0 | Validation | — |
| pydantic-settings | 2.4.0 | Config | — |
| loguru | 0.7.2 | Logging | — |
| pypdf / PyPDF2 | 3.0.1 | Extraction PDF | — |
| python-docx | 1.1.0 | Extraction DOCX | — |
| python-pptx | 1.0.0 | Extraction PPTX | — |
| openpyxl | 3.1.5 | Extraction XLSX | — |
| openai-whisper | 20240930 | Transcription audio/vidéo | Singleton GPU — chargé 1× |
| scikit-learn | 1.5.0 | ML / eval | — |
| numpy | 1.26.4 | Calcul numérique | — |

### 2.2 Services Docker (docker-compose.yml v5.8.3)

| Service | Nom conteneur | Image | Port exposé |
|---|---|---|---|
| PostgreSQL | prof-ia-postgres-v58 | postgres:15 | 127.0.0.1:5432 |
| Ollama (Vulkan) | prof-ia-ollama-vulkan | ollama/ollama:latest | 127.0.0.1:11434 |
| FastAPI Backend | prof-ia-backend-v58 | Build local Python 3.13 | 0.0.0.0:8000 |
| React Frontend | prof-ia-frontend-v58 | Build local Node 20 | 0.0.0.0:3000 |

> **Nginx absent** : contrairement à v5.0, il n'y a pas de reverse proxy dans cette version. Les ports sont exposés directement. CORS est géré par FastAPI via la variable `CORS_ORIGINS` dans `.env`.

### 2.3 Modèles LLM supportés

| Modèle | VRAM | Vitesse | Usage recommandé |
|---|---|---|---|
| qwen3:14b | ~9,3 Go | Modéré | Modèle par défaut — meilleure qualité générale et multilingue que Mistral 7B (2023) |
| deepseek-r1:7b | ~4,7 Go | Lent (30s-6min, raisonnement CoT) | Analyses profondes, rapports, architectures |

> **⚠** Ne jamais charger les deux modèles simultanément. 9,3 + 4,7 = 14 Go — dépasse le budget 12 Go, planterait le driver.

---

## 3. Architecture ALL-IN-ONE — ChromaDB

### 3.1 Pourquoi ALL-IN-ONE vs collections séparées

**Avec collections séparées (v5.0)** : la question *"Comment sécuriser un pipeline CI/CD ?"* était routée vers DevOps uniquement — manquant toute l'expertise AIS (sécurité) pourtant pertinente.

**Avec ALL-IN-ONE (v5.8.3)** : une seule collection `prof_ia_all` — le RAG trouve automatiquement ce qui est pertinent dans **toute** la base, quelle que soit la formation d'origine.

### 3.2 Structure de la collection prof_ia_all

```
prof_ia_all (~33 000 chunks)
├── TSSR        : ~11 000 chunks  (support technique, réseaux)
├── AIS         : ~16 700 chunks  (cybersécurité, SIEM)
├── DevOps      : ~5 300 chunks   (CI/CD, conteneurs)
└── Transverse  : ~200 chunks     (commandes Linux)
```

### 3.3 Configuration ChromaDB (config.py)

| Paramètre | Valeur | Description |
|---|---|---|
| `CHROMADB_PATH` | `/app/chromadb_data` | Volume bind mount depuis l'hôte |
| `EMBEDDING_MODEL` | `BAAI/bge-m3` | 1024 dimensions — meilleur choix local pour le FR (MTEB 2026) |
| `EMBEDDING_BATCH_SIZE` | `32` | AMD BC-250 : 32 safe (64 risque OOM) |
| `CHUNK_SIZE` | `400` | Mots par chunk |
| `CHUNK_OVERLAP` | `80` | Chevauchement entre chunks |
| `RAG_THRESHOLD` | `0.72` | Seuil similarité cosine (distance ≤ 0.28) |

### 3.4 Endpoints de gestion ChromaDB

| Méthode | Endpoint | Description |
|---|---|---|
| GET | `/datasets/stats` | Répartition par métier (TSSR/AIS/DevOps) |
| GET | `/indexing/status` | Statistiques de la collection RAG |
| POST | `/indexing/directory` | Indexation d'un répertoire complet |
| POST | `/indexing/reset` | Reset complet ChromaDB ⚠ irréversible |

---

## 4. Formats de Fichiers Supportés

Le répertoire d'uploads est monté sous `/app/data/uploads` dans le conteneur backend. Les sous-dossiers sont créés automatiquement au démarrage selon l'extension.

### 4.1 Documents textuels

| Extension | Format | Extracteur v5.8.3 | Qualité |
|---|---|---|---|
| `.pdf` | PDF texte natif | pypdf 3.0.1 | ⭐⭐⭐⭐⭐ Excellent |
| `.docx` | Word 2007+ | python-docx 1.1.0 | ⭐⭐⭐⭐⭐ Excellent |
| `.pptx` | PowerPoint 2007+ | python-pptx 1.0.0 | ⭐⭐⭐⭐ Très bon |
| `.xlsx` | Excel 2007+ | openpyxl 3.1.5 | ⭐⭐⭐⭐ Très bon |
| `.txt` | Texte brut UTF-8 | Built-in Python | ⭐⭐⭐⭐⭐ Parfait |
| `.md` | Markdown | Built-in Python | ⭐⭐⭐⭐⭐ Parfait |

### 4.2 Fichiers audio / vidéo (transcription Whisper)

| Extension | Format | Modèle Whisper | Temps estimé (1h audio) |
|---|---|---|---|
| `.mp4` | Vidéo H.264 | base (145 Mo, fp16 ROCm) | ~10 min sur BC-250 |
| `.mp3` | Audio MPEG | base (145 Mo, fp16 ROCm) | ~8 min sur BC-250 |
| `.wav` | Audio PCM | base (145 Mo, fp16 ROCm) | ~6 min sur BC-250 |

> **⚠** Whisper est un singleton chargé une seule fois au démarrage et réutilisé pour tous les fichiers audio/vidéo. Il libère la VRAM immédiatement après transcription (`torch.cuda.empty_cache()`). Ne pas faire tourner Ollama simultanément pendant une transcription longue.

### 4.3 Endpoints de gestion des documents

| Méthode | Endpoint | Description |
|---|---|---|
| POST | `/documents/upload` | Upload et indexation (multipart/form-data) |
| GET | `/documents/list` | Liste des documents indexés avec métadonnées |
| DELETE | `/documents/{file_id}` | Suppression d'un document et de ses chunks |

---

## 5. RAG — Les 3 Modes de Requête

### 5.1 Comparatif des modes

| Critère | PRÉCIS | EXPLORE | SYNTHÈSE |
|---|---|---|---|
| Chunks récupérés | top-5 | top-12 | top-20 |
| Contexte max Mistral | 8 192 tokens | 8 192 tokens | 16 384 tokens |
| Algorithme | Cosine classique | MMR 70/30 | Multi-Query + MMR |
| Sous-questions générées | 0 | 0 | 3 automatiques |
| Vitesse (Mistral) | 15-30s | 30-60s | 2-6 min |
| Vitesse (DeepSeek) | 30-60s | 1-2 min | 5-10 min |
| Déterministe | Oui — 100% | Quasi (MMR varié) | Non (multi-query) |
| Idéal pour | Commandes, procédures | Concepts, comparaisons | Rapports, analyses |

### 5.2 Configuration RAG (config.py)

```python
# Mode PRÉCIS
RAG_THRESHOLD  = 0.72
RAG_TOP_K      = 5
NUM_CTX        = 8192

# Mode EXPLORE
RAG_TOP_K_EXPLORE  = 12
MMR_LAMBDA         = 0.7    # 70% pertinence / 30% diversité
NUM_CTX_EXPLORE    = 8192

# Mode SYNTHÈSE
RAG_TOP_K_SYNTHESIS  = 20
MULTI_QUERY_COUNT    = 3
MULTI_QUERY_ENABLED  = True
NUM_CTX_SYNTHESIS    = 16384
```

### 5.3 Endpoint /chat

```http
POST /chat
Content-Type: application/json
X-Session-Token: <token>

{
  "message": "Comment configurer un VLAN trunk ?",
  "mode": "précis",        // "précis" | "explore" | "synthèse"
  "model": "qwen3:14b"
}
```

---

## 6. Datasets & Fine-Tuning LoRA

### 6.1 Datasets préchargés (7 sources)

| Dataset | Source | Taille source | Chunks indexés | Métier |
|---|---|---|---|---|
| Tech Support Conversations | Kaggle | ~800 Mo | ~4 500 | TSSR |
| Customer Support Tickets | HuggingFace | ~1,5 Go | ~6 500 | TSSR |
| Linux Terminal Commands | Kaggle | ~45 Mo | ~200 | Transverse |
| Advanced SIEM Dataset | HuggingFace | ~2,8 Go | ~9 200 | AIS |
| Cybersecurity Threat Logs | Kaggle | ~1,9 Go | ~7 500 | AIS |
| AI-Driven CI/CD Pipeline Logs | Kaggle | ~950 Mo | ~3 800 | DevOps |
| DEVOPS Dataset | HuggingFace | ~200 Mo | ~1 500 | DevOps |
| **Total** | | **~8,2 Go source** | **~33 200 chunks** | |

### 6.2 Le Golden Dataset — Comment il se construit

Prof IA v5.8.3 génère automatiquement son corpus d'entraînement à partir des conversations réelles.

| Étape | Mécanisme | Seuil / Critère |
|---|---|---|
| 1. Conversation | L'apprenant pose une question → RAG → LLM génère la réponse | — |
| 2. Auto-évaluation | Score calculé sur 4 critères (pertinence RAG, complétude, citations, style) | Score ≥ 0.85 |
| 3. Marquage Golden | La conversation est marquée `is_golden=true` dans PostgreSQL | automatique |
| 4. Évaluation humaine | Le formateur note de 1 à 5 étoiles via l'interface | Note ≥ 5 ⭐ |
| 5. Export SFT | Formatage JSONL pour entraînement LoRA | 50 exemples minimum |

### 6.3 Critères d'auto-évaluation (config.py)

| Critère | Poids | Mesure |
|---|---|---|
| Pertinence RAG | 25% | Score similarité cosine moyen des chunks (ChromaDB) |
| Complétude | 25% | Longueur réponse entre 50 et 500 mots |
| Factualité | 25% | Présence de citations (« Selon... », « D'après... ») |
| Style | 25% | Absence de marqueurs d'hallucination (« je pense », « probablement ») |

Seuil global : `GOLDEN_THRESHOLD = 0.85` dans config.py

### 6.4 Configuration LoRA optimisée BC-250

| Hyperparamètre | Valeur BC-250 | Explication |
|---|---|---|
| `r` (rang LoRA) | 16 | Compromis qualité/VRAM — r=8 moins précis, r=32 dépasse la VRAM |
| `lora_alpha` | 32 | Facteur d'échelle des adaptateurs (= 2× r) |
| `target_modules` | q_proj, v_proj | Couches d'attention ciblées |
| `lora_dropout` | 0.05 | Régularisation légère |
| `bias` | none | Économise de la VRAM |
| Précision | **fp16** (NON bf16) | RDNA2 = fp16 natif — bf16 non supporté sur Cyan Skillfish |
| `gradient_checkpointing` | True | Réduit la VRAM de ~40% |
| `batch_size` | 1 | Contrainte 12 Go |
| `gradient_accumulation_steps` | 8 | Simule un batch de 8 sans dépasser la VRAM |
| `max_seq_length` | 2048 tokens | Calibré pour la VRAM disponible |

### 6.5 Estimation des temps d'entraînement BC-250

| Taille dataset | Exemples Q/R | Epochs | Durée estimée | Qualité attendue |
|---|---|---|---|---|
| Petit | 100-500 | 3 | 1h-2h | Spécialisation rapide |
| Moyen | 500-2 000 | 3 | 3h-6h | Bonne généralisation TSSR/AIS |
| Grand | 2 000-5 000 | 3 | 8h-16h | Excellent — recommandé prod |
| Golden seul (typique) | 200-800 | 5 | 2h-5h | Très bon — données de qualité |

> **⚠** Arrêter Ollama avant de lancer le fine-tuning (`docker compose stop ollama`) pour libérer ~4,5 Go de VRAM. Le script `train.py` le vérifie automatiquement.

### 6.6 Workflow complet fine-tuning

| Étape | Action | Commande |
|---|---|---|
| 1 | Utiliser Prof IA en production | Interface web → /chat |
| 2 | Auto-évaluation marque les golden conversations | Automatique (score ≥ 0.85) |
| 3 | Vérifier la taille du Golden Dataset | `GET /conversations/stats` |
| 4 | Arrêter Ollama | `docker compose stop ollama` |
| 5 | Lancer le fine-tuning | `cd fine_tuning && python3 train.py` |
| 6 | Convertir LoRA en GGUF | `python llama.cpp/convert-hf-to-gguf.py` |
| 7 | Importer dans Ollama | `ollama create prof-ia-custom -f Modelfile` |
| 8 | Redémarrer Ollama | `docker compose start ollama` |
| 9 | Mettre à jour le modèle actif | `OLLAMA_MODEL=prof-ia-custom` dans `.env` |

---

## 7. Guide par Profil Utilisateur

### 7.1 Étudiant / Utilisateur final

Prof IA tourne entièrement en local — aucune donnée ne sort du réseau.

- **Accès** : `http://192.168.1.11:3000` — login `user` / `user`
- **3 interfaces** : Terminal (Design A), Dashboard (Design B), Minimal (Design C)
- **3 modes RAG** : Précis (rapide), Explore (diversifié), Synthèse (exhaustif)
- **2 modèles** : Mistral 7B (défaut) et DeepSeek R1 7B (à télécharger)
- **Notation** : noter les réponses 1-5 étoiles alimente le dataset de fine-tuning
- **Upload** : ajouter ses propres PDF/DOCX/MP4 directement via l'interface

### 7.2 DevOps — Ce que vous devez savoir

```bash
# Démarrer la stack complète
docker compose up -d

# Logs en temps réel
docker compose logs -f backend

# Vérifier que le GPU AMD est utilisé
docker exec prof-ia-backend-v58 python3 -c \
  "import torch; print('GPU:', torch.cuda.is_available())"

# Backup PostgreSQL
docker exec prof-ia-postgres-v58 \
  pg_dump -U user prof_ia_v5 > backup_$(date +%Y%m%d).sql

# Stats ChromaDB
curl http://localhost:8000/datasets/stats

# Ajouter un PC client (modifier CORS sans rebuild)
nano /home/user/projet_v58/.env
# Ajouter l'IP dans CORS_ORIGINS
docker compose restart backend
```

**Points d'attention v5.8.3** :
- Pas de Nginx — ports 3000 et 8000 exposés directement
- ChromaDB = bind mount (`./chromadb_data`) — sauvegarder avant toute manipulation
- `OLLAMA_KEEP_ALIVE=24h` — le modèle reste en VRAM entre les requêtes
- CORS configurable via `.env` sans rebuild d'image

### 7.3 Administrateur Système — Ce que vous devez savoir

```bash
# GRUB — allouer la VRAM au GPU (gttsize + ttm.* ENSEMBLE, pas gttsize seul)
# /etc/default/grub :
GRUB_CMDLINE_LINUX_DEFAULT="quiet amdgpu.gttsize=14750 ttm.pages_limit=3959290 ttm.page_pool_size=3959290"
update-grub && reboot
# NE JAMAIS ajouter amd_iommu=on — IOMMU cassé sur BC-250 (crashs, écran noir)

# Groupes requis pour /dev/kfd et /dev/dri
usermod -aG video,render user

# Surveillance VRAM en temps réel
sudo radeontop

# Infos VRAM via sysfs
cat /sys/class/drm/card0/device/mem_info_vram_total
cat /sys/class/drm/card0/device/mem_info_vram_used

# Vérification driver AMD
lsmod | grep amdgpu
ls -la /dev/kfd /dev/dri

# Firewall — seuls les ports 3000 et 8000 accessibles depuis le LAN
ufw allow 3000/tcp
ufw allow 8000/tcp
# Ports internes (5432, 11434) en local seulement — ne pas exposer

# Cron backup quotidien ChromaDB
0 3 * * * docker compose -f /home/user/projet_v58/docker-compose.yml stop backend \
  && cp -r /home/user/projet_v58/chromadb_data /mnt/ssd_cours/backup_chromadb_$(date +\%Y\%m\%d) \
  && docker compose -f /home/user/projet_v58/docker-compose.yml start backend
```

**PostgreSQL 18.2 — tuning recommandé BC-250** :

| Paramètre | Valeur | Raison |
|---|---|---|
| `shared_buffers` | 2GB | Cache PostgreSQL principal |
| `effective_cache_size` | 6GB | Estimation cache OS |
| `work_mem` | 256MB | Tri et jointures |
| `max_connections` | 20 | BC-250 : limiter les connexions concurrent |

---

## 8. Architecture Globale — Vue d'ensemble

### 8.1 Flux de données — Requête RAG

```
Navigateur PC Windows (192.168.1.16)
        │  HTTP :3000
        ▼
┌─────────────────────┐
│  React Frontend     │  interface Terminal / Dashboard / Minimal
│  prof-ia-frontend   │  api.js → X-Session-Token header
└──────────┬──────────┘
           │  HTTP :8000
           ▼
┌─────────────────────┐
│  FastAPI Backend    │  Python 3.13 + asyncio
│  prof-ia-backend    │  Authentification + routing
└──────┬──────┬───────┘
       │      │
       │      ▼
       │  ┌──────────────────────┐
       │  │  EmbeddingEngine     │  BAAI/bge-m3 (1024d)
       │  │  sentence-transformers│  GPU RDNA2 — batch_size=32
       │  └──────────┬───────────┘
       │             │  vecteur 384d
       │             ▼
       │  ┌──────────────────────┐
       │  │  ChromaDB            │  collection prof_ia_all
       │  │  prof_ia_all         │  ~33 000 chunks — HNSW index
       │  │  (~3.9 Go sur NVMe)  │  top-5 / top-12 / top-20 chunks
       │  └──────────┬───────────┘
       │             │  chunks + scores
       ▼             ▼
┌─────────────────────────────────┐
│  RAG Engine v5.8.3              │  modes : précis / explore / synthèse
│  MMR + Multi-Query              │  NaN guard, threshold 0.72
└──────────────┬──────────────────┘
               │  prompt + contexte
               ▼
┌──────────────────────┐
│  Ollama              │  Mistral 7B Q4_K_M (~4.5 Go VRAM)
│  prof-ia-ollama-vulkan │  ou DeepSeek R1 7B (~4.7 Go VRAM)
│  GPU RDNA2 24/40 CU  │  OLLAMA_KEEP_ALIVE=24h — 40 CU si unlock-40cu.sh appliqué
└──────────────────────┘
               │  réponse texte
               ▼
┌──────────────────────┐
│  PostgreSQL 18.2     │  Sauvegarde conversation + rating
│  prof-ia-postgres    │  is_golden si score ≥ 0.85
└──────────────────────┘
               │  dataset golden
               ▼
┌──────────────────────┐
│  Fine-Tuning LoRA    │  fine_tuning/train.py
│  PEFT + SFTTrainer   │  fp16, r=16, batch=1, grad_accum=8
└──────────────────────┘
```

### 8.2 Résumé des endpoints (API v5.8.3)

| Méthode | Endpoint | Description |
|---|---|---|
| GET | `/health` | Santé globale (PostgreSQL + ChromaDB + Ollama + GPU) |
| GET | `/services/status` | État de chaque conteneur Docker |
| POST | `/services/{name}/restart` | Redémarrer un service |
| POST | `/services/{name}/stop` | Arrêter un service |
| POST | `/services/{name}/start` | Démarrer un service |
| GET | `/datasets/stats` | Répartition par métier dans ChromaDB |
| POST | `/documents/upload` | Upload et indexation |
| GET | `/documents/list` | Liste des documents indexés |
| DELETE | `/documents/{file_id}` | Suppression d'un document |
| GET | `/indexing/status` | Statistiques de la collection RAG |
| POST | `/indexing/directory` | Indexation d'un répertoire |
| POST | `/indexing/reset` | Reset complet ChromaDB ⚠ |
| POST | `/login` | Authentification (token session 12h) |
| POST | `/logout` | Invalider la session |
| POST | `/chat` | Requête RAG (retrieval + génération) |
| GET | `/chat/history` | Historique des conversations |
| POST | `/chat/{id}/rate` | Notation d'une conversation (1-5 étoiles) |
| GET | `/models/available` | Modèles disponibles dans Ollama |
| POST | `/models/switch` | Changer de modèle LLM actif |

### 8.3 Arborescence du projet

```
/home/user/projet_v58/              ← RACINE DU PROJET
├── docker-compose.yml              ← chef d'orchestre Docker
├── .env                            ← variables (CORS, JWT, modèle...)
├── VERSION                         ← 5.8.3
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt
│   └── api/
│       ├── main.py                 ← TOUS les endpoints FastAPI
│       ├── rag_engine.py           ← moteur RAG ChromaDB v5.8.3
│       ├── config.py               ← paramètres (RAG, GPU, CORS)
│       ├── database.py             ← connexion PostgreSQL
│       └── document_processor.py  ← traitement PDF/DOCX/Whisper
├── frontend/
│   ├── Dockerfile
│   ├── .env                        ← REACT_APP_API_URL
│   └── src/
│       ├── App.js                  ← routeur React
│       ├── pages/Terminal.js       ← interface principale (Design A)
│       ├── pages/Dashboard.js      ← tableau de bord (Design B)
│       ├── pages/Minimal.js        ← interface épurée (Design C)
│       ├── pages/ServiceStatus.js  ← contrôle Docker
│       └── services/api.js         ← tous les appels HTTP
├── chromadb_data/                  ← BASE VECTORIELLE (~3.9 Go)
├── data/uploads/                   ← vos PDF/DOCX/MP4 uploadés
├── scripts/
│   ├── import_datasets.py
│   └── datasets/                   ← 7 datasets source
└── fine_tuning/
    ├── train.py                    ← entraînement PEFT/LoRA
    └── config.yaml                 ← hyperparamètres

/mnt/ssd_cours/                     ← SSD USB EXTERNE
├── TSSR/
├── AIS/
├── DevOps/
├── Transverse/
└── backup_chromadb_*/              ← sauvegardes ChromaDB
```

---

*Document généré le 27 Juillet 2026 — Prof IA v6.0 ALL-IN-ONE pour AMD BC-250 (Cyan Skillfish / RDNA2)*  
*Stack : Debian 13.3 · Kernel 6.18 · Mesa 26.0 · ROCm 7.2 · PyTorch 2.11 · PostgreSQL 18.2 · ChromaDB 0.4.22*
