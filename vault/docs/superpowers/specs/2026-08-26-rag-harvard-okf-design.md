# Spec — Vault LLM Wiki « Harvard IT Teacher » (Modèle 3 : LLM Wiki + RAG)

**Date** : 2026-08-26
**Statut** : v1 — scaffold seul (aucun contenu réel ingesté)
**Auteur** : opencode (Michel Husson)
**Référence** : https://www.glukhov.org/fr/knowledge-management/knowledge-systems-architectures/compiled-knowledge/what-is-llm-wiki/#mod%C3%A8le-3-llm-wiki-plus-rag

## 1. Objectif
Créer, dans `H:\RAG-Harvard-IT-teacher\vault\`, un vault Obsidian de **connaissances
complées** (LLM Wiki) servant de **couche de représentation** dans une architecture
hybride **Modèle 3 (LLM Wiki + RAG)**, combinant :
- le modèle **LLM Wiki (Karpathy)** — https://llmwiki.app
- les principes **OKF** — https://github.com/GoogleCloudPlatform/open-knowledge-format

Le RAG **Prof-IA** (déjà présent à la racine du repo : `backend/` FastAPI + base
vectorielle) fournit la **couche d'accès** et doit récupérer dans les deux sens
(sources brutes + pages compilées).

## 2. Architecture hybride (Modèle 3)
```
sources brutes (vault/raw/ + corpus Prof-IA)
  -> pages LLM Wiki (vault/wiki/)
  -> base de connaissances révisée
  -> index de recherche (RAG Prof-IA)
  -> RAG sur connaissances BRUTES et COMPILÉES
  -> réponse citée
```

## 3. Structure du vault
```
H:\RAG-Harvard-IT-teacher\vault\        <- racine du vault Obsidian (plugin karpathywiki)
├── AGENTS.md          # The Schema (conventions + workflows)
├── log.md             # log de maintenance OKF (chronologique)
├── raw\               # Sources brutes (PDF/MD/...), indexées en place par llmwiki
│   └── .gitkeep
└── wiki\              # Connaissances compilées (générées par llmwiki)
    ├──     index.md       # page synthèse racine (régénérée par le plugin karpathywiki)
    ├── sources\       # 1 page / source ingérée
    │   └── .gitkeep
    ├── entities\      # pages entités (personnes, orgs, produits, events)
    │   └── .gitkeep
    └── concepts\      # pages concepts (méthodes, termes, théories)
        └── .gitkeep
```

## 4. Principe de conception (Modèle 3 — impératifs)
- Garder les sources brutes séparées (`raw/` jamais écrasé).
- Markdown autant que possible (portable, diffable, versionnable).
- Suivre la provenance (chaque page répond « d'où vient cette affirmation ? »).
- Préférer moins de pages, meilleures (pas de page pour chaque idée mineure).
- Rendre les liens significatifs (liens typés, pas aléatoires).
- Marquer l'incertitude (statut explicite sur chaque page).

## 5. Schéma de page (frontmatter OKF)
Format OKF (Google Cloud) = **Markdown + frontmatter YAML** ; les métadonnées YAML sont
l'équivalent JSON structuré. Champs (obligatoire plugin `karpathywiki` : `type:`, `tags:`,
`aliases:` ≥1 ; ajout OKF + Modèle 3) :

- `type` (`concept` | `entity` | `source`), `title`, `description`, `resource` (ex. `raw/tcp-ip.pdf`)
- `status` (`draft` | `stable` | `deprecated`), `stale_after` (date)
- `tags` (liste), `generated` (`by` / `at`), `verified` (`by` / `at`)
- `sources` : **liste d'objets** `{ uri, author, last_modified }` (provenance OKF)
- extension Modèle 3 : `statut` (confiance : `confirme`/`probable`/...), `concepts`, `questions_ouvertes`
- `reviewed` (protection plugin)

Liens : `[[wiki-links]]` Obsidian (graphe + PPR du plugin) = équivalent au graphe de liens
Markdown `[...](...)` de l'OKF.

## 6. Workflows
- **Ingest** : source dans `raw/` → plugin → `wiki/sources/<nom>.md` + MAJ
  `entities/`/`concepts/` + signal contradictions.
- **Bridge RAG** : Prof-IA indexe `wiki/**/*.md` en plus des sources brutes.
- **Query** : question contre le wiki compilé ; bonnes réponses archivées.
- **Lint** : santé du wiki (incohérences, périmés, orphelins, provenance manquante).
- **Révision humaine** (Modèle 3, non négociable) : page `verifie: false` relue
  avant usage comme source de vérité.
- **Maintenance OKF** : chaque action → entrée `log.md`.

## 7. Compatibilité OKF (Google Cloud Open Knowledge Format)
Référence : https://github.com/GoogleCloudPlatform/open-knowledge-format
Chaque page = Markdown + frontmatter YAML aux champs OKF (§5). Le corps Markdown + liens
`[[wiki-links]]` forment le graphe de connaissances. → validé/corrigé en continu par le plugin
**`okf-enforcer`** (MartinForReal, implémente la spec OKF v0.2 Google Cloud), consommable
par un explorer OKF, par Obsidian (Graph View) + plugin `karpathywiki`, et par le RAG vectoriel Prof-IA.

## 8. Hors périmètre (v1)
- Aucun ingest réel (scaffold vide).
- Pas de `.obsidian/` (créé par Obsidian à l'ouverture + activation du plugin).
- Pont PIPE → `raw/` et indexation `wiki/` par le RAG Prof-IA différés.
