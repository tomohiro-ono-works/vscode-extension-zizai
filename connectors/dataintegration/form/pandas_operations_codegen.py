"""Render the ordered data operations as standalone pandas statements."""
from itertools import groupby
import keyword
from pathlib import Path
from unicodedata import normalize

from .arithmetic_formula import ArithmeticFormula


ARITHMETIC = {'add': '+', 'subtract': '-', 'multiply': '*', 'divide': '/'}
COMPARISONS = {
    'number_equal': 'eq', 'text_equal': 'eq', 'bool_equal': 'eq', 'date_equal': 'eq',
    'greater': 'gt', 'greater_equal': 'ge', 'less': 'lt', 'less_equal': 'le',
    'date_before': 'lt', 'date_after': 'gt',
}
TEXT_METHODS = {'trim': 'strip', 'upper': 'upper', 'lower': 'lower'}


class PandasOperationsCode:
    def __init__(self, incoming, output, *, lookup_labels, dictionary_refs=(), connector_module='dataintegration_connector'):
        self.output = output
        self.imports = {}
        self.names = {normalize('NFKC', name) for name in (incoming, output, *dictionary_refs)}
        self.connector_module = connector_module
        self.lines = [f'{output} = {incoming}.copy()']
        self.labels = None
        if lookup_labels:
            self.labels = self._name('_column_labels')
            key = self._name('_column_label')
            self.lines.append(f'{self.labels} = {{f"{{{key}!s}}": {key} for {key} in {output}.columns}}')

    def _name(self, preferred):
        name = preferred
        while name in self.names:
            name += '_'
        self.names.add(name)
        return name

    def use(self, module, preferred):
        if module not in self.imports:
            self.imports[module] = self._name(preferred)
        return self.imports[module]

    def label(self, key):
        return f'{self.labels}.get({key!r}, {key!r})' if self.labels else repr(key)

    def column(self, key):
        return f'{self.output}[{self.label(key)}]'

    def value(self, step):
        key, op = step.get('column'), step['op']
        column = self.column(key) if key is not None else None
        target = f'{self.output}[{step["output"]!r}]' if 'output' in step else column
        text = f"{column}.astype('string').str"
        if op == 'formula':
            expression = ArithmeticFormula(step.get('expression')).to_python(
                self.column, lambda code, series: self.formula_divisor(step.get('output', key), code, series))
        elif op in ARITHMETIC:
            other = self.column(step['other_column']) if 'other_column' in step else repr(step['number'])
            if op == 'divide' and 'other_column' in step:
                self.lines.extend([f'if {other}.eq(0).any():',
                                   f'    raise ValueError({f"「{key}」列: 0で割ることはできません。"!r})'])
            elif op == 'divide' and step['number'] == 0:
                raise ValueError('0で割ることはできません。')
            expression = f'{column} {ARITHMETIC[op]} {other}'
        elif op == 'round':
            expression = f'{column}.round({step["digits"]!r})'
        elif op == 'abs':
            expression = f'{column}.abs()'
        elif op == 'fill_null':
            value = step['value']
            if step.get('value_type') == 'datetime':
                value = self.timestamp(value)
            else:
                value = repr(value)
            expression = f'{column}.fillna({value})'
        elif op == 'to_null':
            value = self.timestamp(step['value']) if step.get('value_type') == 'datetime' else repr(step['value'])
            missing = f"{self.use('pandas', 'pd')}.NA"
            expression = f'{column}.mask({column}.eq({value}).fillna(False), {missing})'
        elif op in TEXT_METHODS:
            expression = f'{text}.{TEXT_METHODS[op]}()'
        elif op == 'replace_dictionary':
            reference = step['dictionary_reference']
            if step['dictionary_source'] == 'dataframe':
                dictionary = reference
            elif step['dictionary_source'] == 'csv':
                if not Path(reference).is_absolute() or Path(reference).suffix.lower() != '.csv':
                    raise ValueError('辞書CSVは絶対パスで指定してください。')
                dictionary = repr(reference)
            else:
                raise ValueError('辞書の参照形式を確認してください。')
            module = self.use(self.connector_module, '_zizai_dataintegration')
            expression = (
                f'{module}.replace_dictionary({column}, {dictionary}, '
                f'source_column={step["source_column"]!r}, target_column={step["target_column"]!r}, '
                f'match_mode={step.get("match_mode", "exact")!r}, '
                f'unmatched={step.get("unmatched", "keep")!r}, cascade={step.get("cascade", False)!r})'
            )
        elif op == 'replace_exact':
            expression = (
                f"{column}.astype('string').replace({step['search']!r}, {step['replacement']!r}, regex=False)"
            )
        elif op == 'replace_part':
            expression = f'{text}.replace({step["search"]!r}, {step["replacement"]!r}, regex=False)'
        elif op == 'concat':
            other = f"{self.column(step['other_column'])}.astype('string')"
            expression = f'{text}.cat({other}, sep={step["separator"]!r})'
        elif op == 'split':
            position = step['position'] - 1
            expression = f'{text}.split({step["separator"]!r}, regex=False).str.get({position}).astype(\'string\')'
        elif op == 'extract_regex':
            regex = self.use('re', 're')
            pattern = self._name('_pattern')
            group = step.get('group', 0)
            self.lines.append(f'{pattern} = {regex}.compile({step["pattern"]!r})')
            value = self._name('value')
            match = self._name('match')
            expression = (f"{column}.astype('string').map(\n"
                          f'    lambda {value}: {match}.group({group!r}) if '
                          f'({match} := {pattern}.search({value})) else None,\n'
                          "    na_action='ignore',\n).astype('string')")
        else:
            raise ValueError('未対応の値加工です。')
        self.lines.append(f'{target} = {expression}')

    def formula_divisor(self, key, code, series):
        name = self._name('_divisor')
        zero = f'{name}.eq(0).any()' if series else f'{name} == 0'
        self.lines.extend([f'{name} = {code}', f'if {zero}:',
                           f'    raise ValueError({f"「{key}」列: 0で割ることはできません。"!r})'])
        return name

    def timestamp(self, value):
        return f"{self.use('pandas', 'pd')}.Timestamp({value!r})"

    def comparison(self, rule):
        column = self.column(rule['column'])
        op, value = rule['comparison'], rule.get('value')
        if op == 'is_null':
            return f'{column}.isna()'
        if op == 'not_null':
            return f'{column}.notna()'
        if op == 'contains':
            return f"{column}.astype('string').str.contains({value!r}, regex=False, na=False)"
        if op == 'text_equal':
            column = f"{column}.astype('string')"
        if op in ('between', 'date_between'):
            upper = rule['upper']
            lower_arg, upper_arg = (self.timestamp(value), self.timestamp(upper)) if op == 'date_between' else (
                repr(value), repr(upper))
            return f'{column}.between({lower_arg}, {upper_arg}).fillna(False)'
        if op not in COMPARISONS:
            raise ValueError('比較方法を選択してください。')
        argument = self.timestamp(value) if op.startswith('date_') else repr(value)
        return f'{column}.{COMPARISONS[op]}({argument}).fillna(False)'

    def rows(self, steps):
        conditions = []
        mode = None
        for step in steps:
            op = step['op']
            if op == 'condition':
                rule = step['condition']
                if conditions and mode == step['mode'] and rule.get('logic') in ('and', 'or'):
                    conditions.append(rule)
                else:
                    self.filter(mode, conditions)
                    mode, conditions = step['mode'], [rule]
                continue
            self.filter(mode, conditions)
            conditions = []
            if op == 'filter':
                self.filter(step['mode'], step['conditions'])
            elif op in ('drop_nulls', 'drop_duplicates'):
                method = 'dropna' if op == 'drop_nulls' else op
                labels = [self.label(key) for key in step.get('columns', [])]
                arguments = f"subset=[{', '.join(labels)}]" if labels else ''
                self.lines.append(f'{self.output} = {self.output}.{method}({arguments})')
            elif op in ('head', 'tail'):
                self.lines.append(f'{self.output} = {self.output}.{op}({step["count"]!r})')
            else:
                raise ValueError('未対応の行操作です。')
        self.filter(mode, conditions)

    def filter(self, mode, rules):
        if not rules:
            return
        if mode not in ('keep', 'exclude'):
            raise ValueError('抽出または除外を選択してください。')
        groups = [[self.comparison(rules[0])]]
        for rule in rules[1:]:
            logic = rule.get('logic')
            if logic == 'or':
                groups.append([])
            elif logic != 'and':
                raise ValueError('条件の結合にはANDまたはORを指定してください。')
            groups[-1].append(self.comparison(rule))
        mask = ' | '.join(' & '.join(group) for group in groups)
        if mode == 'exclude':
            mask = f'~({mask})'
        if len(rules) > 1:
            name = self._name('condition')
            self.lines.append(f'{name} = {mask}')
            mask = name
        self.lines.append(f'{self.output} = {self.output}.loc[{mask}]')

    def render(self):
        imports = [f'import {module}' if module == name else f'import {module} as {name}'
                   for module, name in self.imports.items()]
        lines = [*imports, '', *self.lines] if imports else self.lines
        return '\n'.join([*lines, self.output])


def generate_pandas_operations(incoming, output, operations, *, connector_module='dataintegration_connector'):
    try:
        refs = set()
        for item in operations:
            step = item['operation']
            if step.get('op') == 'replace_dictionary' and step.get('dictionary_source') == 'dataframe':
                reference = step['dictionary_reference']
                if not isinstance(reference, str) or not reference.isidentifier() or keyword.iskeyword(normalize('NFKC', reference)):
                    raise ValueError('辞書DataFrameの変数名を指定してください。')
                if normalize('NFKC', reference) == normalize('NFKC', output):
                    raise ValueError('辞書と出力には別の変数名を指定してください。')
                refs.add(reference)
        code = PandasOperationsCode(incoming, output, lookup_labels=operations[0].get('lookup_labels') is True,
                                    dictionary_refs=refs, connector_module=connector_module)
        for category, group in groupby(operations, lambda step: step['category']):
            steps = [item['operation'] for item in group]
            if category == 'condition':
                code.rows(steps)
            elif category == 'value':
                for step in steps:
                    code.value(step)
            else:
                raise ValueError('処理分類を確認してください。')
    except (KeyError, TypeError, IndexError) as error:
        raise ValueError('処理の設定を確認してください。') from error
    return code.render()
