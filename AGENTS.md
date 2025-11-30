# Repository Guidelines

## Project Structure & Module Organization
toyoura-nagisa is split into service-focused folders. `backend/` holds the FastAPI app using a layered structure (`application/`, `domain/`, `infrastructure/`, `presentation/`, `shared/`). Place backend tests in `backend/tests/` beside the feature they verify. `frontend/` delivers the React + Vite client (UI in `src/`, static assets in `public/`). `pfc-server/` is an optional companion for ITASCA PFC integration. Reference material lives in `docs/` and `examples/`; automation scripts and adapters sit in `scripts/` and `workspace/`.

## Build, Test, and Development Commands
Install backend dependencies with `uv sync` and run the API locally via `uv run python backend/run.py`. Frontend dependencies install with `npm run install:frontend`; start both tiers together with `npm run dev`, or run them separately using `npm run start:backend` and `npm run start:frontend`. Validate updates with `uv run pytest backend/tests` (optionally `--cov backend`), `npm run lint` from `frontend/`, and `npm run build`.

## Coding Style & Naming Conventions
Python targets 3.10+, sticks to 4-space indentation, and relies heavily on type hints. Use Ruff for static checks (`npm run lint:backend`) and formatting (`npm run format:backend`). Follow snake_case for modules and functions, while classes remain PascalCase. Frontend code is TypeScript-first: keep React components in PascalCase files (`NagisaAvatar.tsx`) and hooks/utilities in camelCase. Resolve ESLint warnings before commit.

## Testing Guidelines
Prefer pytest for backend logic, covering new tool flows, memory behaviors, and error branches. Use descriptive test names (`test_<feature>_<condition>`) and reuse fixtures when mocking provider responses. Capture WebSocket behaviours with async client tests where possible. For UI changes, linting is the minimum gate; add targeted Jest or Vite smoke checks when you touch rendering logic, and describe any manual PFC validation in the PR.

## Commit & Pull Request Guidelines
The git history follows Conventional Commits (`feat:`, `fix:`, `refactor:`). Keep subjects under 70 characters and include issue references in the body when relevant. PRs should ship a concise summary, a checklist of verification commands, screenshots or recordings for UI updates, and a note about new configuration flags. Request reviews from maintainers responsible for touched layers.

## Security & Configuration Tips
Copy settings from `backend/config_example/` into `backend/config/` and store provider keys via environment variables or local `.env` files—never commit secrets. Confirm Live2D assets and memory snapshots stay out of version control, and rotate exposed API keys immediately.
