# Feuille de route — gates G2 et suivantes

Plan de construction **en aval** de G1. Aucun de ces chantiers n'est ouvert : le
maître [`PROF-IA-v1.4-master.md`](../architecture/PROF-IA-v1.4-master.md) reste
la source des états de gate.

> Source : extrait de `/home/chelmooz/cours/6oct/fait.md` (LEGACY), migré ici le
> 2026-10-06. Les tâches T0.\* et T1.\* sont **closes** — voir
> [CHANGELOG.md](CHANGELOG.md). Seules les tâches non commencées sont
> conservées, et les valeurs de modèle périmées ont été retirées.

## G2 — Mémoire réelle et moteur (bloqué par l'accès BC-250)

- [ ] Campagne T0.-1 sur la machine cible, candidat
      `Qwen2.5-7B-Instruct-Q6_K`, contexte 8K, `-ngl 999`
- [ ] Relever : `MemAvailable`, RSS, VRAM, GTT, température, tok/s, OOM, reset
- [ ] Vérifier que `ttm.pages_limit` permet l'offload complet du candidat
- [ ] Décider le noyau Debian 13 : `6.12.111` (stock, « stable fallback »
      BC-250) ou `7.2.6` (backports, hors matrice de validation)
- [ ] Décider Mesa : backports obligatoire, le stock `25.0.x` est sous le
      plancher BC-250 de `25.1`
- [ ] Décider du contexte 8K vs 16K **sur mesure**, pas par anticipation
- [ ] Archiver le rapport de campagne

## G3 — Retrieval (après G2)

- [ ] Schéma : `documents`, `document_chunks` (vector 1024 + `tsvector`),
      `wiki_documents`, `responses`, `response_evaluations`, `human_feedback`
- [ ] Ingestion PDF/DOCX/PPTX/XLSX/TXT/MD, hash SHA-256, provenance conservée
- [ ] Chunking **400 tokens**, overlap 80
- [ ] BGE-M3 CPU, `batch_size` ≤ 4, `vector(1024)`
- [ ] Recherche dense (pgvector) + lexicale (PostgreSQL FTS), fusion **RRF**
- [ ] Reranker `bge-reranker-v2-m3` CPU, `batch_size` ≤ 4
- [ ] Context builder : 5–8 passages, budget de tokens respecté, citations
      traçables

## G4 — OKF v0.2

- [ ] Bundle `knowledge/` : `index.md` avec `okf_version: "0.2"`, `log.md`
- [ ] Frontmatter `type` non vide, `sources`, `status`, `stale_after`
- [ ] Modèle : `raw/` → consolidation → `knowledge/` → validation
- [ ] Git = vérité éditoriale ; PostgreSQL = index opérationnel

## G5 — Laya

- [ ] RetrievalPlan : intent, complexity, mode, scope, `top_k`
- [ ] Quality Gate **déterministe d'abord** : citation présente dans le
      contexte, source traçable, format déclaré
- [ ] Règle fail-closed : information manquante ⇒ jamais `high` ; contexte
      insuffisant ⇒ refus
- [ ] Évaluation sémantique ensuite, ne pouvant pas élever le verdict
- [ ] `confidence_level` : enum `high | medium | low`, jamais un flottant

## G6 — Évaluation hors ligne

- [ ] Golden set à partir des feedbacks humains `is_golden`
- [ ] Harnais par lot : Recall@K, MRR, groundedness — **hors chemin actif**
- [ ] Rapports de régression ; l'évaluateur ne bloque jamais le chat

## G7 — Production locale

- [ ] Compose : PostgreSQL, backend, frontend, Nginx
- [ ] `llama-server` en systemd sur l'hôte, réseau `profia-llama`
- [ ] Readyzness : DB + service + modèles
- [ ] Backups PostgreSQL et du bundle OKF, restauration **testée**
- [ ] Logs et métriques

## Dettes ouvertes avant G2

1. **Branche `prof-ia-v1.4` absente** et **aucun remote** sur le dépôt projet.
2. **ADR-003** affirme `host-gateway` comme solution de nommage ; la mesure
   montre qu'il résout vers `172.17.0.1`, pas vers la passerelle du réseau
   dédié. À relire.
3. Connectivité TCP conteneur→hôte **non concluante** dans l'environnement de
   développement ; à re-tester hors sandbox.
4. Compilation `llama.cpp` avec `-j$(nproc)` a échoué une fois puis réussi en
   sérieux réduit : `scripts/install/install-llama-cpp.sh` utilise `-j$(nproc)`
   et mériterait un garde-fou.