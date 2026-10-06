# ADR-004 — Laya Quality Gate et OKF v0.2 : ce qui remplace Judge et le vault

**Statut :** accepté · **Date :** 2026-10-06 · **Remplace :** Judge + Devil's Advocate (§14 v1.3) et le vault Obsidian/karpathywiki

## Contexte — l'évaluation

Le projet historique enchaîne deux évaluateurs LLM sur la réponse produite :
un **Judge** (fidélité, pertinence) puis un **Devil's Advocate** (affirmations
non supportées). Deux passages du même modèle local pour juger la sortie d'un
premier passage.

Trois problèmes :

1. **Coût.** Sur 16 Go unifiés où le modèle occupe la majeure partie de la
   mémoire, un second passage de génération n'est pas gratuit — et le reranker,
   lui, tourne déjà avant la génération.
2. **Défaillance silencieuse.** Si l'avocat plante, un implémentation naïve peut
   laisser passer une réponse non vérifiée : l'échec de l'évaluateur devient un
   PASS.
3. **Confusion d'identité.** Juger une réponse avec un LLM et, dans la même
   respiration, l'appeler « qualité », masque le fait que la citation — seule
   partie vérifiable — n'est pas réellement vérifiée.

## Contexte — la connaissance

Le vault est un dépôt Obsidian annoté par le plugin `karpathywiki`, avec un
`AGENTS.md` qui prescrit **Ollama** et **Qwen3-14B** comme moteurs locaux. C'est
une dépendance d'outillage qui décrit l'ancienne architecture.

## Décision — évaluation

**Laya Quality Gate est l'unique juge en chemin actif.**

1. Le Quality Gate est **déterministe d'abord** : une citation existe-t-elle
   dans le contexte fourni ? la source est-elle traçable ? le format déclaré
   est-il bien celui du document ? Ce sont des contrôles, pas des appréciations.
2. L'évaluation **sémantique** par modèle, si elle existe, intervient ensuite et
   **ne peut pas élever** le verdict au-dessus de ce qu'autorisent les contrôles
   déterministes.
3. **Règle fail-closed** : information manquante ⇒ jamais `high`. Si l'analyse
   sémantique est indisponible, le plafond du verdict est abaissé. Contexte
   insuffisant ⇒ refus, pas réponse prudente.
4. **Aucun seuil chiffré de confiance.** `confidence_level` est un enum de
   chaînes `high | medium | low`. Un flottant présenté comme probabilité serait
   une fausse précision : rien ici n'est calibré statistiquement.
5. **Judge et Devil's Advocate sortent du chemin actif.** Le code historique
   reste une **référence de conception** (les critères qu'ils listent deviennent
   les contrôles de Laya), pas une passe à exécuter.
6. **Hors chemin actif** : un harnais d'évaluation **par lot**, qui rejoue des
   jeux de données pour produire des métriques de régression. Il ne juge pas les
   requêtes des utilisateurs et ne doit jamais bloquer le chat.

## Décision — connaissance

**OKF v0.2 est le format canonique de la connaissance.** Markdown UTF-8 avec
frontmatter YAML, versionné en Git.

- `knowledge/index.md` porte `okf_version: "0.2"` ; `log.md` est le journal.
- Les API déclarent `"knowledge_format": "OKF"` et `"knowledge_format_version": "0.2"`.
  Elles **référencent** le format, elles ne le transforment pas en JSON.
- **Git = vérité éditoriale. PostgreSQL = index opérationnel.** Indexer le
  bundle ne le remplace pas.
- Laya ne doit jamais **inventer** une provenance : une provenance absente est
  une provenance absente.

## Conséquences

- Le plugin `karpathywiki` et son `AGENTS.md` (qui prescrit Ollama) ne sont pas
  la cible. Le schéma OKF est repris comme **patrimoine**, réécrit au format
  v1.4.
- L'évaluation en ligne coûte un seul passage de génération.
- La suppression de l'avocat ne supprime pas le contrôle qualité : elle le
  déplace vers des contrôles qui, eux, ne peuvent pas échouer silencieusement.