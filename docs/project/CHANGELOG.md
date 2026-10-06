# PROF IA v1.4 — Journal de chantier

Journal **opérationnel**. Il trace ce qui a été fait, avec quelle preuve et sur
quelle décision. Ce n'est **pas** un document normatif.

- Décisions normatives → [`docs/architecture/PROF-IA-v1.4-master.md`](../architecture/PROF-IA-v1.4-master.md)
- Justifications → [`docs/architecture/adr/`](../architecture/adr/)
- Suivi des gates → section [Gates](#gates) ci-dessous

Aucune date ni aucun identifiant de commit n'est inventé. Tout provient de Git
ou d'un rapport d'exécution réel.

> **Hébergement de la branche.** `prof-ia-v1.4` est une **branche de migration
> du dépôt `RAG-Harvard-IT-teacher`**, créée depuis `main` (`87a274d`).
> `main` reste l'historique stable et n'est pas modifié. Le dossier
> `PROF IA 6oct` reste un point de sauvegarde local (tag
> `snapshot/g0-qwen-2026-10-06`), sans remote.
>
> Les documents v6 du dépôt historique sont **préservés et marqués legacy**
> dans `docs/legacy/` : les README EN/FR, l'ancien `AGENTS.md`, et le document
> maître v1.3. Aucun n'a été réécrit.

---

## 2026-10-06 — Initialisation du dépôt

- Gate: —
- Statut: fait
- Résultat: dépôt local `PROF IA 6oct` initialisé, `git init`, pas de remote
- Commit: `1bdafd4` — *chore: add install script, systemd service, update
  fait.md with Vulkan-only build, memory-safe embeddings, realistic coverage*
- Décision XZ: greenfield dans `PROF IA 6oct/`, ancien dépôt
  `RAG-Harvard-IT-teacher` conservé comme patrimoine
- Artefacts: `README.md`, `.gitignore`,
  `scripts/install/install-llama-cpp.sh`, `deploy/systemd/profia-llama.service`

---

## 2026-10-06 — T0.-1 : protocole de caractérisation mémoire

- Gate: T0.-1
- Statut: **CLOSED / ACCEPTED**
- Résultat: `60` tests protocole verts, puis `76` après couverture de
  l'orchestrateur, puis `101` après durcissement de la détection de flags
- Artefacts promus:
  - `scripts/benchmark/fit_campaign.sh`
  - `scripts/benchmark/run_matrix.sh`
- Bac de validation (reste hors dépôt): `/work/profia-t0-1/`
- Commit: *aucun à ce jour* — les artefacts sont présents dans l'arbre de
  travail, non commités
- Décision XZ:
  - taxonomy de verdicts figée : `STARTUP_FAIL`, `HTTP_FAIL`, `OOM_KILL`,
    `GPU_RESET`, `GENERATION_FAIL`, `INCONCLUSIVE`, `GREEN`
  - `METRIC_MISSING` = `INCONCLUSIVE`, jamais RED
  - aucun seuil de débit, de mémoire ou de température
  - fallback `ngl_partial` autorisé **uniquement** par `OOM_KILL`, `GPU_RESET`,
    `INCONCLUSIVE`
- Preuves notables:
  - mutation volontaire de la règle de fallback → **5 tests échouent** (les
    tests ont des dents)
  - `/proc/meminfo` mal parsé (clé `MemAvailable:` avec deux-points) → budget
    mémoire toujours `null`
  - octets passés dans un convertisseur KiB→MiB → VRAM affichée 11264 au lieu
    de 11
  - signature OOM limitée à `oom_kill` alors que le noyau log `oom_reaper`

---

## 2026-10-06 — G0 : source de vérité documentaire

- Gate: G0
- Statut: **GREEN / CLOSED**
- Résultat: six contradictions vivantes fermées, quatre ADR créées,
  hiérarchie documentaire en place
- Contradictions fermées:
  - `MemoryDenyWriteExecute=true` retiré du service systemd (casse le JIT Vulkan)
  - mention « CUDA (dev) » retirée du README
  - `172.17.0.1` : plus aucune prescription hors legacy
  - auto-contradiction `127.0.0.1` (§A.3.1) marquée superseded
  - document v1.3 renommé `docs/legacy/PROF-IA-v1.3-master.html` + bandeau
  - `PROF-IA-v1.4-master.md` créé (il n'existait pas)
- Artefacts: `AGENTS.md`, `docs/architecture/PROF-IA-v1.4-master.md`,
  `docs/architecture/adr/ADR-001`…`ADR-004`, `knowledge/AGENTS.md`,
  `docs/legacy/PROF-IA-v1.3-master.html`
- Commit: *aucun à ce jour*
- Décision XZ: sécurité documentaire préférée à la pureté du diff ; le dépôt
  historique n'est pas réécrit

---

## 2026-10-06 — G1 (pré-déploiement) : qualification par preuve

- Gate: G1
- Statut: **IN PROGRESS** — non clôturée
- Résultat:
  - `llama.cpp` **réellement compilé** avec `-DGGML_VULKAN=ON
    -DLLAMA_CURL=ON` → `-- Including Vulkan backend`, binaire produit
  - écart Debian 13 établi depuis l'archive : noyau trixie `6.12.111`,
    backports `7.2.6` ; **`6.18.18` n'est packagé ni dans l'un ni dans l'autre**
  - écart Mesa établi : Debian 13 stable livre `25.0.x`, **sous le plancher
    BC-250 de 25.1** ; trixie-backports fournit `25.2.6+`
  - **bug de détection de flags trouvé contre le vrai binaire** : `grep -q`
    sous `pipefail` renvoie un échec quand `grep` sort tôt (SIGPIPE sur
    `printf`), donc `-ngl -c -ctk -ctv -np -fa -b -ub` passaient pour absents
    sur un `--help` de 59 Ko. Le help de 411 octets du stub ne pouvait pas le
    reproduire. Corrigé par correspondance bash `help_has_flag`.
  - `host-gateway` résout vers **`172.17.0.1`** (bridge par défaut), pas vers
    la passerelle du réseau dédié — l'ADR-003 doit être relue sur ce point
- Bac: `/work/profia-g1/` (sondeur `g1_platform_probe.sh`, rapport
  `artifacts/host_run.json` → `BLOCKED`, attendu hors BC-250)
- Commit: *aucun à ce jour*
- Décision XZ: G1 est une qualification **par preuve pré-déploiement**, pas une
  validation matérielle ; la BC-250 intervient comme gate de déploiement

---

## 2026-10-06 — Candidat modèle : Qwen2.5-7B-Instruct Q6_K

- Gate: prérequis de G2
- Statut: **soumis à revue XZ**
- Résultat: bascule du candidat Gemma 4 26B IQ3_XS → Qwen2.5-7B-Instruct Q6_K
- Vérifications:
  - nom de fichier et taille confirmés chez Bartowski :
    `Qwen2.5-7B-Instruct-Q6_K.gguf`, **6,254 Go** (5,825 GiB)
  - `101` tests verts après migration
  - fingerprint enrichi : `model_name`, `model_file`, `model_size_bytes`,
    `model_sha256`, `llama_version`, `llama_help_hash`
  - le `model` du corps HTTP n'est plus codé en dur, il dérive du fichier réel
- Artefacts modifiés:
  `deploy/systemd/profia-llama.service`,
  `docs/architecture/PROF-IA-v1.4-master.md`,
  `docs/architecture/adr/ADR-002-llama-cpp-vulkan.md` (renommé depuis
  `ADR-002-llama-cpp-vulkan-gemma4.md`), `docs/architecture/adr/ADR-004-laya-okf.md`,
  `README.md`, `AGENTS.md`, `scripts/benchmark/fit_campaign.sh`,
  `scripts/benchmark/run_matrix.sh`
- Commit: *aucun à ce jour*
- Décision XZ: candidat ≠ validé ≠ production ; la marge mémoire est une
  motivation, pas une preuve

---

## Gates

| Gate | Sujet | Statut |
|---|---|---|
| T0.-1 | Protocole de caractérisation mémoire | **CLOSED / ACCEPTED** |
| G0 | Documentation, source de vérité | **GREEN / CLOSED** |
| G1 | Qualification pré-déploiement | **IN PROGRESS** |
| G2 | Mémoire réelle + llama.cpp + modèle candidat | non ouvert |
| G3+ | Retrieval, OKF, Laya, E2E | non ouverts |

## Blocages en cours

1. **`ADR-003` à relire avant G2** : elle affirme `host-gateway` comme
   solution de nommage, alors que la mesure montre que `host-gateway` résout
   vers `172.17.0.1` (bridge par défaut) et **non** vers la passerelle
   `172.30.50.1` du réseau dédié.
2. **Connectivité TCP conteneur→hôte non concluante** dans l'environnement de
   développement : à re-tester hors sandbox.
3. **`install-llama-cpp.sh` utilise `-j$(nproc)`** ; la compilation llama.cpp a
   échoué une fois à ce parallélisme puis réussi en série réduit. Garde-fou à
   prévoir.
4. **Candidat Qwen non téléchargé** : aucun SHA256 ne peut être calculé. La
   campagne G2 ne peut pas démarrer sans le fichier réel.