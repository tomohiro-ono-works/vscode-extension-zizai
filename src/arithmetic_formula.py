"""Parse DataFrame column formulas for preview and ordinary pandas code."""
import ast
from io import StringIO
from keyword import iskeyword
from math import isfinite
import operator
import re
import tokenize


_QUOTED_COLUMN = re.compile(r'`((?:[^`\r\n]|``)+)`')
_OPERATORS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}
_SYNTAX_ERROR = '計算式には列名・数値・四則演算・括弧を使ってください。'


def format_column(name):
    if name.isidentifier() and not iskeyword(name):
        return name
    return '`' + name.replace('`', '``') + '`'


class ArithmeticFormula:
    def __init__(self, expression):
        if not isinstance(expression, str) or not expression.strip():
            raise ValueError('計算式を入力してください。')
        if len(expression) > 2048:
            raise ValueError('計算式は2048文字以内で入力してください。')
        self.columns = {}
        self.expression = self._parse(expression.strip())

    def _parse(self, expression):
        prefix = '_quoted_column'
        while prefix in expression:
            prefix += '_'
        quoted = {}

        def replace_column(match):
            key = f'{prefix}{len(quoted)}'
            quoted[key] = match[1].replace('``', '`')
            return f' {key} '

        source = ' '.join(_QUOTED_COLUMN.sub(replace_column, expression).splitlines()).strip()
        pieces = []
        try:
            for token in tokenize.generate_tokens(StringIO(source).readline):
                kind, value = token.type, token.string
                if kind == tokenize.NAME and not iskeyword(value):
                    alias = f'_column_{len(self.columns)}'
                    self.columns[alias] = quoted.get(value, value)
                    pieces.append(alias)
                elif kind == tokenize.NUMBER or (kind == tokenize.OP and value in '+-*/()'):
                    pieces.append(value)
                elif kind not in (tokenize.NEWLINE, tokenize.NL, tokenize.ENDMARKER):
                    raise ValueError(_SYNTAX_ERROR)
            root = ast.parse(' '.join(pieces), mode='eval').body
        except (SyntaxError, tokenize.TokenError, RecursionError) as error:
            raise ValueError(_SYNTAX_ERROR) from error
        allowed = (ast.Name, ast.Load, ast.Constant, ast.UnaryOp, ast.BinOp, *_OPERATORS, *_UNARY)
        for node in ast.walk(root):
            if not isinstance(node, allowed):
                raise ValueError(_SYNTAX_ERROR)
            if isinstance(node, ast.Constant) and (
                type(node.value) not in (int, float) or (type(node.value) is float and not isfinite(node.value))
            ):
                raise ValueError('計算式には有限の数値を指定してください。')
        return root

    def _transform(self, node, column, constant, unary, binary):
        if isinstance(node, ast.Name):
            return column(self.columns[node.id]), True
        if isinstance(node, ast.Constant):
            return constant(node), False
        if isinstance(node, ast.UnaryOp):
            value, series = self._transform(node.operand, column, constant, unary, binary)
            return unary(node.op, value), series
        left, left_series = self._transform(node.left, column, constant, unary, binary)
        right, right_series = self._transform(node.right, column, constant, unary, binary)
        return binary(left, node.op, right, right_series), left_series or right_series

    def evaluate(self, column):
        def binary(left, op, right, series):
            if isinstance(op, ast.Div) and (right.eq(0).any() if series else right == 0):
                raise ValueError('0で割ることはできません。')
            return _OPERATORS[type(op)](left, right)

        try:
            value, _ = self._transform(self.expression, column, lambda node: node.value,
                                       lambda op, value: _UNARY[type(op)](value), binary)
            return value
        except RecursionError as error:
            raise ValueError('計算式が複雑すぎます。') from error

    def to_python(self, column, divisor):
        def binary(left, op, right, series):
            if isinstance(op, ast.Div):
                right = ast.Name(id=divisor(ast.unparse(right), series), ctx=ast.Load())
            return ast.BinOp(left=left, op=op, right=right)

        try:
            tree, _ = self._transform(self.expression, lambda name: ast.parse(column(name), mode='eval').body,
                                      lambda node: node, lambda op, value: ast.UnaryOp(op=op, operand=value), binary)
            return ast.unparse(tree)
        except RecursionError as error:
            raise ValueError('計算式が複雑すぎます。') from error
