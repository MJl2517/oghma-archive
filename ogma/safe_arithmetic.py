from __future__ import annotations

import ast
import math
import operator


MAX_EXPRESSION_LENGTH = 256
MAX_AST_NODES = 64
MAX_AST_DEPTH = 16
MAX_ABSOLUTE_VALUE = 1_000_000_000

_BINARY_OPERATORS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
}
_UNARY_OPERATORS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}


class UnsafeArithmeticExpression(ValueError):
    """The expression contains unsupported syntax or exceeds resource limits."""


def evaluate_arithmetic(expression: str) -> int | float:
    text = str(expression or "").strip()
    if not text or len(text) > MAX_EXPRESSION_LENGTH:
        raise UnsafeArithmeticExpression("Expression is empty or too long.")
    try:
        tree = ast.parse(text, mode="eval")
    except SyntaxError as exc:
        raise UnsafeArithmeticExpression("Expression is malformed.") from exc

    nodes = list(ast.walk(tree))
    if len(nodes) > MAX_AST_NODES:
        raise UnsafeArithmeticExpression("Expression has too many AST nodes.")
    result = _evaluate_node(tree.body, depth=1)
    return _bounded_number(result)


def _evaluate_node(node: ast.AST, depth: int) -> int | float:
    if depth > MAX_AST_DEPTH:
        raise UnsafeArithmeticExpression("Expression is nested too deeply.")
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, float)):
            raise UnsafeArithmeticExpression("Only finite numeric constants are allowed.")
        return _bounded_number(node.value)
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY_OPERATORS:
        operand = _evaluate_node(node.operand, depth + 1)
        return _bounded_number(_UNARY_OPERATORS[type(node.op)](operand))
    if isinstance(node, ast.BinOp) and type(node.op) in _BINARY_OPERATORS:
        left = _evaluate_node(node.left, depth + 1)
        right = _evaluate_node(node.right, depth + 1)
        try:
            result = _BINARY_OPERATORS[type(node.op)](left, right)
        except (ArithmeticError, OverflowError) as exc:
            raise UnsafeArithmeticExpression("Arithmetic operation is invalid.") from exc
        return _bounded_number(result)
    raise UnsafeArithmeticExpression("Expression contains a forbidden operation.")


def _bounded_number(value: int | float) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UnsafeArithmeticExpression("Result is not numeric.")
    if not math.isfinite(value) or abs(value) > MAX_ABSOLUTE_VALUE:
        raise UnsafeArithmeticExpression("Operand or result exceeds the allowed range.")
    return value
