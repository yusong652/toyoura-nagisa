# Unit Test Creation Prompt

## Context Analysis
First, analyze the codebase structure and existing test patterns to ensure consistency:
- Identify the testing framework (pytest, unittest, jest, etc.)
- Review existing test file locations and naming conventions
- Understand the project's test structure and organization
- Check for test utilities, fixtures, or mocks already in use

## Test Requirements
Create comprehensive unit tests that:
1. **Coverage**: Test all public methods and critical code paths
2. **Edge Cases**: Include boundary conditions, null/empty inputs, and error scenarios
3. **Isolation**: Mock external dependencies appropriately
4. **Clarity**: Use descriptive test names following the pattern: `test_<method>_<scenario>_<expected_result>`
5. **Assertions**: Use specific, meaningful assertions with clear failure messages

## Test Structure Template
```python
# Example for Python/pytest
import pytest
from unittest.mock import Mock, patch
from module_under_test import ClassUnderTest

class TestClassName:
    """Test suite for ClassName functionality."""
    
    @pytest.fixture
    def setup(self):
        """Set up test fixtures."""
        # Initialize test data and mocks
        return ClassUnderTest()
    
    def test_method_valid_input_returns_expected(self, setup):
        """Test that method returns expected result with valid input."""
        # Arrange
        expected = "expected_value"
        
        # Act
        result = setup.method("valid_input")
        
        # Assert
        assert result == expected
        
    def test_method_invalid_input_raises_error(self, setup):
        """Test that method raises appropriate error with invalid input."""
        # Arrange & Act & Assert
        with pytest.raises(ValueError, match="specific error message"):
            setup.method(None)
```

## Implementation Steps
1. **Analyze the target code**: Read and understand the module/class to be tested
2. **Identify test scenarios**: List all methods and their test cases
3. **Set up test environment**: Create necessary fixtures and mocks
4. **Write tests incrementally**: Start with happy paths, then edge cases
5. **Verify test quality**: Ensure tests fail when implementation is broken
6. **Run and refine**: Execute tests and improve based on coverage reports

## Best Practices
- Keep tests independent - each test should be able to run in isolation
- Use meaningful test data that reflects real-world scenarios
- Mock external services (databases, APIs, file systems)
- Test behavior, not implementation details
- Aim for at least 80% code coverage
- Include both positive and negative test cases
- Use parameterized tests for similar scenarios with different inputs

## Example Usage
When asked to create unit tests, I will:
1. First examine the existing codebase to understand testing patterns
2. Identify all testable components in the target module
3. Create a comprehensive test suite following the project's conventions
4. Ensure tests are maintainable and provide good documentation
5. Run the tests to verify they pass and provide adequate coverage

Remember: Good tests serve as living documentation and catch regressions early!