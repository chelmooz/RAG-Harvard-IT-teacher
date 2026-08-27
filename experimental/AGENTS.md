# Experimental – Future Work and Fine‑Tuning Playground

**Purpose**: Holds prototype implementations, exploratory notebooks, and emerging features that are not yet part of the stable stack.

## Structure
```
experimental/
├── README.md                # Index of ongoing experiments
├── fine_tuning/             # LoRA / SFT training scripts and configs
│   ├── config.yaml
│   └── train.py
└── drafts/                  # Unpublished design docs and architecture sketches
    └── design‑sketch.md
```

## Where to Look
| Task | Location | Notes |
|------|----------|-------|
| Propose a new experiment | `experimental/README.md` | Add a bullet with short title + link to folder |
| Run a fine‑tuning job | `experimental/fine_tuning/train.py` | Follow `config.yaml` hyper‑parameters |
| Review upcoming design | `experimental/drafts/` | Designs are mutable; flag `WIP` in title |

## Code Map
- **Experiment registry**: `experimental/README.md` → bullet list + links.
- **Training script**: `experimental/fine_tuning/train.py` → loads `config.yaml`.
- **Design sketches**: `experimental/drafts/*.md` → markdown proposals.

## Conventions
- All experiments must include `status: draft` front‑matter tag.
- Naming convention: `<topic>-<owner>-<date>` (e.g., `rag‑summarization‑john‑2026-09-01`).
- Keep experiments self‑contained; avoid importing from `backend/` or `frontend/` unless gated behind a feature flag.
- Delete or graduate experiments after 90 days of inactivity.

## Anti‑Patterns
- Persisting experimental data in `backend/` or `frontend/` without a deprecation plan.
- Using production‑grade scripts (e.g., LoRA trainer) without proper testing harness.
- Mixing stable code with raw prototype code in the same module.

## Commands
```bash
# List registered experiments
grep -E '^\s*-\s' experimental/README.md

# Run a specific fine‑tuning job (example: summarization)
cd experimental/fine_tuning
python train.py --config config.yaml --name summarization
```

## Notes
- Experiments are **not** part of the release pipeline; they are evaluated manually.
- When an experiment reaches `status: stable`, move its folder to the appropriate top‑level directory and add an `AGENTS.md` there.
- Share experimental designs on the team channel before committing large data files.