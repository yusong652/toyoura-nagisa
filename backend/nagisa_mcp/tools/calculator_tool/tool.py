"""calculator tool – safe arithmetic evaluation with enterprise-grade expression parsing.

This tool provides atomic arithmetic computation functionality, focusing exclusively on 
evaluating mathematical expressions with comprehensive safety controls. It supports 
fundamental arithmetic operations with secure AST-based parsing to prevent code injection.

Modeled after coding tool patterns for consistency and interoperability.
"""

import ast
import operator as _op
from typing import Any, Optional, Callable

from fastmcp import FastMCP
from pydantic import Field

from backend.nagisa_mcp.utils.tool_result import ToolResult

__all__ = ["calculate", "register_calculator_tools"]

# -----------------------------------------------------------------------------
# Safe expression evaluation constants
# -----------------------------------------------------------------------------

# Supported operators mapping
_ALLOWED_OPERATORS: dict[type[ast.AST], Callable] = {
    ast.Add: _op.add,
    ast.Sub: _op.sub,
    ast.Mult: _op.mul,
    ast.Div: _op.truediv,
    ast.Pow: _op.pow,
    ast.Mod: _op.mod,
    ast.USub: _op.neg,
    ast.UAdd: _op.pos,
}

# Expression limits for safety
MAX_EXPRESSION_LENGTH = 1000  # Maximum expression length
MAX_RECURSION_DEPTH = 50     # Maximum AST recursion depth
MAX_RESULT_MAGNITUDE = 1e15  # Maximum result magnitude

# -----------------------------------------------------------------------------
# Core evaluation engine
# -----------------------------------------------------------------------------

def _eval_node(node: ast.AST, depth: int = 0) -> float:
    """Recursively evaluate an AST node containing a safe arithmetic expression.
    
    Args:
        node: AST node to evaluate
        depth: Current recursion depth for safety
        
    Returns:
        Evaluated numeric result
        
    Raises:
        ValueError: For unsupported operations or exceeded limits
    """
    if depth > MAX_RECURSION_DEPTH:
        raise ValueError("Expression too deeply nested")
    
    if isinstance(node, ast.Num):  # Python < 3.8 compatibility
        return float(node.n)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return float(node.value)
    if isinstance(node, ast.BinOp):
        if type(node.op) not in _ALLOWED_OPERATORS:
            raise ValueError(f"Unsupported binary operator: {type(node.op).__name__}")
        left = _eval_node(node.left, depth + 1)
        right = _eval_node(node.right, depth + 1)
        
        # Check for division by zero
        if isinstance(node.op, ast.Div) and right == 0:
            raise ValueError("Division by zero")
        
        result = _ALLOWED_OPERATORS[type(node.op)](left, right)
        
        # Check result magnitude
        if abs(result) > MAX_RESULT_MAGNITUDE:
            raise ValueError("Result magnitude exceeds safe limits")
        
        return result
    if isinstance(node, ast.UnaryOp):
        if type(node.op) not in _ALLOWED_OPERATORS:
            raise ValueError(f"Unsupported unary operator: {type(node.op).__name__}")
        operand = _eval_node(node.operand, depth + 1)
        return _ALLOWED_OPERATORS[type(node.op)](operand)
    
    raise ValueError(f"Invalid expression component: {type(node).__name__}")


def _safe_eval(expr: str) -> float:
    """Safely evaluate arithmetic expression using AST parsing.
    
    Args:
        expr: Mathematical expression string
        
    Returns:
        Evaluated numeric result
        
    Raises:
        ValueError: For invalid syntax or unsupported operations
    """
    # Basic input validation
    if not expr or not expr.strip():
        raise ValueError("Empty expression")
    if len(expr) > MAX_EXPRESSION_LENGTH:
        raise ValueError(f"Expression too long (max {MAX_EXPRESSION_LENGTH} characters)")
    
    # Parse and validate AST
    try:
        parsed = ast.parse(expr.strip(), mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Syntax error: {e.msg}") from e
    
    if not isinstance(parsed, ast.Expression):
        raise ValueError("Only expressions are allowed")
    
    return _eval_node(parsed.body)


# -----------------------------------------------------------------------------
# Tool implementation
# -----------------------------------------------------------------------------

def calculate(expression: str = Field(..., description="Mathematical expression to evaluate (supports +, -, *, /, %, **, parentheses, unary +/-)")) -> dict[str, Any]:
    """Evaluate mathematical expressions with safe arithmetic computation and intelligent result formatting.
    
    ## Return Value
    **For LLM:** Returns structured data with consistent format across all calculation tools.
    
    **Structure:**
    ```json
    {
      "operation": {
        "type": "calculate",
        "expression": "2 + 3 * 4",
        "result": "14",
        "result_type": "integer"
      },
      "result": {
        "value": "14",
        "original_expression": "2 + 3 * 4",
        "calculation_successful": true,
        "formatted_display": "2 + 3 * 4 = 14"
      },
      "summary": {
        "operation_type": "calculate",
        "success": true,
        "result_type": "integer"
      }
    }
    ```
    
    **Optional Sections:**
    - `error`: Present when calculation fails with error details
    - `warnings`: Present when expression has potential issues
    
    ## Core Functionality
    Evaluates mathematical expressions with enterprise-grade safety controls and intelligent result formatting.

    ## Strategic Usage
    Use this tool to **perform arithmetic calculations** with proper error handling and result formatting.
    Perfect for mathematical computations in data processing, financial calculations, or general arithmetic needs.
    
    ## Supported Operations
    - **Basic arithmetic**: `+`, `-`, `*`, `/`, `%` (modulo)
    - **Exponentiation**: `**` (power)
    - **Parentheses**: `()` for grouping operations
    - **Unary operators**: `+`, `-` (positive/negative)
    
    ## Safety Features
    - **Expression validation**: Prevents code injection attacks
    - **Division by zero protection**: Graceful error handling
    - **Result formatting**: Automatic integer/float formatting
    - **Input sanitization**: Safe evaluation with AST parsing
    """
    
    def _error(message: str, error_details: Optional[str] = None, expr: str = "") -> dict[str, Any]:
        """Generate standardized error response."""
        # Determine error type based on message
        error_type = "unknown_error"
        if "Division by zero" in message:
            error_type = "division_by_zero"
        elif "Empty expression" in message:
            error_type = "empty_expression"
        elif "Invalid expression" in message:
            error_type = "invalid_expression"
        elif "Numerical overflow" in message:
            error_type = "numerical_overflow"
        
        return ToolResult(
            status="error",
            message=message,
            llm_content=f"Calculator error: {message}",
            error=error_details or message,
            data={
                "operation": {
                    "type": "calculate",
                    "expression": expr,
                    "error": error_details or message
                },
                "result": {
                    "calculation_successful": False,
                    "error_type": error_type,
                    "error_message": error_details or message
                },
                "summary": {
                    "operation_type": "calculate",
                    "success": False
                }
            }
        ).model_dump()
    
    def _success(result: str, original_expr: str) -> dict[str, Any]:
        """Generate standardized success response."""
        result_type = "integer" if "." not in result else "float"
        return ToolResult(
            status="success", 
            message=f"Calculated: {original_expr} = {result}",
            llm_content=f"```\n{original_expr} = {result}\n```",
            data={
                "operation": {
                    "type": "calculate",
                    "expression": original_expr,
                    "result": result,
                    "result_type": result_type
                },
                "result": {
                    "value": result,
                    "original_expression": original_expr,
                    "calculation_successful": True,
                    "formatted_display": f"{original_expr} = {result}"
                },
                "summary": {
                    "operation_type": "calculate",
                    "success": True,
                    "result_type": result_type
                }
            }
        ).model_dump()
    
    # Input validation
    if not expression:
        return _error("Expression cannot be empty", expr=expression)
    
    try:
        # Evaluate expression
        result = _safe_eval(expression)
        
        # Format result (remove trailing .0 for integers)
        if isinstance(result, float) and result.is_integer():
            formatted_result = str(int(result))
        else:
            formatted_result = str(result)
        
        return _success(formatted_result, expression)
        
    except ValueError as e:
        return _error(f"Invalid expression: {e}", str(e), expression)
    except ZeroDivisionError:
        return _error("Division by zero", "Cannot divide by zero", expression)
    except OverflowError:
        return _error("Numerical overflow", "Result too large to compute", expression)
    except Exception as e:
        return _error(f"Calculation failed: {type(e).__name__}", str(e), expression)


# -----------------------------------------------------------------------------
# Registration helper
# -----------------------------------------------------------------------------

def register_calculator_tools(mcp: FastMCP) -> None:
    """Register calculator tools with proper tags synchronization."""
    
    common = dict(
        tags={"calculator", "math", "arithmetic", "computation", "evaluation"}, 
        annotations={"category": "calculator", "tags": ["calculator", "math", "arithmetic", "computation", "evaluation"]}
    )
    
    mcp.tool(**common)(calculate) 