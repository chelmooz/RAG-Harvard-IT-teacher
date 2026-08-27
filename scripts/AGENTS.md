# Scripts – Utility Helpers

**Purpose**: Collection of command‑line utilities used across the project for hardware unlock, line‑length checks, and maintenance tasks.

## Structure
```
scripts/
├── bazzite/                 # BC‑250 setup for Bazzite (rpm-ostree)
│   ├── setup.sh             # Full setup BC‑250 sur Bazzite (rpm-ostree)
│   └── README.md            # Usage guide
├── bc250/                   # Direct BC‑250 helpers (userspace, Bazzite)
│   ├── 40cu-unlock/         # 40 CU unlock via UMR (bc250-cu-live-manager.sh)
│   ├── smu-oc/              # CPU UV/OC via SMU
│   ├── core-unlock/         # 8‑core unlock
│   └── unlock_helper.py     # Python wrapper around SMU tools
└── check_long_lines.py      # Linter for line length (>120 chars)
```

## Where to Look
| Task | Location | Notes |
|------|------------|-------|
| Unlock additional GPU CUs | `scripts/bc250/40cu-unlock/bc250-cu-live-manager.sh` | UMR‑based, no kernel rebuild |
| Batch‑process line length violations | `scripts/check_long_lines.py` | Fails on files >120 characters |
| CPU UV/OC via SMU | `scripts/bc250/smu-oc/bc250_apply.py` | Run with elevated privileges |

## Code Map
- **Unlock logic**: `scripts/bc250/unlock_helper.py` → calls `smu_tool` binary
- **40 CU unlock**: `scripts/bc250/40cu-unlock/bc250-cu-live-manager.sh` → UMR (no rebuild)
- **Line‑length checker**: `scripts/check_long_lines.py` → uses `flake8` under the hood

## Conventions
- Scripts are idempotent where possible.
- All public scripts must have a corresponding entry in `README.md` under `## Scripts`.
- Temporary files are created in `/tmp/prof-ia-<random>` and cleaned up on exit.
- Error handling: exit code `1` on failure, non‑zero on misuse; print usage to stdout.

## Anti‑Patterns
- Direct hardware accesses without fallback – always check `$DISPLAY` and root rights.
- Ignoring environment variables – honor `PROF_IA_DEBUG=true` for verbose output.
- Hard‑coded paths – use `PROJECT_ROOT=$(git rev-parse --show-toplevel)` fallback.

## Commands
```bash
# Run line‑length audit
python scripts/check_long_lines.py .

# Unlock extra CUs via UMR (requires sudo, no kernel rebuild)
sudo scripts/bc250/40cu-unlock/bc250-cu-live-manager.sh
```

## Notes
- The BC‑250 unlock process modifies kernel parameters; verify stability after reboot.
- `check_long_lines.py` respects `.flake8` config; add overrides there if needed.
- All scripts in `scripts/` are cached in the CI PATH for quick access.