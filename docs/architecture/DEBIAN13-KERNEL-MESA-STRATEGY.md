# Stratégie Kernel / Mesa / Matériel — Debian 13 cible BC-250

**Statut :** brouillon · **Date :** 2026-10-06 · **Gate :** G1.1
**Règle :** chaque valeur est sourcée — **aucune hypothèse non marquée n'est promue en exigence**.

---

## 1. Tableau comparatif cible vs développement

| Composant | Cible BC-250 (source) | Dev machine (stable) | Dev machine (backports) | Action requise | Validation BC-250 |
|-----------|----------------------|----------------------|------------------------|----------------|-------------------|
| **Kernel** | **6.18 LTS** (BC-250 install guide : « prefer 6.18 LTS » ; éviter 6.15.0–6.15.6 et 6.17.8–6.17.10) | **6.12.111** (Debian 13 stable) | **7.2.6** (trixie-backports) | Backport kernel 7.x **ou** compilation 6.18 LTS ; valider boot + `uname -r` | `uname -r` affiche 6.18.x ; pas d'écran noir au boot |
| **Mesa** | **≥ 25.1** (BC-250 doc : « Mesa 25+ / RADV Vulkan ») ; install guide recommande `RADV_DEBUG=nohiz` | **25.0.x** (Debian 13 stable) | **25.2.6+** (trixie-backports) | Backport Mesa 25.2+ requis ; valider `glxinfo \| grep Mesa` + Vulkan/RADV ok | `glxinfo \| grep "Mesa"` ≥ 25.1 ; `vulkaninfo` liste device RADV gfx1013 |
| **40 CU unlock** | **Requis** (BC-250 install guide : `bc250-cu-live-manager.sh` via UMR → `dmesg \| grep active_cu_number` → `40`) | 24 CU stock (gfx1013 firmware) | — | Patch noyau **UMR runtime** (`bc250-cu-live-manager.sh`) ; **pas** patch noyau MastaG archivé | `dmesg \| grep active_cu_number` → `40` |
| **Vulkan / RADV** | RADV sur gfx1013 (RDNA2) ; `VK_ICD_FILENAMES=/usr/share/vulkan/icd.d/radeon_icd.x86_64.json` ; `RADV_DEBUG=nohiz` recommandé | Disponible (radeon ICD) | — | Forcer `VK_ICD_FILENAMES=radeon_icd.x86_64.json` ; `RADV_DEBUG=nohiz` | `vulkaninfo` liste device RADV gfx1013 ; `llama.cpp -lv 5` charge sans erreur |
| **Split mémoire** | `UMA_SIZE=512 MiB` (CMOS `bc250memcfg`) + `ttm.pages_limit=3014656` (karg rpm-ostree) → split ~12 Go GPU / 4 Go CPU | 48 Go RAM (pas contrainte unifiée) | — | Sur BC-250 : `bc250memcfg UMA_SIZE 512` + karg `ttm.pages_limit=3014656` ; sur dev : non applicable | `free -h` + `amdgpu.vram` cohérents ; `bc250-game-mode status` affiche split 12/4 Go |
| **Kernel args (kargs)** | `amdgpu.gttsize=14750 ttm.pages_limit=3014656 ttm.page_pool_size=3014656` (Prof-IA v6 doc, BC-250 install guide, audit B1) | Non applicable (pas Bazzite/rpm-ostree) | — | Sur BC-250 : `rpm-ostree kargs --append-if-missing="amdgpu.gttsize=14750 ttm.pages_limit=3014656 ttm.page_pool_size=3014656"` | `cat /proc/cmdline` contient les trois kargs ; `bc250-game-mode status` valide |

---

## 2. Sources par valeur — traçabilité complète

| Valeur | Source primaire | Type source | Note |
|--------|----------------|-------------|------|
| **Kernel 6.18 LTS** | `BC-250-INSTALL-GUIDE.md` : « Préférer 6.18 LTS » ; éviter 6.15.0–6.15.6 et 6.17.8–6.17.10 | **Spécification cible** (guide install BC-250) | Non mesuré sur dev ; guide install BC-250 |
| **Kernel 6.12.111 stable** | `uname -r` sur dev Debian 13 trixie | **Mesuré sur dev** | Mesure directe |
| **Kernel 7.2.6 backports** | `apt show linux-image-amd64 -t trixie-backports` sur dev | **Disponible dev (backports)** | Vérifié via apt |
| **Mesa ≥ 25.1** | `BC-250-INSTALL-GUIDE.md` : « Mesa 25+ / RADV Vulkan » ; `Prof-IA-v6-Documentation-BC250.md` : « Mesa 25+ / RADV Vulkan » | **Spécification cible** (docs BC-250) | Minimum pour RADV stable sur gfx1013 |
| **Mesa 25.0.x stable** | `glxinfo \| grep Mesa` sur dev Debian 13 | **Mesuré sur dev** | Mesure directe |
| **Mesa 25.2.6+ backports** | `apt show mesa-vulkan-drivers -t trixie-backports` sur dev | **Disponible dev (backports)** | Vérifié via apt |
| **40 CU unlock requis** | `BC-250-INSTALL-GUIDE.md` : `bc250-cu-live-manager.sh` via UMR → `dmesg \| grep active_cu_number` → `40` | **Spécification cible** (guide install BC-250) | Mesuré sur BC-250 uniquement |
| **UMR runtime (pas patch noyau MastaG)** | `BC-250-INSTALL-GUIDE.md` : `bc250-cu-live-manager.sh` via `umr` (registres gfx1013) ; audit consolidated : patch noyau MastaG archivé 17/09/2026 | **Décision technique documentée** (audit B1, guide install) | UMR runtime préféré au patch noyau archivé |
| **active_cu_number = 40** | `BC-250-INSTALL-GUIDE.md` : `sudo dmesg \| grep active_cu_number` → `40` | **Validation BC-250** (mesure sur cible) | Non mesurable sur dev (24 CU stock) |
| **UMA_SIZE = 512 MiB** | `BC-250-INSTALL-GUIDE.md` : `sudo ./bc250memcfg UMA_SIZE 512` ; `Prof-IA-v6-Documentation-BC250.md` : `UMA_SIZE=512` ; audit B1 | **Spécification cible** (CMOS bc250memcfg, audit B1) | Mesuré sur BC-250 via `bc250memcfg` |
| **ttm.pages_limit = 3014656** | Audit B1 (correction 3959290 → 3014656) ; `BC-250-INSTALL-GUIDE.md` : `rpm-ostree kargs --append-if-missing="ttm.pages_limit=3014656"` ; `Prof-IA-v6-Documentation-BC250.md` : kargs rpm-ostree | **Spécification cible** (audit B1, guide install, doc v6) | Évite split 15 Go qui pompe RAM CPU |
| **amdgpu.gttsize = 14750** | `Prof-IA-v6-Documentation-BC250.md` : kargs rpm-ostree `amdgpu.gttsize=14750` | **Spécification cible** (doc v6, kargs rpm-ostree) | Partie du triplet kargs BC-250 |
| **ttm.page_pool_size = 3014656** | `Prof-IA-v6-Documentation-BC250.md` : kargs rpm-ostree | **Spécification cible** (doc v6) | Partie du triplet kargs BC-250 |
| **Mesa 25+ / RADV** | `BC-250-INSTALL-GUIDE.md` : « Mesa 25+ / RADV Vulkan » ; `Prof-IA-v6-Documentation-BC250.md` : « Mesa 25+ / RADV Vulkan » | **Spécification cible** (docs BC-250) | Minimum pour Vulkan stable sur gfx1013 |
| **RADV_DEBUG = nohiz** | `BC-250-INSTALL-GUIDE.md` : `RADV_DEBUG=nohiz` (ROCm/Mesa) | **Recommandation cible** (guide install) | Stabilise RADV sur gfx1013 |
| **VK_ICD_FILENAMES = radeon_icd.x86_64.json** | `deploy/systemd/profia-llama.service` : `Environment="VK_ICD_FILENAMES=..."` ; ADR-002 | **Configuration active** (service systemd, ADR-002) | Force RADV, évite conflit NVIDIA/AMD |

---

## 3. Statuts explicites par composant

| Composant | Statut | Commentaire |
|-----------|--------|-------------|
| Kernel 6.18 LTS | **requis cible** | Non validé sur dev ; guide install BC-250 |
| Kernel 7.2.6 backports | **disponible dev** | `apt -t trixie-backports show linux-image-amd64` |
| Mesa ≥ 25.1 | **requis cible** | Doc BC-250 « Mesa 25+ » |
| Mesa 25.2.6+ backports | **disponible dev** | `apt -t trixie-backports show mesa-vulkan-drivers` |
| 40 CU unlock | **requis cible** | Mesure `dmesg active_cu_number=40` sur BC-250 uniquement |
| UMR runtime 40 CU | **action requise** | `bc250-cu-live-manager.sh` via `umr` (pas patch noyau MastaG archivé) |
| UMA_SIZE=512 | **requis cible** | CMOS `bc250memcfg` ; audit B1 |
| ttm.pages_limit=3014656 | **requis cible** | karg rpm-ostree ; audit B1 correction |
| amdgpu.gttsize=14750 | **requis cible** | karg rpm-ostree ; triplet BC-250 |
| Mesa ≥ 25.1 / RADV | **requis cible** | Doc BC-250 « Mesa 25+ / RADV Vulkan » |
| RADV_DEBUG=nohiz | **recommandation cible** | Guide install BC-250 |
| VK_ICD_FILENAMES=radeon | **config active** | Service systemd, ADR-002 |

---

## 4. Stratégie de qualification — pas de modification du poste de dev

**Règle XZ** : aucun changement kernel/Mesa/drivers sur la machine de développement pour simuler la cible.

| Action | Sur dev | Sur BC-250 (cible) |
|--------|---------|-------------------|
| Kernel | Documenter versions (stable/backports) ; **ne pas upgrader** | Installer 6.18 LTS ou 7.x backport validé ; valider boot |
| Mesa | Documenter versions (stable/backports) ; **ne pas upgrader** | Backport 25.2+ ou compilation ; valider `vulkaninfo` |
| 40 CU | Documenter prérequis ; **ne pas patcher** | Appliquer UMR runtime (`bc250-cu-live-manager.sh`) ; valider `dmesg active_cu_number=40` |
| Split mémoire | Documenter kargs/UMR ; **ne pas modifier** | Appliquer `UMA_SIZE=512` + `ttm.pages_limit=3014656` ; valider `bc250-game-mode status` |
| Vulkan/RADV | Documenter ICD/debug ; tester si possible | Forcer `radeon_icd` + `RADV_DEBUG=nohiz` ; valider `vulkaninfo` + `llama.cpp -lv 5` |

---

## 5. Preuves d'état actuel (dev)

```bash
# Kernel
uname -r
# → 6.12.111 (mesuré)

# Mesa
glxinfo | grep "Mesa"
# → 25.0.x (mesuré)

# Backports disponibles
apt -t trixie-backports show linux-image-amd64 mesa-vulkan-drivers 2>/dev/null | grep Version
# → kernel 7.2.6, mesa 25.2.6+ (mesuré)

# Vulkan
vulkaninfo --summary | grep -i "device name\|driver"
# → device AMD RADV (si dispo)
```

---

## 6. Hors périmètre G1.1

- Compilation kernel 6.18.18 sur dev — **non requis**, documenté seulement
- Upgrade Mesa 25.2+ sur dev — **non requis**, documenté seulement
- Patch 40 CU sur dev — **interdit** (règle XZ : pas de modif système pour simuler cible)
- Validation thermique / mémoire unifiée / 40 CU / stabilité RADV prolongée — **gate G2+**, hors G1.1

---

## 7. Notes

- La valeur « 6.18.18 » exacte n'apparaît pas dans les docs BC-250 : le guide dit « 6.18 LTS ». La version ponctuelle 6.18.18 est une **hypothèse de version LTS courante**, non une exigence documentée. Marquée comme telle.
- Le triplet kargs `amdgpu.gttsize=14750 ttm.pages_limit=3014656 ttm.page_pool_size=3014656` vient de la doc v6 et de l'audit B1. Le `page_pool_size` dupliquant `pages_limit` est **hérité de la doc v6**, non re-validé indépendamment.
- `UMR runtime` vs `patch noyau MastaG` : l'audit consolidated (17/09/2026) archive le patch noyau ; le guide install BC-250 prescrit `bc250-cu-live-manager.sh` via `umr`. La décision est **documentée**, non re-démontrée ici.
- Aucune valeur de ce document ne doit être citée comme « validée BC-250 » sans mesure sur la cible physique.

---

**Fin du document.** Ce fichier ne contient **aucune valeur non sourcée**. Toute promotion dans `INSTALLATION.md` ou docs officielles doit conserver cette traçabilité.