# BC-250 Install Guide — Gaming Station + RAG Server (Bazzite)

**Easy**, copy-paste guide from power-on to service verification. For the technical "why", see `vault/docs/superpowers/specs/2026-08-26-bc250-bazzite-deployment.md`.

> OS chosen: **Bazzite** (Fedora immutable, `rpm-ostree`). Everything is **local / FREE**, no cloud. The BC-250 = AMD Cyan Skillfish / RDNA2 / **gfx1013** (PCI `1002:13fe`).

---

## 0. Prerequisites & Warnings

**Hardware**
- PSU **≥ 460 W** properly wired. The **8-pin PCIe** connector must be wired with correct polarity (12V vs GND) — reversal **destroys the card permanently**.
- **DisplayPort 1.4** cable (the BC-250 has **no HDMI** — use DP→HDMI adapter if needed).
- (Optional) **Bluetooth USB dongle** for audio (BlueZ/PipeWire native, no drivers).
- (Recommended for safety) **CH347 programmer** to backup/restore BIOS SPI.

**Risks (read before flashing)**
- ⚠️ **CPU Vid > 1325 mV = hardware brick.** We stay under 1300 mV (Mild profile).
- ⚠️ **Bad BIOS flash = bricked card.** The `bc250_memcfg` method (Step 2) avoids flashing for VRAM split. Flash is only useful for chipset menus / 8-core unlock via BIOS.
- ⚠️ **IOMMU must stay Disabled** (breaks display on BC-250).
- ⚠️ Avoid kernels **6.15.0–6.15.6** and **6.17.8–6.17.10** (broken display). Prefer 6.18 LTS or 6.17.11+.

---

## Step 1 — BIOS Flash (Optional)

> **Do this ONLY if** you want unlocked chipset menus or "clean" 8-core unlock.
> For VRAM split only, skip to Step 2 (method `bc250_memcfg`, no flash).

1. **Backup (CH347)** — read SPI chip with `flashrom -p ch347_spi -r backup_stock.bin`,
   then `diff backup_stock.bin backup_verify.bin` to confirm.
2. **Download** EFI flash kit + modded BIOS. Community references:
   - `BC250_3.00_CHIPSETMENU.ROM` (modded P3.00, VRAM + chipset, **recommended**) — sha256
     `48fbe5d366e6a56e2fdffdca848426216ba1f083610dab63db89d2f4e6c940b5`
   - `Robin5.00` (stock P5.00) — sha256
     `0d6f136cb120cf3b2de26d5c4d7f255604fdbf4b9442af5ba55419b95b89aa82`
3. **FAT32 USB key** (≤32 GB): put EFI kit + `.ROM` on it.
4. **Flash in EFI Shell** (BIOS → boot from USB):
   ```bash
   # from EFI Shell prompt, on key volume (fs0:)
   fs0:
   cd \<tools_folder>
   # flash modded BIOS (exact command depends on tool provided in EFI kit)
   <flash_tool> BC250_3.00_CHIPSETMENU.ROM
   ```
   ⚠️ If flash "hangs" mid-way → **do not reboot**, wait 15 min.
5. **Clear CMOS** (jumper 20s or remove battery) → reset to defaults, applies split.
6. Reboot, **Del** to enter BIOS → continue to Step 2.

---

## Step 2 — BIOS Settings (Do Even Without Flash)

Enter BIOS (**Del** at boot). Navigate **Chipset → GFX Configuration** and **Advanced → CPU Configuration**.

| Setting | Value | Why |
|---|---|---|
| Integrated Graphics Controller | **Forces** | Enables iGPU |
| UMA Mode | **UMA_SPECIFIED** | Allows manual VRAM split |
| **UMA Frame Buffer Size** | **512MB** (dynamic) | ⚠️ **Keep 512 MB**, do NOT switch to 4/12 GB preset (real ceiling is karg `ttm.pages_limit` set at Step 4) |
| IOMMU | **Disabled** | Mandatory (else black screen) |
| Boot Mode | **UEFI** | Standard |

> The real 12 GB GPU / 4 GB CPU split is enforced by OS (karg), not this menu. 512 MB = the
> *minimum* reserved; GPU grows dynamically up to the karg ceiling.

**If stock BIOS (not flashed)** and you want to change VRAM size from Linux without flashing:
```bash
git clone https://github.com/fanoush/bc250_memcfg && cd bc250_memcfg && make
sudo ./bc250memcfg UMA_SIZE 512      # 512 = 512 MB dynamic (recommended)
```

**F10** (Save & Exit).

---

## Step 3 — Install Bazzite

1. Download **Bazzite Desktop (AMD, Stable)** from bazzite.gg.
2. Flash USB key:
   ```bash
   # from a Linux machine; or Fedora Media Writer / balenaEtcher on Windows
   sudo dd if=bazzite.iso of=/dev/sdX bs=4M status=progress oflag=sync
   ```
3. Boot from key, run installer, install to disk (wipe recommended).
4. Reboot, create user account, open terminal.

---

## Step 4 — Drivers & Provisioning (Our Script)

The script `scripts/bazzite/setup.sh` configures **everything**: VRAM kargs, SMU governor, ROCm env vars,
dependencies (`umr`, `python3`), optimizations service install, JEU⇄RAG swapper, and monitoring.

```bash
# Get project repo (or copy scripts/ folder to machine)
git clone <project-repo> bc250-deploy && cd bc250-deploy
# or: copy scripts/ via USB key

cd scripts/bazzite
./setup.sh
```

> **Note**: the `.sh` scripts don't need manual `chmod +x` —
> `setup.sh` handles it automatically (`chmod +x` on `/opt/bc250/*.sh` and installs
> `bc250-game-mode` to `/usr/local/bin`). If you must run them outside `setup.sh`:
> ```bash
> chmod +x scripts/bc250/*.sh
> sudo cp scripts/bc250/bc250-game-mode.sh /usr/local/bin/bc250-game-mode
> sudo chmod +x /usr/local/bin/bc250-game-mode
> ```

The script does, in order:
1. `rpm-ostree kargs --append-if-missing="ttm.pages_limit=3014656"` → 12/4 GB split.
2. Install governor `cyan-skillfish-governor-smu` (COPR `filippor/bazzite`).
3. Export `HSA_OVERRIDE_GFX_VERSION=10.1.3` + `RADV_DEBUG=nohiz` (ROCm/Mesa).
4. Install `umr` + `python3` (dependencies for SMU/UMR scripts).
5. Copy `scripts/bc250/` → `/opt/bc250`, install + enable `bc250-optimizations.service`.
16. Install `bc250-game-mode` to `/usr/local/bin`.
17. Monitoring: `btop htop amdgpu_top mangohud` + `bc250-gpu-fix` (fix 655 % GPU util bug).

> **Reboot mandatory** after (kargs + rpm-ostree packages).

### If COPR Governor Missing
Script warns; install manually from `https://copr.fedorainfracloud.org/coprs/filippor/bazzite/`
or leave default (40 CU scripts work without governor, which mainly handles limits).

---

## Step 5 — Service Verification (Roles & Dependencies)

After reboot, verify each brick. **Roles** and **dependencies**:

| Service / Tool | Role | Depends On | Verification |
|---|---|---|---|
| `bc250-optimizations.service` | Orchestrates 40 CU + 8 cores + UV/OC at boot | `umr`, `python3`, `bc250_smu` | `systemctl status bc250-optimizations` → `active` |
| `apply_phase1.sh` | Chains 3 steps + health-check | 3 scripts below | `sudo /opt/bc250/health-check.sh` → `OK` |
| `bc250-cu-live-manager.sh` | **40 CU** via UMR (gfx1013 registers) | `umr` | `sudo dmesg | grep active_cu_number` → `40` |
| `bc250-unlock-cores.py` | **8 cores** Zen2 via SMU | `python3` | `nproc` → `16` (8c/16t) |
| `bc250_apply.py` | **UV/OC CPU** (Mild profile) | `python3` + `bc250_smu/` | `sudo dmesg | grep -i smu` (no error) |
| `bc250-game-mode` | JEU⇄RAG swap (free/reserve VRAM) | Ollama | `bc250-game-mode status` |
| `bc250-gpu-fix.service` | Fixes GPU util stuck at 655 % | rust (build) or binary | `systemctl status bc250-gpu-fix` + `btop` shows real % |
| `validate.sh` | Validation battery (CU/cores/VRAM/temp/**voltage ≤1300 mV**/services + score) | tools above | `sudo /opt/bc250/validate.sh` → score 100% |

**Verification commands (copy-paste):**
```bash
# Optimization service (40 CU / 8c / UV-OC)
systemctl status bc250-optimizations --no-pager
sudo /opt/bc250/health-check.sh
sudo dmesg | grep -i "active_cu_number" | tail -3
nproc                      # expected 16

# GPU / monitoring
amdgpu_top                 # CU util, clocks, temp, power (Ctrl+C to quit)
btop                       # global view (after fix: correct GPU %)

# Memory swapper
bc250-game-mode status     # shows Ollama + memory + active ttm karg
```

> If `health-check.sh` fails → service **retries** (Restart=on-failure, max 3/2 min) then
> exits cleanly (no bootloop). Typical cause: silicon/VRM refuses OC → adjust profile.

---

## Step 6 — RAG Server (Prof-IA)

Main RAG deployment (FastAPI backend + Ollama + Postgres/pgvector) lives at repo root
(see `README.md`). Summary on BC-250:
```bash
# at project root (after Step 4)
docker compose up -d
ollama pull qwen3:14b      # ~9.3 GB, fits in VRAM (12 GB)
# verify model runs on GPU:
amdgpu_top                 # VRAM line should jump ~9 GB after first query
```

---

## Step 7 — Stress Test & Final Validation (MANDATORY before prod)

```bash
# Automated validation (score + hard voltage guard 1300 mV):
sudo /opt/bc250/validate.sh
# -> checks 8c/40CU/VRAM 512MB/services/temp/voltage, offers stress-ng + FurMark

# Manual stress supplement:
stress-ng --cpu 16 --timeout 300s
# GPU 40 CU (Vulkan) — e.g. llama-bench or Steam/Proton game
amdgpu_top
```
Watch `dmesg` for any SMU/AMDGPU errors. If crash/unstable → lower UV/OC profile
(`bc250_apply.py` → edit `frequency`/`scale`) and reboot.

---

## Quick Troubleshooting

- **Black screen on boot** → avoid kernels 6.15.0–6.15.6 / 6.17.8–6.17.10; boot 6.18 LTS.
- **Slow/crackling DP audio** → known DP clock bug; for now **Bluetooth + speaker**
  (chosen). DP 5.1 deferred (kernel patch `DCCG_AUDIO_DTO1_MODULE=6000000`).
- **Ollama OOM / out of VRAM** → verify `ttm.pages_limit=3014656` (`bc250-game-mode status`) and
  profile is "rag" (`bc250-game-mode rag`).
- **40 CU not applied** → `umr` installed? `systemctl restart bc250-optimizations`.

---

## Dependency Summary

```
setup.sh
 ├─ kargs ttm.pages_limit=3014656   (12/4 GB split)
 ├─ kargs zswap.enabled=1 + mitigations=off   (anti-crash RAM/VRAM, reboot required)
 ├─ swapfile Btrfs 32G (/var/swap) + vm.swappiness=120
 ├─ governor cyan-skillfish (COPR)  (GPU limits) + /etc/cyan-skillfish-governor/config.toml
 ├─ umr          ─────────────────► 40 CU (bc250-cu-live-manager.sh : enable all + write-service-table)
 ├─ python3 + bc250_smu ──────────► 8 cores (bc250-unlock-cores.py apply)
 │                                 └► UV/OC  (bc250_detect.py -> bc250_apply.py --apply)
 ├─ bc250-optimizations.service ──► apply_phase1.sh → health-check.sh
 ├─ validate.sh (validation battery + score)
 ├─ bc250-game-mode (usr/local/bin)
 └─ monitoring: btop htop amdgpu_top mangohud + bc250-gpu-fix + lm_sensors
```

---

*Guide generated for BC-250 (Cyan Skillfish / RDNA2 / gfx1013) — Bazzite immutable OS.  
All local, FREE models (Ollama), no cloud. See spec for deep dive.*