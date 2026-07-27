# Prof IA v5.

## Documentation Technique Complète

### AMD BC-250 · Cyan Skillfish (RDNA2) · ROCm 7.

##### À destination des Web Designers · DevOps · Administrateurs Système


## 1. Caractéristiques de la Stack v5.

#### 1.1 Matériel — AMD BC-250 (Cyan Skillfish)

```
Composant Spécification Impact v
```
```
APU AMD BC- 250 — Cyan Skillfish
(gfx1013)
```
```
Cible d'optimisation principale
```
```
Architecture CPU 6 cœurs × Zen 2 @ ~3,0 GHz asyncio TaskGroup Python 3.
```
```
Architecture GPU 24 Compute Units RDNA2 Batch embeddings, inference
Ollama
```
```
Mémoire 16 Go GDDR6 unifiée (partagée
CPU+GPU)
```
```
Zéro copie PCIe, accès direct
```
```
VRAM allouée 12 Go budget appli (kernel : gttsize=14750+ttm.*=3959290, cf. §GRUB) LLM + embeddings simultanés
```
```
Stockage principal SSD interne OS, Docker, modèles Ollama
```
```
Stockage documents SSD USB 3.0 externe Corpus RAG, uploads, backups
```
```
Réseau 1 GbE / Wi-Fi selon config API REST locale
```
#### 1.2 Stack Logicielle

```
Couche Technologie Version Rôle
```
```
OS Debian GNU/Linux 13.3 (Trixie) Système de base
```
```
Kernel Linux AMD 6.18.10- 1 Pilote amdgpu intégré
```
```
Pilotes GPU Mesa / RADV Vulkan 26.0.0 Rendu + compute ROCm
```
```
Framework IA PyTorch + ROCm 2.11+ / 7.2 Calcul GPU natif RDNA
```
```
Python CPython 3.13 asyncio TaskGroup natif
```
```
LLM Runtime Ollama (image standard, backend Vulkan/RADV — ROCm non fonctionnel sur gfx1013) Latest Vulkan Inference Mistral 7B
```
```
Base vectorielle pgvector (PostgreSQL) 0.8.1 / 18.2 Remplace ChromaDB
```
```
API Backend FastAPI + Uvicorn 0.115.0 / 0.30.0 REST API async
```
```
Frontend React + Tailwind 18.x / 3.x Interface utilisateur
```
```
Proxy Nginx Alpine (latest) Reverse proxy + TLS
```
```
Containerisation Docker + Compose 26.x / 2.x Orchestration services
```
#### 1.3 Variables d'environnement critiques ROCm

```
Ces variables doivent être définies avant tout import PyTorch sous peine de fallback silencieux en mode
CPU.
```
```
Variable Valeur Pourquoi critique
```
```
HSA_OVERRIDE_GFX_VERSION 10.1.3 Force la reconnaissance du Cyan Skillfish
(gfx1013) par ROCm
```
```
ROCR_VISIBLE_DEVICES 0 Cible le seul GPU BC- 250
```
```
PYTORCH_HIP_ALLOC_CONF max_split_size_mb:512 Limite la fragmentation mémoire sur la
GDDR
```
```
amdgpu.gttsize 14750 + ttm.pages_limit=3959290 + ttm.page_pool_size=3959290 (GRUB)
Alloue jusqu'à ~14,5-14,75 Go de GTT sur les 16 Go GDDR6 partagés — les 3
paramètres DOIVENT être posés ensemble (gttsize seul ne suffit pas, le
plafond ttm par défaut peut être atteint avant et faire planter le driver).
L'appli elle-même budgète sur 12 Go (AMD_GTT_SIZE_MB dans config.py), la
marge kernel évite de planter pile à cette limite.
```

```
Variable Valeur Pourquoi critique
```
OLLAMA_NUM_PARALLEL 1 Évite la saturation mémoire (1 seule
requête LLM à la fois)

OLLAMA_NUM_GPU 99 Nombre de LAYERS du modèle chargées sur GPU (PAS le nombre
de CUs — 99 = convention Ollama pour "toutes les layers", cf. FIX BUG#5 dans
rag_engine.py). Le déblocage matériel des CUs (24→40) est indépendant et se
fait au niveau du module amdgpu, voir section "Déblocage 40 CU" ci-dessous et
scripts/unlock-40cu.sh.


## 1.bis Déblocage 40 CU RDNA2 (optionnel)

Le BC-250 sort d'usine avec **24 des 40 Compute Units RDNA2 actifs**. Les 16
restants ne sont pas endommagés : ils sont fusionnés (fused off) en firmware.
Le déblocage est un travail communautaire (crédit **duggasco**,
[bc250-40cu-unlock](https://github.com/duggasco/bc250-40cu-unlock)), documenté
dans [elektricm.github.io/amd-bc250-docs/system/40cu-unlock](https://elektricm.github.io/amd-bc250-docs/system/40cu-unlock/).

**Ce que ça modifie** : deux registres matériels, écrits par le module amdgpu
patché au boot (aucune modification firmware permanente) :

| Registre | Rôle | Stock | Débloqué |
|---|---|---|---|
| `CC_GC_SHADER_ARRAY_CONFIG` | Nombre de CUs annoncé au driver | `0xfff80000` (24) | `0xffe00000` (40) |
| `SPI_PG_ENABLE_STATIC_WGP_MASK` | Où le SPI dispatche les wavefronts | `0x07` | `0x1F` |

**Gain mesuré** (Vulkan `llama-bench pp512`, 1500 MHz) : 230 → 371 tok/s
(**1.61x**), +30 W, +4°C. En 3D, le gain est marginal (+4.4% glmark2) car le
rendu graphique est fill-rate bound, pas CU-bound — c'est un déblocage
compute, pas un déblocage gaming.

**Dans ce projet** : le script `scripts/unlock-40cu.sh` clone le dépôt
communautaire, vérifie votre "harvest pattern" (`cu_map.sh` — certaines cartes
ont des CUs réellement défectueux au-delà des 24 stock), lance l'installeur
Debian/Ubuntu, vérifie le résultat via `dmesg | grep active_cu_number`, puis
met à jour `.env` (`AMD_RDNA2_CUS=40`, `AMD_CU_UNLOCK_APPLIED=true`). C'est
cette variable — pas `OLLAMA_NUM_GPU` — qui pilote le calcul
`PYTORCH_HIP_ALLOC_CONF` et la taille de batch d'embeddings dans
`config.py`/`rag_engine.py`.

**À savoir avant d'activer** :

- Le module amdgpu est reconstruit hors-arbre → à refaire après chaque mise
  à jour du noyau (ou épingler le kernel).
- Toutes les cartes ne se débloquent pas proprement : pattern de fusion
  contigu (CU 0-5 actifs / 6-9 fusionnés, identique sur les 4 shader arrays)
  → généralement propre ; pattern dispersé → CUs potentiellement défectueux,
  prévoir le test de santé par WGP (`bc250-cu-health-test.sh` +
  `bc250-cu-mask.sh`).
- En sustained load à 40 CU / 2 GHz, le radiateur stock throttle (89-107°C
  mesurés sur 10 min). Plafonner le gouverneur à **1500 MHz / 900 mV**
  capture l'essentiel du gain (1.61x) sans problème thermique.
- Secure Boot doit être désactivé, ou le module signé manuellement.
- Réversible : `scripts/unlock-40cu.sh disable` / `restore` reviennent au
  stock 24 CU à partir de la sauvegarde automatique du module d'origine.

## 1.ter ROCm (embeddings) vs Vulkan (LLM) — deux backends GPU différents

Le gfx1013 (Cyan Skillfish) n'a pas de binaires rocBLAS officiels : ROCm y est
expérimental et peu fiable. Ce projet utilise donc **deux chemins GPU
différents selon le composant**, choix délibéré et non un oubli :

| Composant | Backend | Pourquoi |
|---|---|---|
| Embeddings (`rag_engine.py`, SentenceTransformer/PyTorch) | ROCm si dispo, sinon repli CPU automatique | Pas d'alternative Vulkan mûre pour PyTorch/SentenceTransformer ; le volume de calcul (batch d'embeddings) est plus tolérant à un repli CPU que l'inférence LLM interactive. |
| LLM (Ollama, `qwen3:14b`) | **Vulkan (RADV)** | ROCm ne charge pas correctement sur gfx1013 pour l'inférence LLM. Ollama (image `ollama/ollama:latest`, pas `:rocm`) tente ROCm au démarrage, échoue proprement, et bascule automatiquement sur Vulkan — comportement observé et documenté par la communauté BC-250 (projets `akandr/bc250`, `thelamer/bc250-ollama-openwebui`). |

**Conséquence pratique** : `HSA_OVERRIDE_GFX_VERSION` et `ROCR_VISIBLE_DEVICES`
ne doivent être définis QUE pour le service `backend` (embeddings) — plus
pour le service `ollama`, qui n'en a ni besoin ni usage sur Vulkan. Vérifier
le backend réellement utilisé par Ollama au démarrage :
```bash
docker compose logs ollama | grep -i "vulkan\|rocm\|gfx1013"
# doit afficher : library=Vulkan ... description="AMD BC-250 (RADV GFX1013)"
```
Si `ROCm` apparaît à la place de `Vulkan` dans ces logs, l'inférence LLM
tourne sur un chemin non fiable — vérifier la version d'Ollama et de Mesa/RADV.



#### 2.0 Migration embedding : mpnet (768d) → BGE-M3 (1024d)

Le modèle d'embeddings est passé de `paraphrase-multilingual-mpnet-base-v2`
(768 dims, 2021) à **BAAI/bge-m3** (1024 dims, Apache 2.0) — meilleur choix
local pour du retrieval en français d'après les benchmarks MTEB 2026.

⚠️ **Changer de modèle d'embeddings change l'espace vectoriel.** Les vecteurs
768d de l'ancien modèle ne sont ni convertibles ni comparables aux vecteurs
1024d de BGE-M3 — un simple redimensionnement de colonne ne suffit pas.

`database.py` détecte automatiquement l'état au démarrage :
- **Table vide ou inexistante** : correction automatique du schéma
  (`vector(1024)`), rien à faire.
- **Table non vide en 768 dims** : démarrage bloqué avec une erreur
  explicite. Migration manuelle requise :
  ```sql
  DROP INDEX IF EXISTS idx_rag_embedding_hnsw;
  TRUNCATE rag_chunks;  -- les anciens vecteurs sont inutilisables, pas de sauvegarde possible
  ```
  Puis **ré-indexer tous les documents sources** (ré-upload / relance du
  pipeline d'ingestion) — c'est le seul moyen d'obtenir des vecteurs BGE-M3
  cohérents pour les documents déjà connus du système.

#### 2.1 Paquets Python Backend (requirements.txt v5)

```
Paquet Version Catégorie Remplace (v4)
```
```
fastapi 0.115.0 API Web 0.109.
```
```
uvicorn[standard] 0.30.0 ASGI Server 0.27.
```
```
asyncpg 0.29.0 PostgreSQL async psycopg2 + SQLAlchemy
```
```
pgvector 0.3.3 Adaptateur pgvector chromadb
```
```
sentence-transformers 3.0.1 Embeddings GPU 2.3.
```
```
transformers 4.43.0 HuggingFace 4.37.
```
```
torch (ROCm 7.2) 2.11+ GPU RDNA2 2.2.0 (CUDA)
```
```
langchain-text-splitters 0.2.4 Chunking wtpsplit
```
```
accelerate 0.33.0 Entraînement 0.26.
```
```
peft 0.12.0 LoRA adapters 0.8.
```
```
trl 0.10.0 SFTTrainer Trainer HF
```
```
httpx 0.27.0 Client HTTP async 0.26.
```
```
aiofiles 24.1.0 I/O async 23.2.
```
```
pydantic 2.8.0 Validation 2.5.
```
```
pydantic-settings 2.4.0 Config 2.1.
```
```
loguru 0.7.2 Logging 0.7.
```
```
PyPDF2 3.0.1 Extraction PDF 3.0.
```
```
python-docx 1.1.0 Extraction DOCX 1.1.
```
```
python-pptx 1.0.0 Extraction PPTX 0.6.
```
```
openpyxl 3.1.5 Extraction XLSX 3.1.
```
```
openai-whisper 20240930 Transcription audio 20231117
```
```
scikit-learn 1.5.0 ML / eval 1.4.
```
```
numpy 1.26.4 Calcul numérique 1.26.
```
```
datasets 2.21.0 HF Datasets 2.16.
```
```
prometheus-client 0.20.0 Monitoring 0.19.
```
Paquets en rouge = nouveautés v5 ou remplacement majeur.

#### 2.2 Services Système (Docker)

```
Service Image Docker Version Port exposé
```
```
PostgreSQL + pgvector pgvector/pgvector:pg18 18.2 + pgvector 0.8.1 5432
```
```
Ollama (Vulkan) ollama/ollama:latest Latest Vulkan (RADV) 11434
```
```
FastAPI Backend Build local Python 3.13 v5.0.0 8001
```
```
React Frontend Build local Node 20 5.0.0 3000
```
```
Nginx nginx:alpine 1.27+ 8080 (→80)
```

## 3. Fonctions Intégrées à Nginx

Nginx joue le rôle de point d'entrée unique (reverse proxy) pour l'ensemble de la stack Prof IA v5. Il
orchestre le routage, la compression, le cache, la sécurité des en-têtes HTTP et l'exposition des métriques
Prometheus.

#### 3.1 Architecture de routage

```
Route URL Destination interne Fonction
```
```
/ frontend:3000 Interface React (Prof IA)
```
```
/api/* backend:8000 API FastAPI (chat, upload, RAG)
```
```
/api/chat backend:8000/chat Endpoint RAG principal
```
```
/api/documents/* backend:8000/documents/* Upload et indexation
```
```
/api/health backend:8000/health Health check multi-services
```
```
/api/conversations/* backend:8000/conversations/* Logs + dataset golden
```
```
/api/indexing/* backend:8000/indexing/* Gestion de l'index pgvector
```
```
/metrics backend:8000/metrics Métriques Prometheus
```
```
/static/* Cache Nginx local Assets React (CSS, JS, images)
```
#### 3.2 Fonctions de performance

```
▸ Gzip compression (niveau 6) : réduit la taille des réponses JSON de ~70 % sur les longues réponses
RAG
▸ Proxy buffering désactivé pour /api/chat : streaming token-par-token sans latence ajoutée
▸ keepalive_timeout 65s : maintient les connexions TCP ouvertes entre le frontend React et Nginx
▸ Cache statique : assets React mis en cache 30 jours (Cache-Control: public, max-age=2592000)
▸ upstream backend avec keepalive 32 : pool de connexions persistantes vers FastAPI
```
#### 3.3 Fonctions de sécurité

```
En-tête HTTP Valeur Protection
```
```
X-Frame-Options SAMEORIGIN Clickjacking
```
```
X-Content-Type-Options nosniff MIME sniffing
```
```
X-XSS-Protection 1; mode=block XSS basique (legacy)
```
```
Content-Security-Policy default-src 'self' Injection de contenu
```
```
Referrer-Policy strict-origin Fuite de référent
```
```
Permissions-Policy camera=(), microphone=() APIs navigateur non utilisées
```
```
CORS Géré par FastAPI Origines autorisées configurées
```
#### 3.4 Fonctions de monitoring

```
▸ stub_status : expose /nginx_status pour Prometheus
▸ access_log format JSON : compatible avec Loki / Grafana pour l'analyse des temps de réponse
▸ error_log niveau warn : capture les 5xx sans polluer les logs
▸ Rate limiting : limit_req_zone $binary_remote_addr zone=api:10m rate=30r/m sur /api/*
```

#### 3.5 Fonctions spécifiques au BC- 250

```
Le BC-250 n'a pas de NIC 10 GbE — les timeouts sont calibrés pour USB 3.0 et réseau local 1 GbE.
```
```
▸ proxy_read_timeout 300s : délai étendu pour les requêtes Ollama longues (génération LLM 7B)
▸ client_max_body_size 500M : supporte les gros fichiers depuis le SSD USB 3.0 externe
▸ proxy_pass_header X-Request-ID : trace-id unique pour corréler les logs Nginx ↔ FastAPI
```

## 4. Formats de Fichiers Supportés (SSD USB 3.0)

Le SSD externe branché en USB 3.0 sur le BC-250 est monté sous /app/data/uploads. Tous les fichiers y
sont lus, traités (extraction de texte, chunking, embeddings), puis indexés dans pgvector. La vitesse de
lecture USB 3.0 (400-500 Mo/s) ne crée aucun goulot d'étranglement pour les documents courants.

#### 4.1 Documents textuels

```
Extension Format Extracteur v5 Qualité extraction
```
```
.pdf PDF (texte natif) PyPDF2 3.0.1 ⭐⭐⭐⭐⭐ Excellent
```
```
.pdf (scanné) PDF image Pytesseract + Pillow (optionnel) ⭐⭐⭐ Bon (OCR)
```
```
.docx Word 2007+ python-docx 1.1.0 ⭐⭐⭐⭐⭐ Excellent
```
```
.pptx PowerPoint 2007+ python-pptx 1.0.0 ⭐⭐⭐⭐ Très bon
```
```
.xlsx Excel 2007+ openpyxl 3.1.5 (read_only) ⭐⭐⭐⭐ Très bon
```
```
.txt Texte brut UTF- 8 Built-in Python ⭐⭐⭐⭐⭐ Parfait
```
```
.md Markdown Built-in Python ⭐⭐⭐⭐⭐ Parfait
```
```
.csv CSV (tabular) Pandas (ajout prévu) ⭐⭐⭐ En développement
```
#### 4.2 Fichiers audio / vidéo (transcription Whisper)

```
Extension Format Modèle Whisper Temps estimé (1h audio)
```
```
.mp3 Audio MPEG base (145 Mo, fp16 ROCm) ~8 min sur BC- 250
```
```
.wav Audio PCM base (145 Mo, fp16 ROCm) ~6 min sur BC- 250
```
```
.mp4 Vidéo H.264 base — extraction audio via
ffmpeg
```
```
~10 min sur BC- 250
```
```
.m4a Audio AAC base — via ffmpeg ~8 min sur BC- 250
```
```
.ogg Audio Ogg Vorbis base — via ffmpeg ~8 min sur BC- 250
```
```
⚠ Le modèle Whisper est chargé à la demande et libère la VRAM immédiatement après transcription
(torch.cuda.empty_cache()). Ne pas faire tourner Ollama simultanément pendant une transcription longue.
```
#### 4.3 Contraintes SSD USB 3.

```
Paramètre Valeur Impact
```
```
Débit lecture USB 3.0 400 – 500 Mo/s Pas de goulot pour docs < 500 Mo
```
```
Débit écriture USB 3.0 200 – 300 Mo/s Upload de fichiers rapide
```
```
Taille max par fichier 500 Mo (Nginx) Paramètre ajustable dans nginx.conf
```
```
Formats en liste noire Aucun Tous les formats listés sont acceptés
```
```
Formats propriétaires .doc Non natif Convertir en .docx avec LibreOffice avant
```
```
PDF protégé par mot de
passe
```
```
Non supporté Retirer la protection avant upload
```

## 5. Datasets & Fine-Tuning LoRA sur BC- 250

#### 5.1 Le Golden Dataset — Comment il se construit

Prof IA v5 ne part pas d'un dataset externe figé. Il génère automatiquement son propre corpus
d'entraînement à partir des conversations réelles avec les apprenants TSSR / AIS / DevOps.

```
Étape Mécanisme Seuil / Critère
```
```
1.
Conversation
```
```
L'apprenant pose une question → RAG récupère les
chunks → LLM génère la réponse
```
###### —

2. Auto-
évaluation

```
Score calculé sur 4 critères (pertinence RAG,
complétude, citations, style)
```
```
Score ≥ 0.
```
3. Marquage
Golden

```
La conversation est marquée is_golden=true dans
PostgreSQL
```
```
is_golden = true
```
4. Évaluation
humaine

```
Le formateur note de 1 à 5 via l'interface (optionnel) Note humaine ≥ 4
```
5. Export
SFT

```
Formatage Alpaca : Instruction / Entrée RAG /
Réponse idéale
```
```
Format JSON / JSONL
```
#### 5.2 Critères d'auto-évaluation

```
Critère Poids Mesure
```
```
Pertinence RAG 25 % Score de similarité cosine moyen des chunks récupérés (pgvector)
```
```
Complétude 25 % Longueur de réponse entre 50 et 500 mots
```
```
Factualité 25 % Présence de citations (« Selon... », « D'après... »)
```
```
Style 25 % Absence de marqueurs d'hallucination (« je pense », « probablement
»)
```
#### 5.3 Datasets HuggingFace compatibles (optionnels)

En complément du Golden Dataset interne, vous pouvez pré-charger des datasets publics pour le domaine
TSSR / réseau / DevOps :

```
Dataset HuggingFace Taille Domaine Commande
```
```
databricks/dolly-15k (fr) 15 000 ex. Général technique
FR
```
```
datasets.load_dataset(...)
```
```
Open-Platypus 24 000 ex. Raisonnement STEM datasets.load_dataset(...)
```
```
teknium/openhermes-2.5 1 M ex. Instruction
généraliste
```
```
datasets.load_dataset(...)
```
```
iamtarun/python_code_instructions 110 000 ex. Python / DevOps datasets.load_dataset(...)
```
```
Golden Dataset interne Variable TSSR / AIS / DevOps
FR
```
```
asyncpg direct (PostgreSQL
18.2)
```
#### 5.4 Mécanisme LoRA sur BC- 250

Le fine-tuning utilise la méthode LoRA (Low-Rank Adaptation) qui gèle les poids du modèle de base et
n'entraîne que de petites matrices de rang réduit. Sur le BC-250 avec 12 Go de VRAM disponible, la
configuration optimale est :


```
Hyperparamètre LoRA Valeur BC- 250 Explication
```
```
r (rang LoRA) 16 Compromis qualité / VRAM — r=8 moins
précis, r=32 dépasse la VRAM
```
```
lora_alpha 32 Facteur d'échelle des adaptateurs (= 2× r)
```
```
target_modules q_proj, v_proj Couches d'attention ciblées — suffisant pour
90 - 95 % qualité
```
```
lora_dropout 0.05 Régularisation légère
```
```
bias none Pas de biais entraîné — économise de la
VRAM
```
```
Précision fp16 (NON bf16) RDNA2 = fp16 natif — bf16 non supporté sur
Cyan Skillfish
```
```
gradient_checkpointing True Réduit la VRAM de ~40 % au prix d'un recalcul
partiel
```
```
batch_size 1 Contrainte 12 Go — accumuler 8 gradients
équivaut à batch=
```
```
gradient_accumulation_steps 8 Simule un batch de 8 sans dépasser la VRAM
```
```
max_seq_length 2048 tokens Calibré pour la VRAM disponible
```
#### 5.5 Estimation du temps d'entraînement sur BC- 250

```
Référence benchmarks 2025 : Mistral 7B fp16 LoRA sur GPU de 24 CUs RDNA2 avec 12 Go VRAM
alloués, batch=1, grad_accum=8, max_seq=2048.
```
```
Taille dataset Nb exemples Q/R Epochs Durée estimée BC- 250 Qualité attendue
```
```
Petit 100 – 500 3 1h – 2h Spécialisation rapide,
résultats corrects
```
```
Moyen 500 – 2 000 3 3h – 6h Bonne généralisation
domaine TSSR/AIS
```
```
Grand 2 000–5 000 3 8h – 16h Excellent —
recommandé pour
prod
```
```
Très grand 5 000–10 000 2 16h – 32h Optimal — lancer en
overnight
```
```
Golden seul
(typique)
```
```
200 – 800 5 2h – 5h Très bon — données
de qualité
```
Ces estimations sont basées sur un throughput d'environ 150-250 tokens/s pour le forward pass fp16 sur les
24 CUs RDNA2, avec un overhead de 30 % lié au gradient checkpointing ROCm.

```
⚠ Arrêter Ollama (systemctl stop ollama) avant de lancer le fine-tuning pour libérer ~4,5 Go de VRAM. Le
script train.py le vérifie automatiquement.
```
#### 5.6 Workflow complet de fine-tuning par Q/R

```
Étape Action Commande / Outil
```
```
1 Utiliser Prof IA en production avec les
apprenants
```
```
Interface web → /chat
```
```
2 Laisser l'auto-évaluation marquer les
Golden conversations
```
```
Automatique (score ≥ 0.85)
```

Étape Action Commande / Outil

3 Valider manuellement les meilleures
réponses (optionnel)

```
POST /conversations/{id}/evaluate
```
4 Vérifier la taille du Golden Dataset GET /conversations/stats

5 Arrêter Ollama systemctl stop ollama

6 Lancer le fine-tuning cd fine_tuning && python train.py

7 Convertir le modèle LoRA en GGUF llama.cpp convert-hf-to-gguf.py

8 Importer dans Ollama ollama create prof-ia-tssr -f Modelfile

9 Redémarrer Ollama avec le nouveau
modèle

```
systemctl start ollama
```
10 Mettre à jour OLLAMA_MODEL dans
.env

```
OLLAMA_MODEL=prof-ia-tssr
```

## 6. Guide par Profil Utilisateur

#### 6.1 Web Designer — Ce que vous devez savoir

Interface, styles et composants React de Prof IA v5.

```
▸ Frontend : React 18 + Tailwind CSS 3 — composants dans frontend/src/
▸ 5 pages disponibles : Chat, Upload, Indexation, Statistiques, Paramètres
▸ API URL configurable : REACT_APP_API_URL=http://localhost:80 01
▸ Streaming des réponses : l'API /chat supporte Server-Sent Events pour afficher les tokens
progressivement
▸ Thème personnalisable : modifier tailwind.config.js pour adapter les couleurs aux formateurs
▸ Accessibilité : ajouter aria-labels sur les composants de chat pour WCAG 2.1 AA
▸ Déploiement : npm run build → Nginx sert le build statique depuis /app/build
```
```
Le web designer n'a pas besoin de toucher au backend Python. Toute la personnalisation visuelle se fait
dans frontend/src/ avec Hot Reload activé via Docker volumes.
```
#### 6.2 DevOps — Ce que vous devez savoir

Orchestration, monitoring et CI/CD de la stack BC-250.

```
▸ Stack 100 % Docker Compose : un seul docker compose up -d démarre tout
▸ Health checks : PostgreSQL (/pg_isready), Ollama (/api/tags), Backend (/health)
▸ Secrets : utiliser .env (jamais hardcodé) — POSTGRES_PASSWORD, JWT_SECRET,
CHROMA_AUTH
▸ Backups automatiques : pg_dump depuis le conteneur PostgreSQL vers le SSD USB 3.
▸ Prometheus : métriques exposées sur /metrics (latence RAG, tokens générés, GPU usage)
▸ Logs centralisés : Loguru → fichiers JSON dans /app/data/logs — compatible Loki
▸ Rolling update : modifier le tag d'image dans docker-compose.yml + docker compose pull && up -d
▸ Alertes GPU : surveiller HSA_OVERRIDE_GFX_VERSION — si absent, le backend tourne en CPU
```
```
# Commandes DevOps essentielles BC- 250
docker compose up -d # Démarrer la stack
docker compose logs -f backend # Logs en temps réel
docker exec -it prof-ia-backend-v5 python -c "import torch;
print(torch.cuda.is_available())"
docker compose exec postgres pg_dump -U prof_ia prof_ia_v5 > backup_$(date
+%Y%m%d).sql
```
#### 6.3 Administrateur Système — Ce que vous devez savoir

Configuration système Debian 13.3 pour le BC-250.

```
▸ GRUB : ajouter amdgpu.gttsize=14750 ttm.pages_limit=3959290 ttm.page_pool_size=3959290 à GRUB_CMDLINE_LINUX_DEFAULT + update-grub (les 3 ensemble, pas gttsize seul)
▸ Groupes utilisateur : sudo usermod -aG video,render $USER (requis pour /dev/kfd et /dev/dri)
▸ Service Ollama : /etc/systemd/system/ollama.service — Vulkan (RADV), pas de HSA_OVERRIDE_GFX_VERSION (ROCm inutilisé sur ce service)
▸ PostgreSQL 18.2 : shared_buffers=2GB, effective_cache_size=6GB, work_mem=256MB
▸ SSD USB 3.0 : monter avec options noatime,nodiratime pour réduire les écritures inutiles
▸ Swap désactivé recommandé : swapoff -a (la GDDR6 unifiée gère mieux sans swap)
▸ Firewall : ufw allow 8080/tcp (Nginx) — ports 5432, 11434, 8001 en local seulement
▸ Cron backup : 0 3 * * * docker exec prof-ia-postgres pg_dump ... >> /mnt/usb/backups/
```

▸ Surveillance VRAM : rocm-smi (si installé) ou cat /sys/class/drm/card0/device/mem_info_vram_used

```
# Vérification complète santé BC- 250
cat /sys/class/drm/card0/device/mem_info_vram_total # VRAM totale
cat /sys/class/drm/card0/device/mem_info_vram_used # VRAM utilisée
lsmod | grep amdgpu # Driver chargé
ls -la /dev/kfd /dev/dri # Devices GPU
```

## 7. Architecture Globale — Vue d'ensemble

Le schéma ci-dessous représente le flux de données complet depuis la requête de l'apprenant jusqu'à la
réponse RAG enrichie, avec la boucle de fine-tuning.

```
Composant Technologie Connexion Rôle dans le flux RAG
```
```
Navigateur apprenant React 18 HTTP → Nginx:8080 Interface de saisie de
questions
```
```
Nginx nginx:alpine → Frontend:3000 /
Backend:
```
```
Routage, cache,
sécurité
```
```
FastAPI Backend Python 3.13 + asyncio → PostgreSQL +
Ollama
```
```
Orchestration RAG
```
```
EmbeddingEngine SentenceTransformer
fp
```
```
RDNA2 (24 CUs) Vectorisation batch
GPU
```
```
pgvector (PostgreSQL) pg 18.2 + pgvector 0.8.1 asyncpg (socket UNIX) Stockage + recherche
HNSW
```
```
Ollama Mistral 7B Q4_K_M HTTP localhost:11434 Génération de réponse
LLM
```
```
SSD USB 3.0 Stockage documents Mount
/app/data/uploads
```
```
Corpus documentaire
```
```
Golden Dataset PostgreSQL +
SFTTrainer
```
```
asyncpg →
fine_tuning/train.py
```
```
Amélioration continue
```
Document généré le 16 Février 2026 — Prof IA v5.0 pour AMD BC-250 (Cyan Skillfish / RDNA2)

Stack : Debian 13.3 · Kernel 6.18 · Mesa 26.0 · ROCm 7.2 · PyTorch 2.11 · PostgreSQL 18.2 · pgvector
0.8.


