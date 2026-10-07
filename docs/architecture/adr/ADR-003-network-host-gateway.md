# ADR-003 — Réseau hôte↔conteneur : passerelle dédiée, résolution explicite

**Statut :** accepté · **Date :** 2026-10-06 · **Supersede :** le §4 et le §16 du document maître v1.3

## Contexte

`llama.cpp` tourne **sur l'hôte** (ADR-002). FastAPI tourne **dans un
conteneur**. Le backend doit donc joindre un service qui écoute sur l'hôte.

Le document v1.3 prescrivait `--host 172.17.0.1` : l'adresse de l'interface
`docker0` par défaut. Cette adresse **n'est pas garantie** — elle dépend de la
configuration Docker et des réseaux déjà déclarés. Un conflit ou une
configuration différente la déplace, et le backend cesse de joindre llama.cpp
sans aucun signal clair.

Le même document contenait une contradiction interne : son §A.3.1 affirmait
« accès strictement localhost (`127.0.0.1`) » alors que ses §4 et §16 font
écouter llama.cpp sur la passerelle. Depuis un conteneur, `127.0.0.1` désigne
**le conteneur lui-même**, jamais l'hôte.

Une version précédente de cette ADR prescrivait `host-gateway` comme mécanisme
de résolution : `extra_hosts: - "llama-host:host-gateway"`. Or le mécanisme
`host-gateway` de Docker résout vers l'adresse de l'interface `docker0`
par défaut (`172.17.0.1`), **pas** vers la gateway du réseau dédié
`profia-llama` (`172.30.50.1`). Cette différence a causé des pertes de
connexion silencieuses.

## Décision

1. Un réseau bridge **déclaré explicitement** :

   ```bash
   docker network create --driver bridge \
     --subnet 172.30.50.0/24 --gateway 172.30.50.1 profia-llama
   ```

2. `llama-server` écoute sur `172.30.50.1:8081` (l'adresse hôte de ce réseau
   dédié), **pas** sur `0.0.0.0`.
3. Le backend résout l'hôte par le nom DNS `llama-host` vers l'IP explicite
   `172.30.50.1`, injecté via `extra_hosts` :

   ```yaml
   extra_hosts:
     - "llama-host:172.30.50.1"
   ```

   et consomme `LLAMA_SERVER_URL=http://llama-host:8081`.
4. Le port `8081` n'est **jamais** publié dans le compose.
5. Le filtrage réseau local (nftables/iptables) restreint `8081` au backend.

## Justification

Un sous-réseau déclaré rend l'adresse **déterministe** : elle ne peut pas être
réattribuée par Docker, et un conflit se détecte à la création du réseau au
lieu de se manifester plus tard comme une panne de connexion.

L'IP explicite `172.30.50.1` dans `extra_hosts` garantit que `llama-host`
résout **toujours** vers la gateway du réseau dédié `profia-llama`,
indépendamment du comportement par défaut de `host-gateway` (qui pointe vers
`docker0` / `172.17.0.1`). Cela élimine une classe entière de pannes de
connectivité silencieuses.

Écouter sur la passerelle du réseau dédié plutôt que sur `0.0.0.0` évite
d'exposer llama.cpp sur toutes les interfaces, dont le LAN.

## Conséquences

- Le réseau doit **exister avant** le service llama.cpp. Le service systemd le
  vérifie en `ExecStartPre` et refuse de démarrer sinon : un échec de démarrage
  explicite vaut mieux qu'un serveur joignable mais muet.
- Le prérequis est bloquant pour le gate suivant : tant que la
  connectivité hôte↔conteneur n'est pas prouvée, le backend ne peut pas être
  considéré fonctionnel.
- Toute divergence d'adresse (`172.17.0.1`, `0.0.0.0` publié, `127.0.0.1`
  côté backend) est un défaut, pas une variante.
- Le mécanisme `host-gateway` **ne doit pas être utilisé** pour la résolution
  de `llama-host` vers la cible canonique `172.30.50.1`.

## Portée

Cette ADR ne dit rien de l'exposition publique. Le périmètre reste
LAN/applications locales ; une exposition Internet exigerait un profil de
déploiement distinct (authentification, TLS, limitation de débit).