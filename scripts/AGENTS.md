# Scripts – Utility Helpers

**Purpose**: Collection of command‑line utilities used across the project for hardware unlock, line‑length checks, and maintenance tasks.

## Structure
```
scripts/
├── bazzite/                 # BC‑250 research toolkit (source from external repo)
│   ├── install.sh           # Full setup (driver, unlock, OC)
│   └── README.md            # Usage guide
├── bc250/                   # Direct BC‑250 helpers
│   └── unlock_helper.py     # Python wrapper around SMU tools
├── check_long_lines.py      # Linter for line length (>120 chars)
└── unlock-40cu.sh           # Shell script to unlock 40 CUs on BC‑250 GPU
```

## Where to Look
| Task | Location | Notes |
|------|------------|-------|
| Unlock additional GPU CUs | `scripts/bc250/unlock_helper.py` | Run with elevated privileges |
| Batch‑process line length violations | `scripts/check_long_lines.py` | Fails on files >120 characters |
| Automate GPU unlock at boot | `scripts/unlock-40cu.sh` | Hook into systemd service |

## Code Map
- **Unlock logic**: `scripts/bc250/unlock_helper.py` → calls `smu_tool` binary
- **Line‑length checker**: `scripts/check_long_lines.py` → uses `flake8` under the hood
- **Shell unlock**: `scripts/unlock-40cu.sh` → writes to `/sys/kernel/debug/clock_force` (if enabled)

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

# Unlock extra CUs (requires sudo)
sudo scripts/bc250/unlock_helper.py --cu-count 40

# Apply unlock script at boot (systemd)
sudo cp scripts/unlock-40cu.sh /usr/local/bin/
sudo systemctl enable unlock-40cu.service
```

## Notes
- The BC‑250 unlock process modifies kernel parameters; verify stability after reboot.
- `check_long_lines.py` respects `.flake8` config; add overrides there if needed.
- All scripts in `scripts/` are cached in the CI PATH for quick access.