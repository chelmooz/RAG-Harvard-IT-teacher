# PROF-IA v1.4 — Document maître

**Source de vérité unique du projet.** Toute autre affirmation non traçable ici ou
dans `docs/architecture/adr/` est une hypothèse, pas une décision.

- Référence : `2026-10-06`
- Succède à : `docs/legacy/PROF-IA-v1.3-master.html` (**legacy**, ne pas appliquer)
- Dépôt de déploiement : ce dépôt. Le bac d'essai `/work` n'est pas la référence.

## 1. Ce que ce projet est

RAG local pour les métiers IT (TSSR / AIS / DevOps), sur **AMD BC-250**
(16 Go GDDR6 unifiée CPU/GPU, Zen 2 8 cœurs, RDNA2). Tout est local : aucun
appel cloud, aucun secret exposé au navigateur.

Le changement de fond par rapport au projet historique
`RAG-Harvard-IT-teacher` :

| Héritage (legacy) | Cible v1.4 |
|---|---|
| Ollama en conteneur | llama.cpp **hors conteneur**, service systemd |
| Qwen3-14B (Q4_K_M, ~9,3 Go) | **candidat** `Qwen2.5-7B-Instruct` **Q6_K** (6,254 Go) |
| Bazzite | **Debian 13** bare metal |
| Retrieval vectoriel seul | dense + FTS, fusion RRF, reranker |
| Judge + Devil's Advocate | **Laya Quality Gate** (voir ADR-004) |
| vault Obsidian / karpathywiki | bundle **OKF v0.2** (voir ADR-004) |

## 2. Décisions normatives

Chaque ligne est un renvoi à un ADR ou à une preuve établie. Une décision sans
ADR ni preuve n'est pas une décision.

| Sujet | Décision | Source |
|---|---|---|
| OS | Debian 13 bare metal, pas Bazzite | [ADR-001](adr/ADR-001-debian13.md) |
| Moteur LLM | llama.cpp, backend **Vulkan/RADV uniquement**, pas de CUDA | [ADR-002](adr/ADR-002-llama-cpp-vulkan.md) |
| Modèle (candidat) | `bartowski/Qwen2.5-7B-Instruct-GGUF` fichier `Q6_K` | [ADR-002](adr/ADR-002-llama-cpp-vulkan.md) §4 |
| Réseau hôte↔conteneur | réseau dédié `profia-llama` + `host-gateway`, **jamais** `172.17.0.1` | [ADR-003](adr/ADR-003-network-host-gateway.md) |
| Qualité | Laya Quality Gate ; pas de Judge/Devil en chemin actif | [ADR-004](adr/ADR-004-laya-okf.md) |
| Connaissance | OKF v0.2 = format canonique ; Git = vérité éditoriale | [ADR-004](adr/ADR-004-laya-okf.md) |
| Mémoire | **aucun seuil** figé ; tout se mesure | T0.-1, voir §5 |

### États du modèle — à ne pas confondre

| État | Signification | Aujourd'hui |
|---|---|---|
| **candidate** | retenu pour la campagne de qualification pré-déploiement | **Qwen2.5-7B-Instruct Q6_K** |
| **validated** | mesuré sur la machine cible, résultats archivés | aucun modèle |
| **production** | validé puis exploité en service | aucun modèle |

**Candidat principal pour la campagne de qualification pré-déploiement :**
`Qwen2.5-7B-Instruct` **Q6_K** GGUF, source
`bartowski/Qwen2.5-7B-Instruct-GGUF`, fichier `Qwen2.5-7B-Instruct-Q6_K.gguf`
(6,254 Go publiés).

**La validation finale de viabilité sur BC-250 reste une gate de
déploiement.** Voir [ADR-002](adr/ADR-002-llama-cpp-vulkan.md) §4.

## 3. Contraintes non négociables

Ces règles ne se négocient pas en phase ultérieure sans nouvel ADR.

1. **Vulkan, jamais CUDA.** Mesa/RADV compile ses shaders en mémoire exécutable
   (JIT). Le service systemd `profia-llama` ne doit **pas** poser
   `MemoryDenyWriteExecute=true` : cela rend la mémoire ni inscriptible ni
   exécutable et empêche l'initialisation Vulkan. CPU disponible via `-ngl 0`.
2. **Aucune adresse bridge par défaut.** `172.17.0.1` (docker0) n'est pas
   garanti. Le réseau `profia-llama` est déclaré avec un sous-réseau explicite et
   le backend résout l'hôte via `host-gateway`.
3. **Mesurer, ne pas seuiller.** Aucun seuil de débit, de mémoire ou de
   température ne conditionne une décision de production. T0.-1 rend un verdict
   par configuration ; l'exploitation de ces chiffres est une décision humaine.
4. **`confidence_level` est un enum de chaînes** (`high` | `medium` | `low`).
   Aucun score flottant n'est présenté comme une probabilité.
5. **Provenance obligatoire.** Laya ne doit jamais inventer une provenance : une
   citation doit exister dans le contexte fourni et pointer vers une source
   traçable.
6. **Lecture seule pour la caractérisation.** `scripts/benchmark/fit_campaign.sh`
   ne modifie ni TTM, ni kernel, ni voltage, ni CU, ni `/proc`, ni `/sys`.

## 4. Architecture cible

```
React ──Nginx :8080──▶ FastAPI :8000 ──▶ Laya Router ──▶ RetrievalPlan
                                                  │
                          ┌───────────────────────┼──────────────────────┐
                          ▼                       ▼                      ▼
                      BGE-M3            PostgreSQL+pgvector+FTS      knowledge/ (OKF)
                          └───────────────────────┼──────────────────────┘
                                          RRF ──▶ reranker ──▶ top 5–8
                                                    │
                                              Context Builder
                                                    │
                              llama.cpp / Vulkan / RADV (hôte, systemd)
                                                    │
                          Qwen2.5-7B-Instruct Q6_K (candidat)
                                                    │
                                            Laya Quality Gate
                                                    │
                                    réponse + sources + confidence_level
```

- **Hors Docker** : `llama.cpp` (service `profia-llama`) — maîtrise de Vulkan,
  de la mémoire unifiée et de la thermique.
- **Dans Docker** : PostgreSQL/pgvector, FastAPI, React, Nginx.
- `llama-server` n'est **jamais** publié sur un port hôte.

## 5. État de qualification

| Gate | Sujet | État |
|---|---|---|
| T0.-1 | Protocole de caractérisation mémoire | **GREEN** — 76 tests,/scripts promus |
| T0.-1 réel | Campagne du candidat sur BC-250 | **NON LANCÉE** — matériel non qualifié |
| G0 | Documentation, source de vérité | ce document |
| G1 | Plateforme (kernel, Mesa, RADV, CU, thermique) | non ouvert |
| G2 | Mémoire réelle + llama.cpp + modèle candidat | non ouvert |
| G3+ | Retrieval, OKF, Laya, E2E | non ouvert |

**Rien au-delà de T0.-1 n'est établi.** En particulier le budget mémoire réel
ci-dessous est une **hypothèse de conception**, pas une mesure.

## Annexe A — Budget mémoire (hypothèse, NON VALIDÉE)

Conception sur 16 Go unifiés. La seule ligne mesurable sans la machine est la
taille du fichier, publiée par le dépôt GGUF. **Tout le reste est à mesurer.**

| Poste | Cible | Nature |
|---|---|---|
| `Qwen2.5-7B-Instruct-Q6_K.gguf` | **6,254 Go** | taille de fichier publiée — **mesurée chez Bartowski, pas sur la machine** |
| KV cache 8K, `q4_0` | à mesurer | dépend du contexte réel |
| Buffers Vulkan / driver | à mesurer | dépend de Mesa et de l'allocation |
| Runtime llama.cpp | à mesurer | dépend des tenseurs alloués hors fichier |
| OS + services Debian | à mesurer | dépend de l'installation réelle |
| BGE-M3 + reranker | ~3–5 Go RAM | CPU, `batch_size` ≤ 4 |
| PostgreSQL | à mesurer | dépend du volume indexé |

**Le fichier modèle n'est qu'une part du budget.** Additionner 6,25 Go et 16 Go
ne dit rien de la viabilité : il faut tout le reste du tableau.

Contrainte à ne pas oublier : `ttm.pages_limit` plafonne l'espace adressable par
le GPU. **Un TTM inférieur au poids du modèle empêche l'offload complet.** La
valeur effective doit être lue sur la machine ; elle n'est pas fixée ici.

La marge supplémentaire qu'offre Qwen par rapport à Gemma 4 26B IQ3_XS
(6,25 Go contre 12,44 Go) est une **motivation** pour lancer la campagne, pas
une preuve qu'elle aboutira.

Annexe détaillée et historique : `docs/legacy/PROF-IA-v1.3-master.html`.

## Annexe B — Documents hérités

| Document | Statut |
|---|---|
| `docs/legacy/PROF-IA-v1.3-master.html` | **legacy** — patrimoine de migration. Contredit le réseau ; voir bandeau. |
| `RAG-Harvard-IT-teacher` (dépôt séparé) | **patrimoine** — source fonctionnelle de la migration. Non réécrit. |

Dans le legacy, Ollama/Qwen3/Bazzite/Judge apparaissent **uniquement** comme la
source du remplacement. Les y lire comme la cible est une erreur de lecture.