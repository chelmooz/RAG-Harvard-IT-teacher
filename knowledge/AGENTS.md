# knowledge/AGENTS.md — Bundle de connaissance

Règles du bundle de connaissance PROF-IA.

Le format canonique est **OKF v0.2** (Markdown UTF-8 + frontmatter YAML,
versionné en Git). Voir
[ADR-004](../docs/architecture/adr/ADR-004-laya-okf.md) et la
[spécification OKF](https://okf.md/spec/).

## Règle de séparation

| Support | Rôle |
|---|---|
| `raw/` | sources brutes, **jamais** modifiées, non versionnées |
| `knowledge/` | connaissance éditoriale canonique, versionnée en Git |
| PostgreSQL | **index opérationnel** de `knowledge/`, jamais sa source |

Indexer `knowledge/` dans PostgreSQL ne le remplace pas. Si une affirmation ne
vit que dans la base, elle n'est pas encore de la connaissance : elle n'a ni
provenance Git, ni statut, ni cycle de vie.

## Anatomie attendue

```
knowledge/
├── index.md          ← okf_version: "0.2" déclaré ici, et seulement ici
├── log.md            ← journal, entrées "## YYYY-MM-DD"
├── concepts/
├── howtos/
├── references/
├── decisions/
└── sources/
```

## Frontmatter

- `type` : non vide. Règle de conformité principale d'OKF.
- `sources` : provenance. Une affirmation sans source traçable est une
  affirmation non établie.
- `status`, `stale_after` : signaux de confiance. Ce sont des **métadonnées**,
  pas des conditions de validité — un consommateur les pèse, il ne les refuse pas.

## Interdits

1. **Ne pas inventer de provenance.** Si la source est inconnue, l'écrire. Un
   `sources:` vide vaut mieux qu'une source plausible mais fausse.
2. **Ne pas transformer OKF en JSON.** Les contrats API *déclarent* le format :

   ```json
   "knowledge_format": "OKF",
   "knowledge_format_version": "0.2"
   ```

3. **Ne pas indexer avant d'avoir validé.** Le passage `raw/ → knowledge/` est
   éditorial ; l'indexation est une étape suivante et optionnelle.

## Provenance du schéma

Le schéma dérive du `vault/AGENTS.md` du dépôt historique (Modèle 3
LLM Wiki + principes OKF). **Ce schéma historique est conservé comme
patrimoine mais n'est pas la cible** : il prescrit Ollama et Qwen3-14B comme
moteurs locaux, ce qui est caduc (voir ADR-002). Ce que l'on en garde est la
discipline de provenance, pas l'outillage.