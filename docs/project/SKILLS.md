# Méthode de travail — skills mobilisés

Inventaire des compétences utilisées pour le pré-déploiement PROF IA v1.4.
Document de **méthode**, pas de norme : aucune décision d'architecture ne
dépend de ce fichier.

> Source : extrait de `/home/chelmooz/cours/6oct/fait.md` (LEGACY), migré ici
> le 2026-10-06 parce que c'était la seule trace de cet inventaire.

## Processus

| Skill | Phase | Usage |
|---|---|---|
| `brainstorming` | P0 | Design, clarification, registre de décisions |
| `writing-plans` | P0 | Décomposition en tâches TDD |
| `test-driven-development` | T0.-1, P2 | Cycle RED/GREEN/REFACTOR obligatoire |
| `verification-before-completion` | chaque tâche | Preuve par exécution avant commit, jamais d'affirmation |
| `systematic-debugging` | G1 | Debug Vulkan, réseau Docker, OOM |

## Domaine

| Skill | Phase | Usage |
|---|---|---|
| `python-patterns` | P2 | Typing, PEP 8, asyncpg, pydantic v2 |
| `python-testing` | P2 | Fixtures pytest, paramétrage, mocks limités |
| `contract-first` | P2 / P5 | Contrat OpenAPI généré, pas de drift front/back |
| `error-handling` | P2 / P3 | Retries llama, typed errors |
| `domain-modeling` | P2 / P5 | Vocabulaire OKF, chunks, RetrievalPlan, QualityGate |
| `codebase-design` | P2 | Bornes des modules `backend/app/` |
| `benchmark` | G1 / G2 | Baselines tok/s, VRAM, Recall@K |
| `production-audit` | fin | Backups, restauration, readiness |
| `e2e-testing` | P5 | Playwright pour UI chat/wiki |
| `writing-for-agents` | G0 | Rédaction de `AGENTS.md` |
| `setup-matt-pocock-skills` | optionnel | Tracker/triage si des tickets sont publiés |

## Emplacements

| Famille | Chemin |
|---|---|
| Superpowers (processus) | `~/.cache/opencode/packages/superpowers@*/node_modules/superpowers/skills/` |
| Skills domaine | `/home/chelmooz/Work/.agents/skills/` |

## Ce que ces skills ont réellement apporté

Les trois défauts les plus coûteux du chantier ont été trouvés par la
discipline de vérification, pas par la relecture du code :

- **budget mémoire toujours `null`** — `/proc/meminfo` dont la clé
  `MemAvailable:` porte deux-points, jamais appariée.
- **VRAM affichée 11264 au lieu de 11** — octets passés dans un convertisseur
  conceived pour des kB.
- **`grep -q` sous `pipefail`** — faux négatifs sur un `--help` de 59 Ko, que
  le stub de 411 octets ne pouvait pas reproduire.

Les trois auraient produit un rapport **GREEN faux mais crédible**. C'est
précisément ce que la discipline « preuve > affirmation » doit empêcher.