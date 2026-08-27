# Frontend – Prof-IA UI Stack

**Purpose**: React‑based user interface exposing the RAG assistant and vault navigation.

## Structure
```
frontend/
├── src/                 # React source tree
│   ├── components/     # Reusable UI pieces
│   ├── pages/          # Top‑level views (chat, dashboard, minimal)
│   └── routes/         # React Router definitions
├── public/              # Static assets
├── Dockerfile           # Production image
└── package.json        # Dependencies & scripts
```

## Where to Look
| Task | Location | Notes |
|------|----------|-------|
| Add new UI component | `frontend/src/components/` | Follow the `AtomicDesign` pattern |
| Extend routing | `frontend/src/routes/` | Keep path‑case kebab‑typescript |
| Customize theme | `frontend/src/theme/` | Edit CSS variables only |

## Code Map
- **Routing**: `frontend/src/routes/AppRoutes.tsx`
- **Theme**: `frontend/src/theme/ThemeProvider.tsx`
- **Root entry**: `frontend/src/index.tsx`
- **Asset handling**: `frontend/public/`

## Conventions
- Function components with TypeScript typings.
- Styled‑components via CSS modules (`*.module.css`).
- Prop interfaces defined in adjacent `__types__.ts`.
- Linting via `eslint` with `airbnb` baseline.
- Tests live in `__tests__` folders; coverage ≥ 80 %.

## Anti‑Patterns
- Direct DOM mutation – use React state changes.
- Prop drilling without context – refactor to Context API or custom hook.
- Hard‑coded URLs – retrieve API base from `.env` at build time.

## Commands
```bash
# Install deps
npm ci

# Run dev server
npm run dev

# Build for production
npm run build
```

## Notes
- Environment variables in `.env.example` must be pre‑populated for CI.
- All UI strings are i18n‑ready; new UI text must be added to `i18n/additions.json`.
- Image assets must be placed under `public/` to be served statically.