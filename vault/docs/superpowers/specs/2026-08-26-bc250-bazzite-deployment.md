---
type: concept
title: Configuration optimale BC-250 (jeu + serveur RAG)
description: Assemblage "best-of-each" des repos BC-250 pour une machine hybride (station de jeu + serveur RAG Prof-IA/Ollama) sous Bazzite, avec séquences registres/SMU exactes et portabilité.
resource: bc250-sources/
status: stable
stale_after: 2027-08-26
tags:
  - bc250
  - bazzite
  - optimisation
  - ollama
  - rag
generated:
  by: "agent:opencode"
  at: "2026-08-26"
verified:
  by: "human:michel"
  at: "2026-08-26"
sources:
  - uri: "bc250-sources/linux-cachyos-bc250/"
  - uri: "bc250-sources/bc250-cu-live-manager/"
  - uri: "bc250-sources/bc250_smu_oc/"
  - uri: "bc250-sources/bc250-steamos/"
  - uri: "bc250-sources/bc250-steamos-real-toolkit/"
aliases:
  - bc250-best-config
statut: confirme
okf_version: "0.2"
concepts:
  - BC-250
  - Bazzite
  - Ollama
  - Vulkan
  - ROCm
questions_ouvertes:
  - "Phase 2 (noyau Bazzite custom + Mesa async) : à planifier si ROCm embeddings ou +10-15 FPS jeu requis."
  - "Harvest pattern du silicium : stresser 40 CU / 8 cœurs avant mise en prod."
---

# Configuration optimale BC-250 — station de jeu + serveur RAG (hybride)

## Contexte

BC-250 (AMD Cyan Skillfish / RDNA2 / **gfx1013**, PCI `1002:13fe`) utilisé **les deux** :
- **Serveur RAG Prof-IA** : Ollama (Vulkan/RADV) + PostgreSQL/pgvector + backend FastAPI + vault LLM Wiki.
- **Station de jeu** : Steam/Proton (Vulkan/RADV).

**OS retenu : Bazzite** (Fedora immutable, `rpm-ostree`) — fait les deux (Steam + Docker/serveurs).

> ⚠️ **Article pausehardware « Linux 6.19 AMDGPU » : NON APPLICABLE.** Le basculement AMDGPU-par-défaut de 6.19 ne concerne que le **GCN 1.0/1.1**. Le BC-250 est **RDNA2/gfx1013**, il utilise déjà AMDGPU. Tourner un noyau ≥6.x aide, mais le gain « +40 % » cité ne nous concerne pas.

## Sources analysées (clonées dans `bc250-sources/`, non versionnées)

| Repo | Apport retenu |
|---|---|
| MastaG/linux-cachyos-bc250 | Patches noyau (télémétrie, PASID TLB/ROCm, 40 CU, SCLK) + Mesa patché |
| WinnieLV/bc250-cu-live-manager | 40 CU + CPU unlock via **UMR** (sans patch noyau), Bazzite OK |
| bc250-collective/bc250_smu_oc | UV/OC CPU par messages SMU (testé Bazzite) |
| keyboardspecialist/bc250-steamos | RAM/VRAM split (UMA + TTM), ACPI, power |
| rpf16rj/bc250-steamos-real-toolkit | Profil « Mild » UV de référence |

## Correction vs spec précédente

- `TTM pages_limit=3959290` (~15 Go) **trop haut** → GPU pompe la RAM CPU (Postgres/Ollama host).
  **Correct** : `UMA_SIZE=512 MiB` + `ttm.pages_limit=3014656` (~11,5 Go dynamique) ≈ **12 Go GPU / 4 Go CPU**.
- BIOS : P3.00, VRAM dynamique 512 Mo, IOMMU OFF (déjà fait).

---

## Phase 1 — Baseline sûr (userspace, AUCUN rebuild noyau)

Tout passe par UMR / messages SMU / grub-kargs. Couvre 100 % du serveur RAG + jeu de base.

### 1.1 Déblocage 40 CU (capé 1500 MHz / 900 mV)

Séquence exacte (registres gfx1013, appliquée par UMR — `WinnieLV/bc250-cu-live-manager.sh`):

| Registre | 24 CU (stock) | 40 CU |
|---|---|---|
| `mmCC_GC_SHADER_ARRAY_CONFIG` | défaut | `0x0` |
| `mmSPI_PG_ENABLE_STATIC_WGP_MASK` | `0x07` | `0x1f` |
| `mmRLC_PG_ALWAYS_ON_WGP_MASK` | `0x07` | `0x1f` |

ASIC : `cyan_skillfish.gfx1013`. Appliquer par ligne (SE0-1/SH0-1) : `CC=0x0`, `SPI=<masque>`, puis `RLC=union`.
Persistance boot : service systemd `bc250-cu-live-manager` (lit `/etc/bc250-cu-live-manager.conf`).

**Cap de sécurité** (MastaG) : à 1500 MHz / 900 mV le gain est ~1,5–1,6× throughput pour ~+30 W / +4 °C.
Ne PAS dépasser **GPU ≤ ~2,2–2,4 GHz** en air cooling. Stresser avant prod (silicon harvest scatteré = CUs défectueux possibles → masquer WGP via `amdgpu.disable_cu=SE.SH.WGP`).

Vérification : `bc250-cu-status.sh -q` → `40/40` ; benchmark `llama-bench` pp512 Vulkan.

### 1.2 Déblocage CPU 8 cœurs (6→8)

Message SMU « ungated » Q3 `0x98` vers **SMN `0x0115A870`**, masque **`0x77` → `0xFF`** (PCI `0000:00:00.0`, fenêtre `0xB8`/`0xBC`).
Volatil : conserve après warm reboot, **perdu après cold power-off** → service boot `bc250-core-unlock` qui ré-écrit le masque (et redémarre `cyan-skillfish-governor-smu`).
Vérification : `nproc` ≥ 16.

### 1.3 UV/OC CPU (efficacité + thermique)

Messages SMU Q3 (`bc250_smu_oc`, `bc250_smu/api_q3.py`) :
- `0x8F` fréquence boost max, `0x50` échelle VID (négatif = undervolt), `0x8B`/`0x8C` limites temp CPU/GPU, `0x9A` désactive le chemin « extra voltage ».

**Plage sûre** (`bc250_limits.py`) : `vid_max = 1325 mV` (**>1,325 V = risque brick confirmé**), `freq 3500–4500`, temp défaut 90 °C.

**Profil « Mild » recommandé** (réf. rpf16rj, stable sur alim 460 W) :
```
[overclock]
frequency = 3500
scale = -22
max_temperature = 80
```
→ `q3_0x8f(3500)` + `q3_0x50(-22)` + `q3_0x8b/8c(80)` + `disable_extra_cpu_gpu_voltage(True)`.
Persistance : `bc250-apply --install overclock.conf` → `/etc/systemd/system/bc250-smu-oc.service`, `systemctl enable bc250-smu-oc`.

### 1.4 Split RAM/VRAM corrigé (12 Go GPU / 4 Go CPU)

- CMOS UMA (via `bc250memcfg`, distro-agnostique) : `UMA_SIZE = 512` (MiB).
- TTM (Bazzite = `rpm-ostree kargs`, pas grub) :
  ```
  rpm-ostree kargs --append-if-missing="ttm.pages_limit=3014656"
  ```
  soit ~11,5 Go dynamique + 512 Mo UMA ≈ 12 Go GPU, ≥4 Go CPU.

**Résultat Phase 1** : Ollama (qwen3:14b GPU plein) + Postgres + backend + vault servis à pleine capacité GPU (40 CU), host à 8 cœurs sous-voltage. Jeu Steam fonctionnel (sans async-compute).

---

## Phase 2 — Opt-in avancé (noyau Bazzite custom + couche Mesa)

Nécessaire **uniquement** si : embeddings ROCm GPU, ou +10–15 FPS en jeu (async-compute Vulkan).

### 2.1 Patches MastaG — portabilité

Tous touchent `drivers/gpu/drm/amd/*` (amont 6.x), donc **logique non CachyOS-only** mais **exigent un rebuild de noyau Bazzite** (akmod / kernel-tree), car Bazzite ship un seul noyau unifié.

| Patch | But | Phase 2 ? |
|---|---|---|
| 0001 télémétrie 8c + activité GPU | `gpu_busy_percent` correct | utile |
| 0003 nct6687d hwmon | ventilo/PWM | module à part |
| 0004 PASID TLB (gfx1013) | **enableur ROCm** | requis ROCm |
| 0005 compute GFXOFF guard | ROCm | requis ROCm |
| 0006 runlist TLB flush | ROCm (`amdgpu.bc250_flush_by_runlist=1`) | requis ROCm |
| 0007 TTM null-page guard | stabilité | recommandé |
| 0008 SCLK 350–2230 MHz | plage governor | utile |
| 0009 40 CU (noir boot) | alt. UMR | optionnel |

### 2.2 ROCm embeddings (bge-m3) sur gfx1013

- Noyau patché 0004+0005+0006 + `options amdgpu bc250_flush_by_runlist=1` (HWS only).
- rocBLAS/Tensile **gfx1013** sous `/opt/rocm/lib/rocblas/library` (GabriWar/bc250-rocm-working) + PyTorch natif gfx1013.
- **Alternative simple (défaut)** : endpoint embedding Ollama (Vulkan/RADV) — fiable sans ROCm.

### 2.3 Mesa async-compute (jeu)

Noyau 0004/0005/0006 + **Mesa/RADV custom** buildé sous `/opt/bc250-gfx1013/` et épinglé via
`VK_DRIVER_FILES=/opt/bc250-gfx1013/share/vulkan/icd.d/radeon_icd.x86_64.json`.
`RADV_GFX103=1` **jamais global** (jeux ciblés seulement). +25 mV GPU si green/black-screen.

---

## 6. Outilage durci (revue senior system designer, 2026-08-26)

Scripts désormais **vendored** dans `scripts/bc250/` (MIT — voir `CREDITS.md` à la racine).
`bc250-sources/` a été supprimé après harvest (gitignoré).

### 6.1 Orchestration + santé (idempotent, boot)
- `scripts/bc250/apply_phase1.sh` : enchaîne 40 CU → 8 cœurs → UV/OC CPU, puis lance le health-check. Sort en erreur si non effectif.
- `scripts/bc250/health-check.sh` : vérifie `active_cu_number` via `dmesg` (≥40) + `nproc` (≥8).
- `scripts/bc250/bc250-optimizations.service` (systemd) : `Type=oneshot`, `Restart=on-failure`, `RestartSec=15`, `StartLimitIntervalSec=120`/`StartLimitBurst=3` (anti-bootloop si silicon/VRM refusent). Installé + activé par `setup.sh` sous `/opt/bc250`.

### 6.2 Memory OC (GDDR6) — garde-fous stricts
- `scripts/bc250/mem-oc/mem_oc.sh` : tente l'OD sysfs `pp_od_clk_voltage` (incrément +50 MHz, `stress-ng` puis revert auto si instable).
- Sur Cyan Skillfish l'OD sysfs est **souvent absent** → message clair : utiliser le réglage « memory clock » du **BIOS/CMOS** (manuel) ou un message SMU mémoire VÉRIFIÉ (non automatisé ici). C'est le plus gros levier jeu, mais le plus risqué.

### 6.3 Bascule JEU ⇄ RAG (partage mémoire unifiée)
- `scripts/bc250/bc250-game-mode.sh` : `game` (décharge Ollama → VRAM libre), `rag` (recharge), `status`.
- `game-boot`/`rag-boot` : posent `ttm.pages_limit` (8/8 vs 12/4 Go) + reboot — le BIOS reste à 512 Mo **dynamique** (le karg est le vrai plafond).
- ⚠️ RAG + jeu **simultanés** dépassent le budget 12 Go GPU (qwen3:14b 9,3 Go + jeu) → privilégier le swapper, pas le simultané.

### 6.4 Provisioning Bazzite (`scripts/bazzite/setup.sh`)
`rpm-ostree kargs` (split 12/4) + governor COPR + **`umr` + `python3`** (dépendances 40 CU / SMU) + install service `/opt/bc250` + `bc250-game-mode` dans `/usr/local/bin` + **monitoring** (`btop`/`htop`/`amdgpu_top`/`mangohud` + `bc250-gpu-fix` pour l'util GPU 655%).

### 6.5 Fine-tuning (rappel)
qwen3:14b QLoRA 4-bit sur **12 Go** est marginal (modèle + LoRA + KV + contexte). Recommandé : LoRA sur machine bien plus grosse, export GGUF, dépôt sur le BC-250. `fine_tuning/` est correct mais à exécuter **hors-box**.

### 6.6 Audio de la station de jeu — décision (2026-08-26)
**Choix utilisateur : Bluetooth uniquement pour l'instant** (dongle USB → BlueZ + PipeWire, natif Bazzite, aucun driver propriétaire) + enceinte BT. Suffisant pour la station de jeu v1. Aucun script additionnel requis (`setup.sh` ne touche pas l'audio).
- **DP/HDMI 5.1 différé** (« au besoin ») : le BC-250 n'a que du **DisplayPort** (pas HDMI). Bug d'horloge DP confirmé (DTO programmé pour réf `728,631 MHz` vs DPREFCLK réel `600,000 MHz` → **39,5 kHz au lieu de 48 kHz**, son lent/crachouillant). Fix possible : patch noyau `DCCG_AUDIO_DTO1_MODULE = 6000000` (réf. `essdee4336/kernel-bazzite-dp-audio-fix`, TheFloW) OU adaptateur audio USB. À traiter uniquement si l'audio DP devient nécessaire.
- `bc250-audio-fix` (rpf16rj) supprimé avec `bc250-sources/` sans harvest — à réintroduire **uniquement** si on veut l'audio DP.

## Sécurité (rappel)

- **Vid CPU ≤ 1300 mV** (brick au-delà). Temp CPU/GPU ≤ ~90 °C.
- GPU air ≤ ~2,2–2,4 GHz. Alim dimensionnée (≥460 W HP testé pour 8c+40CU sous-UV).
- Stresser 40 CU + 8 cœurs (OCCT/Prime95/Furmark réel) avant prod.
- `AMD-BC-250-at-his-Best/` (nested .git) **non touché** ; sources dans `bc250-sources/` (gitignoré).
