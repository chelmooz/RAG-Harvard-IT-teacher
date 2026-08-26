# Guide d'installation BC-250 — Station de jeu + serveur RAG (Bazzite)

Guide **facile**, copier-coller, de la mise sous tension jusqu'à la vérification des
services. Pour le « pourquoi » technique, voir `vault/docs/superpowers/specs/2026-08-26-bc250-bazzite-deployment.md`.

> OS retenu : **Bazzite** (Fedora immutable, `rpm-ostree`). Tout est **local / FREE**,
> aucun cloud. Le BC-250 = AMD Cyan Skillfish / RDNA2 / **gfx1013** (PCI `1002:13fe`).

---

## 0. Prérequis & avertissements

**Matériel**
- Alim **≥ 460 W** correctement câblée. Le connecteur **8-pin PCIe** doit être câblé avec la
  bonne polarité (12V vs GND) — une inversion **détruit la carte définitivement**.
- Câble **DisplayPort 1.4** (le BC-250 n'a **pas** de HDMI — utiliser adaptateur DP→HDMI si besoin).
- (Optionnel) Dongle **Bluetooth USB** pour le son (BlueZ/PipeWire natifs, aucun driver).
- (Recommandé sécurité) Programmateur **CH347** pour sauvegarder/restaurer le BIOS SPI.

**Risques (lire avant de flasher)**
- ⚠️ **Vid CPU > 1325 mV = brick matériel.** On reste sous 1300 mV (profil « Mild »).
- ⚠️ **Flashage BIOS** mal fait = carte brickée. La méthode `bc250_memcfg` (Étape 2) évite le flash
  pour le split VRAM. Le flash n'est utile que pour les menus chipset / 8 cœurs via BIOS.
- ⚠️ **IOMMU** doit rester **désactivé** (casse l'affichage sur BC-250).
- ⚠️ Éviter les noyaux **6.15.0–6.15.6** et **6.17.8–6.17.10** (affichage cassé). Préférer 6.18 LTS
  ou 6.17.11+.

---

## Étape 1 — Flashage du BIOS (optionnel)

> **À faire seulement si** tu veux les menus chipset débloqués ou le déblocage 8 cœurs « propre ».
> Pour le seul split VRAM, passe à l'Étape 2 (méthode `bc250_memcfg`, aucun flash).

1. **Sauvegarde (CH347)** — lire la puce SPI avec `flashrom -p ch347_spi -r backup_stock.bin`,
   puis `diff backup_stock.bin backup_verify.bin` pour confirmer.
2. **Télécharger** l'EFI kit (utilitaires de flash) + le BIOS moddé. Références communautaires :
   - `BC250_3.00_CHIPSETMENU.ROM` (moddé P3.00, VRAM + chipset, **recommandé**) — sha256
     `48fbe5d366e6a56e2fdffdca848426216ba1f083610dab63db89d2f4e6c940b5`
   - `Robin5.00` (stock P5.00) — sha256
     `0d6f136cb120cf3b2de26d5c4d7f255604fdbf4b9442af5ba55419b95b89aa82`
3. **Clé USB FAT32** (≤32 Go) : y mettre l'EFI kit + le `.ROM`.
4. **Flash en EFI Shell** ( BIOS → boot sur la clé) :
   ```bash
   # depuis l'invite EFI Shell, sur le volume de la clé (fs0:)
   fs0:
   cd \<dossier_outils>
   # flash du BIOS moddé (commande exacte selon l'outil fourni dans l'EFI kit)
   <outil_flash> BC250_3.00_CHIPSETMENU.ROM
   ```
   ⚠️ Si le flash « hang » en cours → **ne pas rebooter**, attendre 15 min.
5. **Clear CMOS** (jumper 20 s ou batterie) → reset aux défauts, applique bien le split.
6. Reboot, **Del** pour entrer dans le BIOS → passe à l'Étape 2.

---

## Étape 2 — Réglages BIOS (à faire même sans flash)

Entre dans le BIOS (**Del** au boot). Navigue **Chipset → GFX Configuration** et **Advanced → CPU Configuration**.

| Réglage | Valeur | Pourquoi |
|---|---|---|
| Integrated Graphics Controller | **Forces** | Active l'iGPU |
| UMA Mode | **UMA_SPECIFIED** | Autorise le split VRAM manuel |
| **UMA Frame Buffer Size** | **512MB** (dynamique) | ⚠️ **Garde 512 Mo**, ne passe PAS au preset 4/12 Go (le vrai plafond est le karg `ttm.pages_limit`, posé à l'Étape 4) |
| IOMMU | **Disabled** | Obligatoire (sinon écran noir) |
| Boot Mode | **UEFI** | Standard |

> Le split réel 12 Go GPU / 4 Go CPU est imposé par l'OS (karg), pas par ce menu. 512 Mo = le
> *minimum* réservé ; le GPU grossit jusqu'au plafond dynamiquement.

**Si BIOS stock (pas flashé)** et que tu veux changer la taille VRAM depuis Linux sans flasher :
```bash
git clone https://github.com/fanoush/bc250_memcfg && cd bc250_memcfg && make
sudo ./bc250memcfg UMA_SIZE 512      # 512 = 512 Mo dynamique (recommandé)
```

**F10** (Save & Exit).

---

## Étape 3 — Installation de Bazzite

1. Télécharger **Bazzite Desktop (AMD, Stable)** depuis bazzite.gg.
2. Graver la clé USB :
   ```bash
   # depuis une machine Linux ; ou Fedora Media Writer / balenaEtcher sur Windows
   sudo dd if=bazzite.iso of=/dev/sdX bs=4M status=progress oflag=sync
   ```
3. Booter sur la clé, lancer l'installateur, installer sur le disque (effacement conseillé).
4. Reboot, créer le compte utilisateur, ouvrir un terminal.

---

## Étape 4 — Drivers & provisioning (notre script)

Le script `scripts/bazzite/setup.sh` configure **tout** : kargs VRAM, governor SMU, variables ROCm,
dépendances (`umr`, `python3`), install du service d'optimisations, swapper JEU⇄RAG, et monitoring.

```bash
# Récupérer le dépôt du projet (ou copier le dossier scripts/ sur la machine)
git clone <repo-projet> bc250-deploy && cd bc250-deploy
# ou : copier scripts/ via clé USB

cd scripts/bazzite
./setup.sh
```

> **Note** : les scripts `.sh` n'ont pas besoin d'être rendus exécutables manuellement —
> `setup.sh` s'en charge automatiquement (`chmod +x` sur `/opt/bc250/*.sh` et installation
> de `bc250-game-mode` dans `/usr/local/bin`). Si tu dois les lancer hors `setup.sh` :
> ```bash
> chmod +x scripts/bc250/*.sh
> sudo cp scripts/bc250/bc250-game-mode.sh /usr/local/bin/bc250-game-mode
> sudo chmod +x /usr/local/bin/bc250-game-mode
> ```

Le script fait, dans l'ordre :
1. `rpm-ostree kargs --append-if-missing="ttm.pages_limit=3014656"` → split 12/4 Go.
2. Install governor `cyan-skillfish-governor-smu` (COPR `filippor/bazzite`).
3. Export `HSA_OVERRIDE_GFX_VERSION=10.1.3` + `RADV_DEBUG=nohiz` (ROCm/Mesa).
4. Install `umr` + `python3` (dépendances des scripts SMU/UMR).
5. Copie `scripts/bc250/` → `/opt/bc250`, install + enable `bc250-optimizations.service`.
6. Installe `bc250-game-mode` dans `/usr/local/bin`.
7. Monitoring : `btop htop amdgpu_top mangohud` + `bc250-gpu-fix` (fix util GPU 655 %).

> **Reboot obligatoire** après (kargs + paquets rpm-ostree).

### Si le COPR governor est absent
Le script warning ; installe manuellement depuis `https://copr.fedorainfracloud.org/coprs/filippor/bazzite/`
ou laisse le défaut (les scripts 40 CU fonctionnent sans le governor, qui sert surtout aux limites).

---

## Étape 5 — Vérification des services (rôles & dépendances)

Après reboot, vérifie chaque brique. **Rôles** et **dépendances** :

| Service / outil | Rôle | Dépend de | Vérification |
|---|---|---|---|
| `bc250-optimizations.service` | Orchestre 40 CU + 8 cœurs + UV/OC au boot | `umr`, `python3`, `bc250_smu` | `systemctl status bc250-optimizations` → `active` |
| `apply_phase1.sh` | Enchaîne les 3 étapes + health-check | les 3 scripts ci-dessous | `sudo /opt/bc250/health-check.sh` → `OK` |
| `bc250-cu-live-manager.sh` | **40 CU** via UMR (registres gfx1013) | `umr` | `sudo dmesg | grep active_cu_number` → `40` |
| `bc250-unlock-cores.py` | **8 cœurs** Zen2 via SMU | `python3` | `nproc` → `16` (8c/16t) |
| `bc250_apply.py` | **UV/OC CPU** (profil Mild) | `python3` + `bc250_smu/` | `sudo dmesg | grep -i smu` (pas d'erreur) |
| `bc250-game-mode` | Bascule JEU⇄RAG (libère/réserve VRAM) | Ollama | `bc250-game-mode status` |
| `bc250-gpu-fix.service` | Corrige util GPU bloquée à 655 % | rust (build) ou binaire | `systemctl status bc250-gpu-fix` + `btop` affiche % réel |
| `validate.sh` | Batterie de validation (CU/cœurs/VRAM/temp/**tension ≤1300 mV**/services + score) | outils ci-dessus | `sudo /opt/bc250/validate.sh` → score 100% |

**Commandes de vérif (copier-coller) :**
```bash
# Service d'optimisations (40 CU / 8c / UV-OC)
systemctl status bc250-optimizations --no-pager
sudo /opt/bc250/health-check.sh
sudo dmesg | grep -i "active_cu_number" | tail -3
nproc                      # attendu 16

# GPU / monitoring
amdgpu_top                 # util CU, clocks, temp, power (Ctrl+C pour quitter)
btop                       # vue globale (après fix : % GPU correct)

# Swapper mémoire
bc250-game-mode status     # montre Ollama + mémoire + karg ttm actif
```

> Si `health-check.sh` échoue → le service **retente** (Restart=on-failure, max 3/2 min) puis
> lâche proprement (pas de bootloop). Cause typique : silicon/VRM refuse l'OC → revoir le profil.

---

## Étape 6 — Serveur RAG (Prof-IA)

Le déploiement RAG principal (backend FastAPI + Ollama + Postgres/pgvector) est géré à la racine
du dépôt (voir `README.md`). En résumé sur le BC-250 :
```bash
# à la racine du projet (après Étape 4)
docker compose up -d
ollama pull qwen3:14b      # ~9,3 Go, tient en VRAM (12 Go)
# vérifier que le modèle est en GPU :
amdgpu_top                 # la ligne VRAM doit monter ~9 Go après un premier query
```

---

## Étape 7 — Stress test & validation finale (OBLIGATOIRE avant prod)

```bash
# Validation automatisée (score + garde-fou tension dur 1300 mV) :
sudo /opt/bc250/validate.sh
# -> vérifie 8c/40CU/VRAM 512Mo/services/temp/tension, propose stress-ng + FurMark

# Stress manuel complémentaire :
stress-ng --cpu 16 --timeout 300s
# GPU 40 CU (Vulkan) — ex. llama-bench ou un jeu Steam/Proton
amdgpu_top
```
Surveille `dmesg` pour toute erreur SMU/AMDGPU. Si crash/instable → réduire le profil UV/OC
(`bc250_apply.py` → éditer `frequency`/`scale`) et reboote.

---

## Dépannage rapide

- **Écran noir au boot** → kernel à éviter (6.15.0–6.15.6 / 6.17.8–6.17.10) ; boot sur 6.18 LTS.
- **Audio DP lent/crachouillant** → bug horloge DP connu ; pour l'instant **Bluetooth + enceinte**
  (choix retenu). Audio DP 5.1 différé (patch noyau `DCCG_AUDIO_DTO1_MODULE=6000000`).
- **Ollama hors VRAM** → vérifier `ttm.pages_limit=3014656` (`bc250-game-mode status`) et que le
  profil est bien « rag » (`bc250-game-mode rag`).
- **40 CU non pris** → `umr` installé ? `systemctl restart bc250-optimizations`.

---

## Résumé des dépendances

```
setup.sh
 ├─ kargs ttm.pages_limit=3014656   (split 12/4 Go)
 ├─ kargs zswap.enabled=1 + mitigations=off   (anti-crash RAM/VRAM, reboot requis)
 ├─ swapfile Btrfs 32G (/var/swap) + vm.swappiness=120
 ├─ governor cyan-skillfish (COPR)  (limites GPU) + /etc/cyan-skillfish-governor/config.toml
 ├─ umr          ─────────────────► 40 CU (bc250-cu-live-manager.sh : enable all + write-service-table)
 ├─ python3 + bc250_smu ──────────► 8 cœurs (bc250-unlock-cores.py apply)
 │                                 └► UV/OC  (bc250_detect.py -> bc250_apply.py --apply)
 ├─ bc250-optimizations.service ──► apply_phase1.sh → health-check.sh
 ├─ validate.sh (batterie de validation + score)
 ├─ bc250-game-mode (usr/local/bin)
 └─ monitoring: btop htop amdgpu_top mangohud + bc250-gpu-fix + lm_sensors
```
