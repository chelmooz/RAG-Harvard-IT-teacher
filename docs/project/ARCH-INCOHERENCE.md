# Incohérence architecturale — Séparation réseau vs migration applicative

**Statut :** à valider par XZ · **Date :** 2026-10-06 · **Gate :** G1.1 (T05)
**Prérequis :** T01 accepté (réseau résolu), T02 accepté (audit Ollama complet)

---

## 1. Constat : deux architectures simultanées

Le dépôt **racontait encore deux architectures simultanément** au démarrage de G1.1 :

| Couche | Architecture active (code/config) | Architecture normative (ADR/systemd) |
|--------|-----------------------------------|--------------------------------------|
| **Infrastructure** | `docker-compose.yml` : service `ollama` (image `ollama/ollama:0.32.15`, ports 11434/11436, healthcheck) | ADR-002 : `llama.cpp` **hors conteneur**, service systemd `profia-llama` |
| **Configuration** | `config.py` : `OLLAMA_HOST`, `OLLAMA_MODEL`, 8 options `OLLAMA_*` | ADR-002 : `LLAMA_SERVER_URL=http://llama-host:8081` (ajouté T01) |
| **Code backend** | `dependencies.py` : `OllamaLLMClient` = **seule** implémentation `LLMClient` | Protocole `LLMClient` abstrait (prêt pour `LlamaCppClient`) |
| **Réseau** | `host-gateway` implicite (pointe vers `docker0` 172.17.0.1) | ADR-003 : `172.30.50.1` explicite via `extra_hosts` (T01 résolu) |
| **Frontend** | Affiche `health.ollama` | Doit afficher `health.llm` (schéma migré) |

---

## 2. Séparation nette : Réseau vs Migration applicative

```text
RÉSEAU (T01 — RÉSOLU)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ADR-003
172.30.50.1
llama-host
extra_hosts: "llama-host:172.30.50.1"
LLAMA_SERVER_URL=http://llama-host:8081
        ↓
        ✅ RÉSOLU (T01 accepté)

MIGRATION APPLICATIVE (CHANTIER RESTANT)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Ollama en conteneur (docker-compose.yml)
        ↓
llama.cpp hôte (systemd profia-llama)
        ↓
        20 références `migrate` à migrer
        (chemin d'exécution complet — voir audit T02)
```

> **Point critique :** T01 a résolu le **transport/réseau** (endpoint canonique `172.30.50.1`, `llama-host`, `LLAMA_SERVER_URL`). **Il n'a PAS résolu la migration applicative Ollama → llama.cpp.** Les 20 références `migrate` identifiées dans l'audit T02 (OLLAMA-AUDIT.md) restent à traiter dans un chantier dédié post-G1.1.

---

## 3. Preuve de séparation (T01 vs T02/T05)

| Ticket | Périmètre | Preuve de réalisation |
|--------|-----------|----------------------|
| **T01** | Réseau / Transport | `docker-compose.yml` : `extra_hosts: llama-host:172.30.50.1` + `LLAMA_SERVER_URL` ; `config.py` : `LLAMA_SERVER_URL` ; ADR-003 mise à jour (IP explicite, `host-gateway` noté non fiable) ; tests syntaxe OK |
| **T02** | Audit exhaustif | `docs/project/OLLAMA-AUDIT.md` : 35 fichiers classés → 20 `migrate` (chemin d'exécution), 5 `legacy`, 10 `keep` |
| **T03** | Guide installation | `INSTALLATION.md` : 4 phases, badges, section références Ollama (intègre audit T02) |
| **T05** (ce doc) | Documentation séparation | Ce document : séparation explicite réseau vs migration, déclaration conditionnelle |

---

## 4. Déclaration de clôture conditionnelle

### ADR-003 — Réseau : **CLOSED / ACCEPTED**

> **L'ADR-003 réseau est résolue.** La résolution explicite `172.30.50.1` via `extra_hosts` est en production dans le compose, `LLAMA_SERVER_URL` existe dans le compose et `config.py`, le service systemd valide la gateway `172.30.50.1` en `ExecStartPre`. `host-gateway` n'est plus utilisé pour la cible canonique.

### Migration Ollama → llama.cpp : **OUVERT / CHANTIER POST-G1.1**

> **La migration applicative Ollama → llama.cpp N'EST PAS RÉALISÉE.** Les 20 références `migrate` identifiées dans l'audit T02 (OLLAMA-AUDIT.md §4) maintiennent Ollama dans le chemin d'exécution réel. Ce chantier est **hors G1.1**, planifié post-G1.1 avec skill `improve-codebase-architecture` si refonte structurelle nécessaire.

> **Critère de sortie pour déclarer la migration close :**
> 1. `docker-compose.yml` : service `ollama` supprimé, `depends_on` retiré, `OLLAMA_HOST` retiré, backend raccordé au réseau `profia-llama` uniquement.
> 2. `config.py` : section `OLLAMA_*` supprimée/archivée, `LLAMA_SERVER_URL` seule source de vérité.
> 3. `dependencies.py` : `LlamaCppClient` implémenté (API OpenAI-compatible `/v1/chat/completions` sur `LLAMA_SERVER_URL`), câblé dans `get_llm_client()`.
> 4. `rag_engine.py`, `main.py`, `evaluation.py`, `schemas.py` : code Ollama remplacé par protocole `LLMClient` abstrait.
> 5. Frontend : champ `health.ollama` → `health.llm` (coordonné avec `schemas.py`).
> 5. Tests : mockent le protocole `LLMClient` (seam publique), pas l'implémentation `OllamaLLMClient`.
> 6. Scripts BC-250 : `bc250-game-mode.sh` arrête/démarre `profia-llama.service` au lieu de `systemctl --user ollama`.
> 7. Docs racine v6 (`BC-250-INSTALL-GUIDE*.md`, `Prof-IA-v6-Documentation-BC250.md`, `BACKLOG.md`, `fait.md`) : bandeaux legacy + renvoi vers `INSTALLATION.md`.

---

## 5. Preuves de non-régression (T01 accepté)

| Test | Résultat |
|------|----------|
| `docker compose config` (avec `.env` factice) | ✅ Syntax OK |
| `python3 -m py_compile backend/api/config.py` | ✅ OK |
| `docker compose config` + `grep extra_hosts` | ✅ `llama-host:172.30.50.1` présent |
| `python3 -m py_compile` + `grep LLAMA_SERVER_URL` | ✅ Champ présent dans `Settings` |
| ADR-003 : `grep -c "172.30.50.1"` | ✅ 4 occurrences (gateway, extra_hosts, commentaire, ExecStartPre) |
| ADR-003 : `grep -c "host-gateway"` | ✅ 0 occurrence active (seule mention historique + avertissement) |

---

## 5. Références

- `docs/project/OLLAMA-AUDIT.md` (T02) — audit exhaustif 35 fichiers, 20 migrate, 5 legacy, 10 keep
- `INSTALLATION.md` (T03) — guide 4 phases, badges, section références Ollama
- `docs/architecture/adr/ADR-003-network-host-gateway.md` — ADR mise à jour (T01)
- `docker-compose.yml` — compose v1.4 (T01 : extra_hosts + LLAMA_SERVER_URL)
- `backend/api/config.py` — `LLAMA_SERVER_URL` ajouté (T01)
- `docs/architecture/DEBIAN13-KERNEL-MESA-STRATEGY.md` (T04)
- `docs/project/G1.1-SPEC.md` — spécification G1.1 (T01–T05)
- `docs/project/CHANGELOG.md` — journal G1.1 IN PROGRESS

---

## 6. Déclaration finale

> **T01 a résolu le problème réseau, mais la migration applicative Ollama → llama.cpp n'est PAS considérée comme réalisée par T01.**
>
> Ce document officialise la séparation. **ADR-003 réseau = CLOSED.** Migration Ollama→llama.cpp = **CHANTIER OUVERT (post-G1.1)**.
>
> Le dépôt ne raconte plus deux architectures contradictoires **au niveau documentaire** (T03/T05). Le code, lui, migre au chantier suivant.

---

**Fin du document.** Ce document ne remplace pas le chantier de migration applicative. Il officialise la séparation et fige la condition de sortie pour ADR-003.