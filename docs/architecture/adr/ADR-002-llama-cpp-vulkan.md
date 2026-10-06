# ADR-002 — llama.cpp hors conteneur, Vulkan/RADV

**Statut :** accepté · **Date :** 2026-10-06 · **Remplace :** Ollama en conteneur, Qwen3-14B

> Cette ADR fixe le **moteur**, le **backend** et le **mode d'exécution**, qui sont
> des décisions de structure. Le **modèle** est une décision distincte, révisable
> sans toucher au reste : voir §4 et le maître.

## Contexte

Le projet historique exécute **Ollama** dans Docker et sert **Qwen3-14B**
(Q4_K_M, ~9,3 Go) via l'API OpenAI sur `:11436`.

Deux propriétés du matériel pèsent lourd :

1. **16 Go de GDDR6 unifiée** CPU/GPU. Un modèle de 12 Go en occupe ~75 % avant
   tout le reste (noyau, RAG, base, embeddings, reranker).
2. RDNA2 / gfx1013 : la documentation BC-250 décrit ROCm sur cette cible comme
   expérimental et incomplet, et recommande Vulkan pour llama.cpp.

## Décision

1. **Moteur** : `llama.cpp`, compilé avec `-DGGML_VULKAN=ON -DLLAMA_CURL=ON`.
2. **Backend GPU** : **Vulkan/RADV exclusivement.** Aucune dépendance CUDA.
   Repli CPU disponible par `-ngl 0`.
3. **Exécution** : **hors conteneur**, service systemd `profia-llama`.
4. **Modèle** : traité séparément, voir §4 ci-dessous.
5. **Paramètres de départ** : `-c 8192 -ctk q4_0 -ctv q4_0 -fa on -b 512 -ub 512
   -np 1 --jinja`. Ce sont des **points de départ à mesurer**, pas des valeurs
   garanties.

## 4. Modèle candidat

Le modèle **n'est pas** fixé par cette ADR. Trois états sont à ne pas confondre :

| État | Signification |
|---|---|
| **candidate** | retenu pour la campagne de qualification pré-déploiement |
| **validated** | mesuré sur la machine cible, résultats archivés |
| **production** | validé puis exploité en service |

Candidat actuel pour la campagne de qualification :

| Champ | Valeur |
|---|---|
| Modèle | `Qwen2.5-7B-Instruct` |
| Quantification | `Q6_K` |
| Format | GGUF |
| Source | `bartowski/Qwen2.5-7B-Instruct-GGUF` |
| Fichier | `Qwen2.5-7B-Instruct-Q6_K.gguf` |
| Taille publiée | **6,254 Go** (5,825 GiB) |

Historique : **Gemma 4 26B A4B IQ3_XS** (12,44 Go) avait été retenu comme
candidat initial. Il a été écarté au profit de Qwen2.5-7B Q6_K pour la marge
mémoire supplémentaire — ce qui est une **motivation**, pas une preuve.

> Le passage de `candidate` à `validated` exige une mesure réelle sur BC-250.
> Rien dans ce dépôt ne permet de l'affirmer aujourd'hui.

## Justification

- **Vulkan plutôt que CUDA** : CUDA n'est pas disponible sur RDNA2 ; forcer un
  chemin HIP pour llama.cpp sur gfx1013 ajoute un risque et un support non garanti. Le chemin Vulkan est celui que la communauté BC-250 documente.
- **Hors conteneur** : sur une machine dont la contrainte principale est la
  mémoire unifiée, un interposer entre llama.cpp et le pilote Vulkan n'apporte
  pas de valeur et coûte en observabilité. Le reste de la pile reste conteneurisé.
- **`-np 1`** : une requête à la fois. `-np > 1` multiplierait les KV caches
  sans budget mémoire pour les justifier.

## Conséquences et risques

- **`MemoryDenyWriteExecute=true` est proscrit** dans le service systemd : Mesa
  compile ses shaders en mémoire exécutable (JIT), et cette directive rend la
  mémoire ni inscriptible ni exécutable. L'initialisation Vulkan échoue.
- **Le budget mémoire n'est pas garanti, même avec le candidat Qwen.** Le
  fichier de 6,25 Go n'est qu'une **part** du budget : runtime, KV cache
  (dépendant du contexte), allocations Vulkan, buffers, surcoûts noyau et
  fragmentation s'y ajoutent. Une marge plus large rend la campagne plus
  plausible ; elle ne la prouve pas. `ttm.pages_limit` plafonne en outre
  l'espace adressable par le GPU : si le plafond est inférieur au poids du
  modèle, l'offload complet est impossible.
  → Qualifié au gate **G2** par campagne T0.-1, jamais supposé.
- Les 40 CU sont **à qualifier**, pas acquis : le dépôt amont du patch noyau
  d'unlock a été archivé le 17/09/2026. La route UMR runtime déjà présente dans
  l'historique en est indépendante, ce qui la rend préférable.
- ROCm reste **optionnel** et non décidé : il ne sera considéré que si une
  mesure montre un gain réel pour embeddings/reranker sans dégrader la stabilité.