# Testing Guide for toyoura-nagisa

## Quick Start

```bash
# Run all tests
uv run pytest

# Run with coverage report
uv run pytest --cov=packages/backend --cov-report=html

# Run specific test file
uv run pytest packages/backend/tests/domain/models/test_messages.py

# Run specific test class
uv run pytest packages/backend/tests/domain/models/test_messages.py::TestUserMessage

# Run specific test function
uv run pytest packages/backend/tests/domain/models/test_messages.py::TestUserMessage::test_create_user_message_with_string_content
```

## Test Organization

```
packages/backend/tests/
├── conftest.py                 # Shared fixtures and pytest configuration
├── domain/                     # Domain layer tests (pure logic, no dependencies)
│   └── models/
│       ├── test_messages.py    # Message model tests
│       └── test_streaming.py   # Streaming chunk tests
├── application/                # Application layer tests (mocked dependencies)
│   └── services/
│       └── test_tool_executor.py  # Tool executor service tests
└── infrastructure/             # Infrastructure layer tests (integration tests)
    ├── llm/
    │   └── providers/
    └── mcp/
        └── tools/
```

## Test Types

### Unit Tests (packages/backend/tests/domain/)

**Characteristics:**
- No external dependencies
- Fast execution (milliseconds)
- Test pure business logic
- 100% coverage target

**Example:**
```python
def test_create_user_message_with_string_content():
    """Test creating a user message with simple string content."""
    # Arrange & Act
    message = UserMessage(content="Hello, world!")

    # Assert
    assert message.role == "user"
    assert message.content == "Hello, world!"
```

**Run unit tests only:**
```bash
uv run pytest -m unit
```

### Integration Tests (packages/backend/tests/application/)

**Characteristics:**
- Mock external dependencies (LLM APIs, databases)
- Test component interactions
- Slower than unit tests (seconds)
- 80% coverage target

**Example:**
```python
@pytest.mark.asyncio
async def test_execute_single_non_confirmation_tool(
    mock_tool_manager, sample_session_id, sample_tool_call
):
    """Test executing a tool with mocked dependencies."""
    executor = ToolExecutor(mock_tool_manager, sample_session_id)
    result = await executor.execute_all([sample_tool_call], "msg_id")
    assert result.user_rejected is False
```

**Run integration tests only:**
```bash
uv run pytest -m integration
```

### E2E Tests (packages/backend/tests/e2e/)

**Characteristics:**
- Full system integration
- Real dependencies (or docker-compose services)
- Slow execution (minutes)
- 40% coverage target

**Run E2E tests only:**
```bash
uv run pytest -m e2e
```

## Testing Best Practices

### 1. Test Structure (AAA Pattern)

```python
def test_example():
    # Arrange - Set up test data and dependencies
    message = UserMessage(content="Test")

    # Act - Execute the behavior being tested
    result = message.to_dict()

    # Assert - Verify the outcome
    assert result["role"] == "user"
```

### 2. Descriptive Test Names

```python
# ✅ Good - Describes behavior and expected result
def test_create_user_message_with_string_content():
    pass

def test_user_message_role_cannot_be_changed():
    pass

# ❌ Bad - Vague, doesn't describe what's being tested
def test_user_message():
    pass

def test_message_creation():
    pass
```

### 3. One Assertion Per Concept

```python
# ✅ Good - Test one concept with related assertions
def test_user_message_has_correct_defaults():
    message = UserMessage(content="Test")
    assert message.role == "user"
    assert message.id is None
    assert message.timestamp is None

# ❌ Bad - Multiple unrelated concepts
def test_user_message():
    message = UserMessage(content="Test")
    assert message.role == "user"
    assert len(message.content) > 0
    assert message.to_dict()["role"] == "user"
```

### 4. Use Fixtures for Reusable Data

```python
# conftest.py
@pytest.fixture
def sample_user_message_dict():
    return {
        "role": "user",
        "content": "Hello, how are you?",
        "id": "msg_001"
    }

# test_messages.py
def test_create_message_from_dict(sample_user_message_dict):
    message = UserMessage(**sample_user_message_dict)
    assert message.content == "Hello, how are you?"
```

### 5. Mock External Dependencies

```python
from unittest.mock import Mock, AsyncMock

@pytest.mark.asyncio
async def test_tool_execution_with_mock():
    # Mock the external dependency
    mock_manager = Mock()
    mock_manager.handle_function_call = AsyncMock(
        return_value={"status": "success"}
    )

    # Use the mock in your test
    executor = ToolExecutor(mock_manager, "session_123")
    result = await executor.execute_all([tool_call], "msg_id")

    # Verify the mock was called correctly
    mock_manager.handle_function_call.assert_called_once()
```

### 6. Test Edge Cases

```python
def test_message_with_empty_string_content():
    """Test that empty content is valid."""
    message = UserMessage(content="")
    assert message.content == ""

def test_message_with_very_long_content():
    """Test message with extreme content length."""
    long_content = "A" * 100000
    message = UserMessage(content=long_content)
    assert len(message.content) == 100000
```

### 7. Use Parametrized Tests for Similar Scenarios

```python
@pytest.mark.parametrize("content,expected_length", [
    ("Short", 5),
    ("Medium length message", 21),
    ("", 0),
    ("A" * 1000, 1000),
])
def test_message_content_length(content, expected_length):
    message = UserMessage(content=content)
    assert len(message.content) == expected_length
```

## Running Tests

### Run All Tests
```bash
uv run pytest
```

### Run with Verbose Output
```bash
uv run pytest -v
```

### Run with Coverage
```bash
# Terminal report
uv run pytest --cov=packages/backend --cov-report=term-missing

# HTML report (opens in browser)
uv run pytest --cov=packages/backend --cov-report=html
open htmlcov/index.html
```

### Run Tests in Parallel (faster)
```bash
uv run pytest -n auto  # Uses all CPU cores
```

### Run Specific Markers
```bash
# Run only unit tests
uv run pytest -m unit

# Run only integration tests
uv run pytest -m integration

# Run only slow tests
uv run pytest -m slow

# Run only PFC-related tests
uv run pytest -m pfc
```

### Stop on First Failure
```bash
uv run pytest -x
```

### Show Local Variables on Failure
```bash
uv run pytest --showlocals
```

### Re-run Failed Tests
```bash
# First run
uv run pytest

# Re-run only failures
uv run pytest --lf  # last failed
```

## Test Coverage Goals

| Layer | Target Coverage | Current |
|-------|----------------|---------|
| Domain Models | 90% | TBD |
| Application Services | 80% | TBD |
| Infrastructure | 70% | TBD |
| **Overall** | **80%** | **TBD** |

## Continuous Integration

Tests run automatically on:
- Every commit (unit tests)
- Every pull request (unit + integration tests)
- Before merge to main (all tests including E2E)

### GitHub Actions Workflow

See `.github/workflows/test.yml` for the complete CI configuration.

## Writing New Tests

### 1. Choose the Right Location

```
Domain logic (pure functions, models)
→ packages/backend/tests/domain/

Application logic (services, orchestration)
→ packages/backend/tests/application/

Infrastructure (LLM clients, databases, external APIs)
→ packages/backend/tests/infrastructure/
```

### 2. Follow the Naming Convention

```
File: test_<module_name>.py
Class: Test<ClassName>
Function: test_<behavior>_<expected_result>
```

### 3. Use Appropriate Markers

```python
import pytest

@pytest.mark.unit
def test_pure_function():
    pass

@pytest.mark.integration
@pytest.mark.asyncio
async def test_with_external_dependency():
    pass

@pytest.mark.e2e
@pytest.mark.slow
def test_full_workflow():
    pass
```

### 4. Add Fixtures to conftest.py

If a fixture is used across multiple test files, add it to `conftest.py`.

### 5. Document Complex Tests

```python
def test_complex_scenario():
    """
    Test the scenario where:
    1. User rejects first tool
    2. Remaining tools are cascade blocked
    3. Rejection message is preserved

    This ensures proper cascade blocking behavior.
    """
    # Test implementation
```

## Debugging Tests

### Run with Debugger
```bash
uv run pytest --pdb  # Drop into debugger on failure
```

### Print Debug Output
```python
def test_with_debug():
    message = UserMessage(content="Test")
    print(f"Message: {message}")  # Will only show on failure
    assert message.role == "user"
```

### Show Print Statements
```bash
uv run pytest -s  # Show print statements even on success
```

## Common Issues

### Issue: Tests pass individually but fail when run together

**Cause:** Shared state between tests

**Solution:** Use fixtures and ensure test isolation

```python
@pytest.fixture(autouse=True)
def reset_global_state():
    """Reset global state before each test."""
    # Reset code here
    yield
    # Cleanup code here
```

### Issue: Async tests not running

**Cause:** Missing `@pytest.mark.asyncio` decorator

**Solution:**
```python
@pytest.mark.asyncio
async def test_async_function():
    result = await some_async_function()
    assert result is not None
```

### Issue: Import errors in tests

**Cause:** Python path not configured correctly

**Solution:** Run tests with `uv run pytest` (uv manages the path)

## Resources

- [Pytest Documentation](https://docs.pytest.org/)
- [Pytest Best Practices](https://docs.pytest.org/en/stable/goodpractices.html)
- [Testing Best Practices (Martin Fowler)](https://martinfowler.com/testing/)
- [Test-Driven Development](https://en.wikipedia.org/wiki/Test-driven_development)
