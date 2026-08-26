# SCHEMA — Vault LLM Wiki (`karpathywiki` / OpenCode + Modèle 3 + OKF)

Vault Obsidian de **connaissances compilées auto-maintenues par IA**, exécuté par le plugin
Obsidian **karpathywiki** (green-dalii/obsidian-llm-wiki) branché sur nos **modèles locaux
FREE** (Ollama, endpoint OpenAI-compatible `127.0.0.1:11436`) — **pas de
Claude/cloud**. On s'aligne sur le concept **LLM Wiki (Karpathy)** (réf. lucasastorian/llmwiki),
le **Modèle 3 — LLM Wiki + RAG** et les principes **OKF**. Le vault est **agnostique sur
l'exécuteur** : il peut être maintenu par le plugin Obsidian **karpathywiki** ou par **OpenCode**
(les deux en local, modèles FREE).

> Ce fichier EST « The Schema » : structure, conventions et workflows suivis par l'IA
> et l'humain.
>
> **Exécuteur (IA) — agnostique :** le vault est maintenu en local par l'un (ou plusieurs) des
> moteurs ci-dessous, tous sur nos **modèles FREE** (Ollama, `127.0.0.1:11436`),
> **jamais Claude/cloud** :
> - **Plugin Obsidian `karpathywiki`** (green-dalii) — commands Ingest/Query/Lint, retrieval PPR.
> - **OpenCode** (agentic, local) — lit/écrit le filesystem du vault en suivant ce AGENTS.md.
> lucasastorian/llmwiki = référence *conceptuelle* (même concept Karpathy), pas l'exécuteur.
>
> **OKF enforceur :** le plugin **`okf-enforcer`** (MartinForReal, v0.6.1, Apache-2.0 —
> implémente la spec OKF v0.2 de Google Cloud) valide et corrige automatiquement le
> frontmatter OKF (règle dure : `type` non vide ; v0.2 : `generated`/`verified`, `status`,
> `stale_after`, `sources`). À installer à côté de `karpathywiki` (auto-fix + hooks on-save).

## Modèles & endpoint (local, FREE)
- **Serveur d'inférence** : **Ollama** (OpenAI-compatible ; un seul serveur sert le RAG *et* le vault).
  Récupérer le modèle (BC-250) :
  `ollama pull qwen3:14b`
- **Endpoint** : OpenAI-compatible `http://127.0.0.1:11436/v1` (`WIKI_API_KEY=unused` — keyless).
  L'Ollama docker (service `ollama`, interne `:11434`) est exposé sur l'hôte `:11436` :
  la même instance répond au backend RAG (interne `:11434`) et au vault (hôte `:11436`).
- **Modèle** : `qwen3:14b`
  (Qwen3-14B, quant Q4_K_M, **~9,3 GB**, contexte 8192, Apache-2.0).
  Tient **intégralement en VRAM** sur le BC-250 (~12 Go) → **GPU plein, sans offload partiel**.
- **`num_ctx` (qwen3:14b) — VRAM BC-250** : **1024** pour les ops vault légères (Ingest / petit Query),
  **8192** pour le RAG profond / chat long. Épingler via Modelfile (`PARAMETER num_ctx 8192`).
- **Références BC-250 (source de vérité communautaire)** :
  <https://elektricm.github.io/amd-bc250-docs/> et <https://github.com/akandr/bc250>.

## Position (Modèle 3 : LLM Wiki + RAG)
Ce vault est la **couche de représentation compilée**. Le RAG **Prof-IA** (racine du repo :
`backend/` FastAPI + base vectorielle) est la **couche d'accès** qui récupère dans les deux
sens (sources brutes + pages compilées) :

```
sources brutes (vault/raw/ + corpus Prof-IA)
  -> pages LLM Wiki (vault/wiki/)          <= couche compilée (ce vault, plugin karpathywiki)
  -> base de connaissances révisée
  -> index de recherche (RAG Prof-IA, vectoriel)
  -> RAG sur connaissances BRUTES et COMPILÉES
  -> réponse citée
```

## Format sur disque (plugin karpathywiki — à respecter)
Le vault = un **vault Obsidian** ouvert avec le plugin **karpathywiki**. Le plugin lit vos
notes, appelle le LLM local, et écrit les pages wiki — il ne modifie **jamais** vos notes
sources. Structure générée :

- **`wiki/`** — pages générées (Markdown ordinaire, éditables/maintenables à la main) :
  `wiki/index.md` (synthèse racine, **régénérée** par *Regenerate index*),
  `wiki/sources/`, `wiki/entities/`, `wiki/concepts/`.
- **`.obsidian/plugins/karpathywiki/`** — cache + config du plugin (PDF cache y vit aussi).
  Hors versionning ; jamais source de vérité.

```
vault/                              # racine du vault Obsidian
  raw/                              # sources brutes (PDF/MD/...), déposées par PIPE/Prof-IA — lues en place
  AGENTS.md                         # The Schema (ce fichier)
  log.md                            # log OKF (PROTÉGÉ)
  wiki/                             # GÉNÉRÉ par le plugin (ne pas éditer à la main, sauf révision humaine)
    index.md                        # synthèse racine (régénérée par le plugin)
    sources/  entities/  concepts/  # pages par type
```

Les sources vivent **n'importe où** dans le vault (racine ou `raw/`). Retrieval du plugin =
**Personalized PageRank sur le graphe `[[wiki-links]]`** (sans embeddings, sans vector DB) —
cf. Modèle 3, c'est la couche « représentation » ; le RAG vectoriel Prof-IA est la couche
« accès » séparée.

## Conventions de page
- **Liens / graphe** : `[[wiki-links]]` Obsidian natifs — requis par le plugin `karpathywiki`
  pour son retrieval PPR, et ils forment le **graphe de connaissances** exactement comme les
  liens Markdown `[...](...)` de l'OKF. (On peut aussi écrire `[Cible](Cible.md)` pour une
  compatibilité OKF stricte.)
- **Citations** (attribution de source, mécanisme natif du plugin) : `sources:` en frontmatter
  + mention de la source dans le corps. Les footnotes Obsidian `[^1]` sont tolérées.
- **Frontmatter** : le plugin écrit `type:`, `tags:`, `aliases:` (≥1) sur chaque page ; on
  ajoute (toléré en surplus) les champs OKF + Modèle 3 :

| Champ | Rôle | Origine | Valeurs / exemple |
|---|---|---|---|
| `type` | nature | OKF | `concept` \| `entity` \| `source` (libre) |
| `title` | titre | OKF | `TCP/IP` |
| `description` | résumé 1 ligne | OKF | `Suite de protocoles réseau...` |
| `resource` | emplacement ressource | OKF | `raw/tcp-ip.pdf` |
| `status` | cycle de vie | OKF | `draft` \| `stable` \| `deprecated` |
| `stale_after` | péremption | OKF | `2027-08-26` |
| `tags` | indexation | OKF | `[it, reseau]` |
| `generated` | génération | OKF | `by: "agent:karpathywiki"`, `at: "2026-08-26"` |
| `verified` | vérification humaine | OKF | `by: "human:michel"`, `at: "2026-08-27"` |
| `sources` | provenance (objets) | OKF | `- uri: raw/tcp-ip.pdf`, `author: ...`, `last_modified: ...` |
| `aliases` | alias (≥1, plugin) | karpathywiki | `[Nom Alt]` |
| `reviewed` | protège la page | karpathywiki | `true` |
| `statut` | confiance (extension) | notre extension | `confirme`/`probable`/`conteste`/`depasse`/`a_reviser`/`conflit_source`/`resume_genere` |
| `okf_version` | version OKF (racine) | OKF | `"0.2"` (déclaré dans `wiki/index.md`) |
| `concepts` | concepts clés | Modèle 3 | `[TCP, IP]` |
| `questions_ouvertes` | points non résolus | Modèle 3 | `[...]` |

### Modèle de page (OKF)
```markdown
---
type: concept
title: TCP/IP
description: Suite de protocoles de communication réseau (modèle en couches).
resource: raw/tcp-ip.pdf
status: active
stale_after: 2027-08-26
tags:
  - it
  - reseau
generated:
  by: "agent:karpathywiki"
  at: "2026-08-26"
verified:
  by: "human:michel"
  at: "2026-08-27"
sources:
  - uri: "raw/tcp-ip.pdf"
    author: "Auteur inconnu"
    last_modified: "2026-08-01"
aliases:
  - Transmission Control Protocol / Internet Protocol
statut: confirme
concepts:
  - TCP
  - IP
questions_ouvertes:
  - "Impact VLAN sur la latence ?"
---

# TCP/IP

Résumé fidèle à la source, conservant la structure de l'argument
(problème résolu, hypothèses, compromis, dépendances, incertitudes).

## Relations
- dépend de [[IP]]
- contraste avec [[UDP]]
- exemple de [[VLAN trunk]]

Contradictions : voir [[Source X]] (conflit_source ; source : raw/tcp-ip.pdf).
```

## Maintenance par l'IA locale (modèles FREE, pas Claude)
Deux exécuteurs possibles, sur le **même vault** (format agnostique). Les deux utilisent vos
modèles FREE locaux (Ollama, `127.0.0.1:11436`), **jamais Claude**.

**Option A — Plugin Obsidian `karpathywiki`** (green-dalii), branché sur un LLM local
(Ollama, endpoint OpenAI-compatible ; `WIKI_API_KEY=unused` pour sans-clé).
Commandes principales :

- **Ingest single source / from folder** (= **consolidate**) : extrait entités + concepts,
  écrit `wiki/{sources,entities,concepts}`, fusionne les doublons, signale les contradictions,
  ajoute les `[[liens]]`. C'est l'opération de compilation du LLM Wiki.
- **Query wiki** : chat grounded dans le wiki ; retrieval par **PPR sur le graphe `[[wiki-links]]`**
  (cascade 5 étages : lex → mots-clés LLM → scan local → fallback LLM → expansion PPR).
- **Lint wiki** + **Smart Fix All** : scan santé (doublons, liens morts, pages vides,
  orphelines, aliases manquants, contradictions) + réparation en ordre causal.
- **Regenerate index** : reconstruit `wiki/index.md`.

**Option B — OpenCode** (agentic, local). OpenCode opère directement sur le filesystem du vault
en suivant ce AGENTS.md comme instruction (The Schema) ; il utilise déjà vos modèles FREE
(config omo/opencode). Opérations :
- **consolidate** : lit `raw/`, génère/maj `wiki/{sources,entities,concepts}` + `[[liens]]`
  selon le modèle de page ci-dessus.
- **query** : lit `wiki/` (suit les `[[liens]]` comme un PPR « manuel ») + répond grounded.
- **lint** : scanne liens morts, frontmatter incohérent, doublons, pages orphelines/périmées.

Le format (Markdown + frontmatter + `[[wiki-links]]`) est le **contrat commun** : karpathywiki
et OpenCode produisent/consomment les mêmes fichiers → interchangeables et cohabitables.

### Fonctionne-t-il avec un petit modèle local ? (query / lint / consolidate)
**Oui, les trois opérations tournent en local** (plugin *local-first*, supporte Ollama /
LM Studio / tout endpoint OpenAI-compatible) :
- **Query** ✅ : la cascade est majoritairement locale (lex + scan substring + PPR Monte-Carlo) ;
  le LLM n'intervient que pour ~1–2 appels (mots-clés, génération de réponse). Petit modèle OK.
- **Lint** ✅ : scan déterministe, quasi sans LLM (réparation rule-based). Indépendant du modèle.
- **Consolidate (Ingest)** ✅ : nécessite un modèle qui **suit le schéma d'extraction**
  (qualité d'instruction > taille). Un petit modèle **fine-tuné sur le contenu** (système LoRA
  Prof-IA) est idéal. Caveat : un gros vault (>~2000 pages) veut un contexte long pour l'ingest ;
  mitigations : granularité *Coarse/Minimal*, ingestion par petits batches, ou headless CLI
  (`pnpm llm-wiki ingest --vault … --source …`, keyless local).

Le RAG vectoriel Prof-IA (racine repo) reste la couche d'accès complémentaire (Modèle 3) :
il indexe `wiki/**/*.md` + sources brutes pour le retrieval vectoriel.

## Maintenance autonome
Routine planifiée **locale** (tâche planifiée Windows / cron, ou commande du plugin
karpathywiki) exécutée par notre LLM local (Ollama, modèles FREE) — **pas de
Claude/cloud**. Elle lit le nouveau depuis la dernière exécution (dépôts dans `raw/`, notes,
highlights) et met à jour le wiki. Le wiki **compounds** (se capitalise) dans le temps.

## Trois échelles (LLM Wiki)
- **Personnelle** : seconde cervelle que l'on n'a pas à mettre à jour soi-même.
- **Pour ton IA** : couche de contexte pour que les agents (JARVIS/LLM) appliquent vos modèles mentaux.
- **Institutionnelle** : mémoire organisationnelle auto-maintenue.

## Bridge RAG (Modèle 3)
Le RAG Prof-IA (racine repo) indexe `vault/wiki/**/*.md` **en plus** des sources brutes
→ retrieval sur connaissances brutes ET compilées.

## Lint / hygiène (aligné commande Lint du plugin)
- résolution des citations (attribution → sources présentes)
- liens morts (`[[ ]]` brisés)
- pages orphelines / périmées (`stale_after`, `statut`)
- cohérence frontmatter / aliases manquants / doublons / contradictions

## Compatibilité OKF (Google Cloud Open Knowledge Format)
Chaque page = **Markdown + frontmatter YAML** conforme OKF v0.2 (champs `type`, `title`,
`description`, `resource`, `status`, `stale_after`, `tags`, `generated`, `verified`,
`sources`). Le corps Markdown (+ `[[wiki-links]]`) forme le graphe de connaissances.
→ validé/corrigé en continu par le plugin **`okf-enforcer`** (MartinForReal) ; consommable
par un explorer OKF, par `karpathywiki` (local-first) et par le RAG vectoriel Prof-IA.
`index.md` (avec `okf_version: "0.2"`) + `log.md` complètent le bundle.

## Hors périmètre (v1)
- Scaffold vide, aucun ingest réel.
- Pas de `.obsidian/` (créé par Obsidian à l'ouverture + activation du plugin).
- Pont PIPE → `raw/` et indexation `wiki/` par le RAG Prof-IA différés.
