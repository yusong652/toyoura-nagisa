# Contributing to Toyoura Nagisa

Thank you for your interest in contributing to Toyoura Nagisa!

## Development Setup

### Prerequisites

- Python 3.10 or higher
- [uv](https://github.com/astral-sh/uv) - Fast Python package installer

### Installation

```bash
# Clone the repository
git clone https://github.com/yusong652/toyoura-nagisa.git
cd toyoura-nagisa

# Install uv if not already installed
curl -LsSf https://astral.sh/uv/install.sh | sh

# Install all dependencies
uv sync --all-extras
```

## Running Tests

### Run All Tests

```bash
# Run all tests with coverage
uv run pytest

# Run tests without coverage (faster for development)
uv run pytest --no-cov
```

### Run Specific Tests

```bash
# Run a specific test file
uv run pytest packages/backend/tests/domain/models/test_messages.py

# Run a specific test function
uv run pytest packages/backend/tests/domain/models/test_messages.py::test_create_user_message_with_string_content

# Run tests matching a pattern
uv run pytest -k "test_user_message"
```

### View Coverage Report

```bash
# Generate HTML coverage report
uv run pytest

# Open coverage report in browser
open htmlcov/index.html  # macOS
xdg-open htmlcov/index.html  # Linux
```

## Code Quality

### Linting with Ruff

```bash
# Check for linting issues
uv run ruff check packages/backend

# Auto-fix linting issues
uv run ruff check packages/backend --fix

# Check code formatting
uv run ruff format packages/backend --check

# Auto-format code
uv run ruff format packages/backend
```

### Type Checking with mypy

```bash
# Run type checker
uv run mypy packages/backend --ignore-missing-imports
```

### Security Scanning

```bash
# Install bandit
uv run pip install bandit[toml]

# Run security scan
uv run bandit -r packages/backend
```

## Pull Request Process

1. **Fork the repository** and create your branch from `master`

2. **Install dependencies**:
   ```bash
   uv sync --all-extras
   ```

3. **Make your changes**:
   - Write clear, descriptive commit messages
   - Follow the existing code style
   - Add tests for new functionality

4. **Run tests and linters**:
   ```bash
   # Run all quality checks
   uv run pytest                                  # Tests
   uv run ruff check packages/backend --fix       # Linting
   uv run ruff format packages/backend            # Formatting
   uv run mypy packages/backend --ignore-missing-imports  # Type checking
   ```

5. **Ensure tests pass**:
   - All tests must pass
   - Coverage should not decrease
   - No linting errors
   - No type errors (within reason)

6. **Create your Pull Request**:
   - Provide a clear description of the changes
   - Reference any related issues
   - Include screenshots/videos for UI changes
   - Ensure CI/CD checks pass

## Coding Standards

### Python Code Style

- **Line length**: 120 characters
- **Quotes**: Double quotes for strings
- **Imports**: Organized by Ruff (stdlib → third-party → local)
- **Type hints**: Use type hints for function signatures
- **Docstrings**: Google style for public APIs

### Testing Standards

- **Coverage target**: Minimum 10% (gradually increasing to 80%)
- **Test naming**: `test_<functionality>_<scenario>`
- **Test organization**: Mirror source code structure in `tests/`
- **Fixtures**: Use pytest fixtures for setup/teardown

### Architecture Guidelines

- **Clean Architecture**: Follow separation of concerns
  - Domain: Business logic and models
  - Application: Use cases and orchestration
  - Infrastructure: External dependencies
  - Presentation: API routes and handlers

- **Dependency Rule**: Dependencies point inward
  - Infrastructure → Application → Domain
  - Never the reverse

## Commit Message Format

```
<type>: <subject>

Co-authored-by: Nagisa Toyoura <nagisa.toyoura@gmail.com>
```

### Types

- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `perf`: Performance improvements
- `build`: Build system changes
- `ci`: CI/CD changes

### Examples

```
feat: add support for OpenAI GPT-5 model

Co-authored-by: Nagisa Toyoura <nagisa.toyoura@gmail.com>
```

```
fix: resolve CORS configuration security vulnerability

Co-authored-by: Nagisa Toyoura <nagisa.toyoura@gmail.com>
```

## Project Structure

```
toyoura-nagisa/
├── packages/
│   └── backend/             # Python backend
│       ├── domain/          # Domain models and business logic
│       ├── application/     # Application services and use cases
│       ├── infrastructure/  # External dependencies
│       ├── presentation/    # API routes and handlers
│       ├── config/          # Configuration management
│       ├── shared/          # Shared utilities
│       └── tests/           # Test suite
├── pfc-mcp/
│   ├── src/pfc_mcp/         # MCP server package
│   └── pfc-bridge/          # PFC WebSocket bridge runtime
├── .github/
│   └── workflows/           # CI/CD workflows
├── pytest.ini               # Pytest configuration
└── pyproject.toml           # Project dependencies and tools
```

## Getting Help

- **Issues**: [GitHub Issues](https://github.com/yusong652/toyoura-nagisa/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yusong652/toyoura-nagisa/discussions)
- **Documentation**: See `.claude/` directory for additional guides

## License

By contributing, you agree that your contributions will be licensed under the GPL v3 License.
