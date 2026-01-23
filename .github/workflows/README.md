# GitHub Actions Workflows

This directory contains CI/CD workflows for toyoura-nagisa.

## Workflows

### Test & Lint (`test.yml`)

Runs on every push to master, main, or develop branches, and on all pull requests.

**Jobs:**

1. **Test** - Runs tests across Python 3.10, 3.11, and 3.12
   - Installs dependencies with `uv`
   - Runs pytest with coverage
   - Uploads coverage to Codecov (Python 3.11 only)

2. **Lint & Type Check**
   - Runs Ruff linter
   - Runs Ruff formatter check
   - Runs mypy type checker

3. **Security Scan**
   - Runs bandit security checker
   - Uploads security report as artifact

## Running Locally

### Prerequisites

```bash
# Install uv
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install dependencies
uv sync --all-extras
```

### Run Tests

```bash
# Run all tests with coverage
uv run pytest

# Run specific test file
uv run pytest packages/backend/tests/domain/models/test_messages.py

# Run without coverage (faster)
uv run pytest --no-cov
```

### Run Linters

```bash
# Run Ruff linter
uv run ruff check packages/backend

# Auto-fix issues
uv run ruff check packages/backend --fix

# Check formatting
uv run ruff format packages/backend --check

# Auto-format
uv run ruff format packages/backend
```

### Run Type Checker

```bash
# Run mypy
uv run mypy packages/backend --ignore-missing-imports
```

### Run Security Scanner

```bash
# Install bandit
uv run pip install bandit[toml]

# Run bandit
uv run bandit -r packages/backend
```

## Coverage Reports

Coverage reports are generated in the following formats:

- **Terminal**: Displayed during test run
- **HTML**: `htmlcov/index.html` (open in browser)
- **XML**: `coverage.xml` (for Codecov integration)

### View HTML Coverage Report

```bash
# Generate coverage
uv run pytest

# Open in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Configuration Files

- `pytest.ini` - Pytest and coverage configuration
- `pyproject.toml` - Ruff and mypy configuration
- `.gitignore` - Ignores coverage and cache files

## Current Coverage Target

- **Minimum**: 10% (will be increased gradually)
- **Goal**: 80%

## Codecov Integration

To enable Codecov integration:

1. Sign up at https://codecov.io/
2. Add your repository
3. Get the upload token
4. Add `CODECOV_TOKEN` to GitHub repository secrets
   - Settings → Secrets and variables → Actions → New repository secret

## Badge (Add to README)

```markdown
[![Test & Lint](https://github.com/yusong652/toyoura-nagisa/actions/workflows/test.yml/badge.svg)](https://github.com/yusong652/toyoura-nagisa/actions/workflows/test.yml)
[![codecov](https://codecov.io/gh/yusong652/toyoura-nagisa/branch/master/graph/badge.svg)](https://codecov.io/gh/yusong652/toyoura-nagisa)
```
