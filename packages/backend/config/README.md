# Backend Config Policy

This directory is version-controlled.

## What belongs here

- Non-secret defaults used by the backend runtime (`dev.py`, `pfc.py`, `cors.py`, `__init__.py`)
- Prompt files for backend behavior (optional location, see prompt resolution below)

## What should NOT be committed

- API keys, tokens, credentials
- Machine-specific overrides (local paths, private endpoints, personal debug flags)

Use environment variables in `packages/backend/.env` for sensitive or local-only values.

## PFC config scope

`pfc.py` is intentionally minimal now:

- `PFC_PATH` (optional, used for environment display)
- `PFC_WORKSPACE` (optional workspace fallback)

Runtime PFC bridge startup is not controlled by backend config flags.

## Local override area

Local-only config files can be placed under:

- `packages/backend/config/local/`

The folder exists for developer overrides and is git-ignored (except `.gitkeep`).

## Prompt resolution order

Prompt loading now checks directories in this order:

1. `config/prompts/` (repo root, shared target)
2. `packages/backend/config/prompts/` (backend-local)

This keeps backend behavior stable while allowing shared prompt ownership at root level.
