# AGENTS.md — PROF-IA

Point d'entrée pour tout agent ou humain qui travaille sur ce dépôt.
**Avant d'agir, lire `docs/architecture/PROF-IA-v1.4-master.md`.**

## Hiérarchie documentaire

Seul le premier niveau fait autorité. Un niveau inférieur qui contredit un
niveau supérieur est un défaut, pas une variante.

| Niveau | Emplacement | Autorité |
|---|---|---|
| **1 — Normatif** | `docs/architecture/PROF-IA-v1.4-master.md` | Source de vérité |
| **1 — Décisions** | `docs/architecture/adr/ADR-*.md` | Justifie le maître, ne le remplace pas |
| 2 — Cadre de travail | `knowledge/AGENTS.md` | Règles du bundle de connaissance |
| 3 — Référence | `docs/legacy/` | Patrimoine. **Ne pas appliquer.** |
| 3 — Patrimoine | dépôt `RAG-Harvard-IT-teacher` | Source fonctionnelle de la migration |

## Règles qui ne se négocient pas

1. **Vulkan uniquement, jamais CUDA.** Mesa/RADV écrit ses shaders en mémoire
   exécutable : `MemoryDenyWriteExecute=true` dans un service systemd **casse**
   l'initialisation Vulkan. Ne jamais l'ajouter.
2. **Jamais `172.17.0.1`.** L'adresse du bridge `docker0` n'est pas garantie.
   Utiliser le réseau déclaré `profia-llama` et sa gateway `172.30.50.1`.
   **Pas `host-gateway`** : ce mécanisme résout vers `docker0` (`172.17.0.1`),
   pas vers la gateway du réseau dédié — voir ADR-003.
3. **Mesurer, ne pas seuiller.** Aucun seuil de débit, mémoire ou température ne
   conditionne une décision. `scripts/benchmark/fit_campaign.sh` rend un verdict
   par configuration et **n'encode aucun seuil**.
4. **`confidence_level` est un enum de chaînes**, jamais un flottant présenté
   comme probabilité.
5. **Jamais de provenance inventée.** Une citation doit exister dans le contexte
   fourni et pointer vers une source traçable.
6. **Caractérisation = lecture seule.** Le banc ne modifie ni TTM, ni kernel,
   ni voltage, ni CU, ni `/sys`, ni `/proc`.

## Ce qui n'est pas établi

Le matériel **n'a pas été qualifié**. Ne pas traiter comme acquis :

- le noyau 6.18 (Debian 13 livre 6.12) et Mesa ≥ 25.1 (peut exiger
  backports/experimental) — voir [ADR-001](docs/architecture/adr/ADR-001-debian13.md) ;
- les 40 CU — à qualifier, le dépôt amont du patch noyau ayant été archivé ;
- le budget mémoire réel : 12,44 Go sur 16 Go est une **hypothèse**, pas une
  mesure. Voir l'annexe A du maître.

## État

| Gate | Sujet | État |
|---|---|---|
| T0.-1 | Protocole de caractérisation | GREEN (76 tests) |
| T0.-1 réel | Campagne du candidat sur BC-250 | non lancée |
| G0 | Documentation | ce commit |
| G1+ | Plateforme, mémoire, RAG, OKF, Laya, E2E | non ouverts |

Le backend applicatif n'existe pas encore. Ne pas supposer l'existence de
`docker-compose.yml`, `pyproject.toml`, `.env.example` ou d'un `backend/app/`.

## Le bac `/work` n'est pas la référence

`/work/profia-t0-1/` contient le banc GHOST/MONKEY et les 76 tests. Il sert à
**éprouver** le protocole, pas à définir l'architecture. En cas de divergence,
le maître de ce dépôt l'emporte.