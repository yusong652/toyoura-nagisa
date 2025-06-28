"""
Calculator Tool Module
Provides basic arithmetic evaluation capability through FastMCP tool interface.
Only supports +, -, *, /, **, %, parentheses and unary operators. Raises error on invalid input.
"""

from __future__ import annotations

import ast
import operator as _op
from fastmcp import FastMCP
from pydantic import Field

# ------------------------------------------------------------------
# Safe expression evaluation helpers (recursive AST walk)
# ------------------------------------------------------------------

_ALLOWED_OPERATORS: dict[type[ast.AST], _op.operator] = {
    ast.Add: _op.add,
    ast.Sub: _op.sub,
    ast.Mult: _op.mul,
    ast.Div: _op.truediv,
    ast.Pow: _op.pow,
    ast.Mod: _op.mod,
    ast.USub: _op.neg,
    ast.UAdd: _op.pos,
}


def _eval_node(node: ast.AST) -> float:
    """Recursively evaluate an AST node containing a safe arithmetic expression."""
    if isinstance(node, ast.Num):  # type: ignore[attr-defined]
        return node.n  # type: ignore[attr-defined]
    if isinstance(node, ast.BinOp):
        if type(node.op) not in _ALLOWED_OPERATORS:  # noqa: E721
            raise ValueError("Unsupported binary operator")
        left = _eval_node(node.left)
        right = _eval_node(node.right)
        return _ALLOWED_OPERATORS[type(node.op)](left, right)
    if isinstance(node, ast.UnaryOp):
        if type(node.op) not in _ALLOWED_OPERATORS:  # noqa: E721
            raise ValueError("Unsupported unary operator")
        operand = _eval_node(node.operand)
        return _ALLOWED_OPERATORS[type(node.op)](operand)
    raise ValueError("Invalid expression component")


def _safe_eval(expr: str) -> float:
    """Safely evaluate arithmetic expression using AST parsing."""
    try:
        parsed = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise ValueError(f"Syntax error: {e.msg}") from e
    if not isinstance(parsed, ast.Expression):  # type: ignore[arg-type]
        raise ValueError("Only expressions are allowed")
    return _eval_node(parsed.body)


# ------------------------------------------------------------------
# FastMCP registration
# ------------------------------------------------------------------

def register_calculator_tools(mcp: FastMCP):
    """Register calculator utility tools with FastMCP."""

    common_kwargs = dict(tags={"calculator"}, annotations={"category": "calculator"})

    @mcp.tool(**common_kwargs)
    def calculate(expression: str = Field(..., description="Arithmetic expression to evaluate")) -> str:
        """Evaluate a basic arithmetic expression and return the result as string.

        Supported operators: +, -, *, /, %, **, parentheses, unary +/-.
        Do NOT pass arbitrary Python code. If expression contains unsupported elements an error is returned.
        """
        try:
            result = _safe_eval(expression)
            # Remove trailing .0 for integers
            if isinstance(result, float) and result.is_integer():
                return str(int(result))
            return str(result)
        except Exception as e:
            return f"Error: {e}" 