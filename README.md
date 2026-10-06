# PROF-IA v1.4 — RAG Local pour IT (TSSR/AIS/DevOps)

Système RAG 100% local sur AMD BC-250 (16 Go GDDR6 unifiée) : Debian 13 bare metal, llama.cpp (Vulkan/RADV), BGE-M3, reranker, PostgreSQL/pgvector, Laya Quality Gate, OKF v0.2.

> **Source de vérité :** [`docs/architecture/PROF-IA-v1.4-master.md`](docs/architecture/PROF-IA-v1.4-master.md)
> Règles pour agents et humains : [`AGENTS.md`](AGENTS.md)
>
> **Le matériel n'est pas qualifié.** Le budget mémoire, le noyau, Mesa et les
> 40 CU sont des hypothèses à mesurer, pas des acquis.

## Stack

- **LLM** : candidat `Qwen2.5-7B-Instruct` **Q6_K** GGUF (6,254 Go) via llama.cpp + Vulkan/RADV (CPU via `-ngl 0`) — *candidat de qualification, non validé*
- **Historique** : Gemma 4 26B A4B IQ3_XS (12,44 Go) était le candidat initial, écarté au profit de Qwen pour la marge mémoire
- **Embeddings** : BAAI/bge-m3 (1024-d) + bge-reranker-v2-m3
- **Vector DB** : PostgreSQL 16 + pgvector + Full-Text Search (RRF)
- **API** : FastAPI (asyncpg, pydantic v2)
- **Frontend** : React + Nginx reverse proxy
- **Orchestration** : Laya (Router + Quality Gate)
- **Knowledge** : OKF v0.2 (Markdown + YAML frontmatter, git-native)
- **Infra** : Docker Compose (backend/db/frontend/nginx) + llama.cpp systemd sur hôte

## Ce qui existe aujourd'hui

Le dépôt est au stade **pré-déploiement**. Seuls les artefacts suivants sont
présents ; le reste est planifié et **ne doit pas être supposé existant**.

```
PROF IA 6oct/
├── AGENTS.md                      # règles pour agents et humains
├── docs/
│   ├── architecture/
│   │   ├── PROF-IA-v1.4-master.md # source de vérité
│   │   └── adr/                   # une ADR par décision structurante
│   └── legacy/                    # patrimoine v1.3 — NE PAS APPLIQUER
├── knowledge/AGENTS.md            # règles du bundle OKF v0.2
├── deploy/
│   ├── llama/                     # VERSION de llama.cpp à épingler
│   └── systemd/profia-llama.service
└── scripts/
    ├── install/install-llama-cpp.sh
    └── benchmark/                 # T0.-1 (protocole de caractérisation)
```

Non construits : `backend/`, `frontend/`, `docker-compose.yml`,
`pyproject.toml`, `.env.example`. Ils apparaissent au gate G1 et suivants.

## Caractérisation mémoire (T0.-1)

Seule chose exécutable aujourd'hui, et uniquement sur la machine cible :

```bash
# Prérequis : llama.cpp compilé + modèle GGUF en place
sudo ./scripts/benchmark/run_matrix.sh --requests 10
```

`fit_campaign.sh` mesure **une** configuration et rend un verdict par exit
code ; `run_matrix.sh` séquence la matrice. Le protocole est **en lecture
seule** : il ne touche ni TTM, ni noyau, ni voltage, ni CU. Il ne fixe aucun
seuil de débit, de mémoire ou de température. Voir
[`AGENTS.md`](AGENTS.md) pour le contrat de verdict.

## Documentation

| Document | Statut |
|---|---|
| [Master v1.4](docs/architecture/PROF-IA-v1.4-master.md) | **Source de vérité** |
| [ADR](docs/architecture/adr/) | Décisions et leur justification |
| [knowledge/AGENTS.md](knowledge/AGENTS.md) | Règles du bundle OKF v0.2 |
| [v1.3](docs/legacy/PROF-IA-v1.3-master.html) | Legacy — patrimoine de migration |

## Tests

Les 76 tests du protocole T0.-1 vivent dans le bac `/work/profia-t0-1/` :
ils dépendent des stubs GHOST/MONKEY, volontairement absents de ce dépôt.