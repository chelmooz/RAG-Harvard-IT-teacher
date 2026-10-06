# ADR-001 — Debian 13 bare metal comme OS cible

**Statut :** accepté · **Date :** 2026-10-06 · **Remplace :** Bazzite (hérité du dépôt historique)

## Contexte

Le dépôt `RAG-Harvard-IT-teacher` avait basculé sur **Bazzite** (commit
`94e6c41`, « Bazzite-only — drop Debian scripts/docs »), avec des scripts
d'optimisation BC-250 écrits pour rpm-ostree et Bazzite. Les documents
maîtres v1.2 et v1.3 de PROF-IA, eux, prescrivent **Debian 13**.

Deux trajectories s'affrontaient : le dépôt réel (Bazzite) et la spécification
(cierge). Un agent suivant les deux à la fois produirait une architecture
incohérente.

## Décision

**Debian 13 (trixie) bare metal.** Bazzite est retiré de la cible.

## Justification

- La spécification du projet l'impose depuis le début ; c'est le choix
  documenté, pas une hypothèse.
- Bare metal supprime une couche d'abstraction sur une machine où l'accès à la
  mémoire unifiée et au GPU est justement le point critique.
- Les scripts BC-250 existants (UMR 40 CU, SMU-OC, mem-oc) sont des scripts
  shell/Python génériques ; seule l'intégration rpm-ostree était spécifique à
  Bazzite.

## Conséquences

- Les scripts `rpm-ostree` de l'historique sont inutilisables ; il faut les
  réécrire pour `systemd` + sysfs.
- **Risque documenté** : Debian 13 stable livre le noyau **6.12**, alors que la
  documentation BC-250 recommande 6.18.18 LTS et déclare 6.12 « fallback stable ».
  Mesa ≥ 25.1 (minimum BC-250 amont) peut nécessiter les dépôts
  backports/experimental.
  Ces deux points sont à qualifier au gate **G1**, pas supposés acquis.
- Le support matériel ne peut pas être supposé : il sera mesuré sur la machine.

## Ce que cette décision ne décide pas

Ni le noyau exact, ni la version de Mesa, ni le statut des 40 CU. Ces points
relèvent de G1 et doivent être **mesurés**, pas hérités d'un document.