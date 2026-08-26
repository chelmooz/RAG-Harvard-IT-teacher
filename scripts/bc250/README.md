# Outils d'optimisation BC-250 (Phase 1 — userspace, sans rebuild noyau)

Scripts vendored depuis les projets communautaires BC-250 (tous **MIT** —
voir `CREDITS.md` à la racine). Ils implémentent les leviers validés dans
`vault/docs/superpowers/specs/2026-08-26-bc250-bazzite-deployment.md`.

## Leviers

| Levier | Script | Source | Mécanisme |
|--------|--------|--------|-----------|
| 40 CU | `40cu-unlock/bc250-cu-live-manager.sh` | WinnieLV/bc250-cu-live-manager | UMR (registres gfx1013) |
| 8 cœurs Zen2 | `core-unlock/bc250-unlock-cores.py` | keyboardspecialist/bc250-steamos | SMU Q3 `0x98` → SMN `0x0115A870` |
| UV/OC CPU | `smu-oc/bc250_apply.py` (+ `bc250_smu/`) | bc250-collective/bc250_smu_oc | SMU `0x8F/0x50/0x8B/0x8C/0x9A` |
| Memory OC (GDDR6) | `mem-oc/mem_oc.sh` | toolkit maison (gardes) | sysfs `pp_od_clk_voltage` (si dispo) — sinon BIOS/CMOS |
| Orchestration | `apply_phase1.sh` | toolkit maison | 40 CU → 8c → UV/OC + health-check |
| Health-check | `health-check.sh` | toolkit maison | dmesg CU + nproc cœurs |
| Service boot | `bc250-optimizations.service` | toolkit maison | systemd `Restart=on-failure` + limite |
| Mode JEU/RAG | `bc250-game-mode.sh` | toolkit maison | libère/réserve VRAM Ollama |

Le split RAM/VRAM (12 Go GPU / 4 Go CPU) est géré par `scripts/bazzite/setup.sh`
(`rpm-ostree kargs ttm.pages_limit=3014656` + `UMA_SIZE=512` via CMOS).

## Garde-fous (À LIRE)

- **Vid CPU ≤ 1325 mV** sinon brick matériel. Le preset « Mild » (3500 MHz / scale −22 /
  80 °C) reste sous ce seuil (marge : viser ≤ 1300 mV).
- **GPU ≤ 2,2–2,4 GHz** en refroidissement air ; cap recommandé 1500 MHz / 900 mV pour 40 CU.
- **PSU ≥ 460 W**.
- Le déblocage 8 cœurs est **volatil au cold boot** → prévoir un service systemd au démarrage.
- **Stresser** 40 CU + 8 cœurs avant toute mise en prod.
- Tout est **non testé à l'exécution** en pré-déploiement (pas de machine) : valeurs issues
  de l'analyse communautaire, à valider sur le matériel réel.

## Utilisation

```bash
# 40 CU (UMR, nécessite umr + droits)
sudo ./40cu-unlock/bc250-cu-live-manager.sh

# 8 cœurs Zen2
python3 ./core-unlock/bc250-unlock-cores.py

# UV/OC CPU (éditer bc250_apply.py / config d'abord)
python3 ./smu-oc/bc250_apply.py
```

> Phase 2 (opt-in) : noyau Bazzite custom (patches MastaG/linux-cachyos-bc250 0001-0009)
> pour ROCm/embeddings GPU + async-compute jeu. Non inclus ici (rebuild noyau requis).
