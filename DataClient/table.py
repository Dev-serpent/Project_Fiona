from __future__ import annotations

import json
import operator
import re
import sqlite3
from ast import Add, BinOp, Constant, Div, Expression, Load, Mult, Name, NodeVisitor, Sub, UnaryOp, USub, parse
from pathlib import Path
from typing import Any


Rows = list[dict[str, Any]]


def load_table(path: Path) -> Rows:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return load_csv(path)
    if suffix == ".json":
        return load_json(path)
    if suffix in {".db", ".sqlite", ".sqlite3"}:
        return load_sqlite(path)
    raise ValueError(f"unsupported table input format: {path.suffix}")


def save_table(rows: Rows, path: Path, *, table_name: str = "data") -> Path:
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return save_csv(rows, path)
    if suffix == ".json":
        return save_json(rows, path)
    if suffix in {".db", ".sqlite", ".sqlite3"}:
        return save_sqlite(rows, path, table_name=table_name)
    raise ValueError(f"unsupported table output format: {path.suffix}")


def convert_table(input_path: Path, output_path: Path, *, table_name: str = "data") -> Path:
    return save_table(load_table(input_path), output_path, table_name=table_name)


def load_csv(path: Path) -> Rows:
    pandas = _pandas_module()
    frame = pandas.read_csv(path, keep_default_na=False, dtype=str)
    return _records_from_frame(frame)


def save_csv(rows: Rows, path: Path) -> Path:
    pandas = _pandas_module()
    path.parent.mkdir(parents=True, exist_ok=True)
    pandas.DataFrame(rows).to_csv(path, index=False)
    return path


def load_json(path: Path) -> Rows:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("rows"), list):
        data = data["rows"]
    if not isinstance(data, list):
        raise ValueError("JSON table input must be a list of objects or an object with a 'rows' list")
    rows: Rows = []
    for item in data:
        if not isinstance(item, dict):
            raise ValueError("JSON table rows must be objects")
        rows.append(dict(item))
    return rows


def save_json(rows: Rows, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rows, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return path


def load_sqlite(path: Path, *, table_name: str | None = None) -> Rows:
    with sqlite3.connect(path) as connection:
        table = table_name or _first_table(connection)
        if not table:
            return []
        cursor = connection.execute(f"SELECT * FROM {_quote_identifier(table)}")
        columns = [description[0] for description in cursor.description or []]
        return [dict(zip(columns, row, strict=False)) for row in cursor.fetchall()]


def save_sqlite(rows: Rows, path: Path, *, table_name: str = "data") -> Path:
    columns = table_columns(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        quoted_table = _quote_identifier(table_name)
        connection.execute(f"DROP TABLE IF EXISTS {quoted_table}")
        if not columns:
            connection.execute(f"CREATE TABLE {quoted_table} (_empty TEXT)")
            return path
        column_sql = ", ".join(f"{_quote_identifier(column)} TEXT" for column in columns)
        connection.execute(f"CREATE TABLE {quoted_table} ({column_sql})")
        placeholders = ", ".join("?" for _column in columns)
        quoted_columns = ", ".join(_quote_identifier(column) for column in columns)
        connection.executemany(
            f"INSERT INTO {quoted_table} ({quoted_columns}) VALUES ({placeholders})",
            [[_stringify(row.get(column, "")) for column in columns] for row in rows],
        )
    return path


def table_columns(rows: Rows) -> list[str]:
    columns: list[str] = []
    for row in rows:
        for key in row:
            column = str(key)
            if column not in columns:
                columns.append(column)
    return columns


def add_column(rows: Rows, name: str, default: str = "") -> Rows:
    if not name:
        raise ValueError("column name cannot be empty")
    if not rows:
        return [{name: default}]
    for row in rows:
        row.setdefault(name, default)
    return rows


def add_row(rows: Rows) -> Rows:
    columns = table_columns(rows)
    rows.append({column: "" for column in columns})
    return rows


def evaluate_formula(formula: str, rows: Rows, *, row_index: int = 0) -> Any:
    expression = formula.strip()
    if expression.startswith("="):
        expression = expression[1:].strip()
    if not expression:
        return ""
    columns = table_columns(rows)
    expression = _replace_ranges(expression, rows, columns)
    expression = _replace_cell_refs(expression, rows, columns)
    return _SafeFormulaEvaluator().evaluate(expression)


def cell_name(row_index: int, column_index: int) -> str:
    return f"{_column_letters(column_index)}{row_index + 1}"


def cell_value(rows: Rows, columns: list[str], cell_ref: str) -> Any:
    match = re.fullmatch(r"([A-Za-z]+)(\d+)", cell_ref.strip())
    if not match:
        raise ValueError(f"invalid cell reference: {cell_ref}")
    column_index = _column_index(match.group(1))
    row_index = int(match.group(2)) - 1
    if row_index < 0 or row_index >= len(rows) or column_index >= len(columns):
        return ""
    return rows[row_index].get(columns[column_index], "")


def _records_from_frame(frame: Any) -> Rows:
    return [dict(row) for row in frame.to_dict(orient="records")]


def _replace_ranges(expression: str, rows: Rows, columns: list[str]) -> str:
    pattern = re.compile(r"\b([A-Za-z]+\d+):([A-Za-z]+\d+)\b")
    return pattern.sub(lambda match: repr(_range_values(rows, columns, match.group(1), match.group(2))), expression)


def _replace_cell_refs(expression: str, rows: Rows, columns: list[str]) -> str:
    pattern = re.compile(r"\b([A-Za-z]+\d+)\b")
    return pattern.sub(lambda match: repr(cell_value(rows, columns, match.group(1))), expression)


def _range_values(rows: Rows, columns: list[str], start: str, end: str) -> list[Any]:
    start_col, start_row = _split_cell(start)
    end_col, end_row = _split_cell(end)
    values: list[Any] = []
    for row_index in range(min(start_row, end_row), max(start_row, end_row) + 1):
        for column_index in range(min(start_col, end_col), max(start_col, end_col) + 1):
            if 0 <= row_index < len(rows) and 0 <= column_index < len(columns):
                values.append(rows[row_index].get(columns[column_index], ""))
    return values


def _split_cell(reference: str) -> tuple[int, int]:
    match = re.fullmatch(r"([A-Za-z]+)(\d+)", reference.strip())
    if not match:
        raise ValueError(f"invalid cell reference: {reference}")
    return _column_index(match.group(1)), int(match.group(2)) - 1


def _column_letters(index: int) -> str:
    if index < 0:
        raise ValueError("column index cannot be negative")
    letters = ""
    current = index
    while True:
        current, remainder = divmod(current, 26)
        letters = chr(65 + remainder) + letters
        if current == 0:
            return letters
        current -= 1


def _column_index(letters: str) -> int:
    value = 0
    for letter in letters.upper():
        if not "A" <= letter <= "Z":
            raise ValueError(f"invalid column letter: {letter}")
        value = value * 26 + (ord(letter) - 64)
    return value - 1


class _SafeFormulaEvaluator(NodeVisitor):
    _binary_ops = {
        Add: operator.add,
        Sub: operator.sub,
        Mult: operator.mul,
        Div: operator.truediv,
    }

    _functions = {
        "SUM": lambda values: sum(_numbers(values)),
        "AVG": lambda values: sum(_numbers(values)) / len(_numbers(values)) if _numbers(values) else 0,
        "MIN": lambda values: min(_numbers(values), default=0),
        "MAX": lambda values: max(_numbers(values), default=0),
        "COUNT": lambda values: len([value for value in _flatten(values) if str(value) != ""]),
        "LEN": lambda value: len(str(value)),
        "LOWER": lambda value: str(value).lower(),
        "UPPER": lambda value: str(value).upper(),
    }

    def evaluate(self, expression: str) -> Any:
        tree = parse(expression, mode="eval")
        return self.visit(tree)

    def visit_Expression(self, node: Expression) -> Any:
        return self.visit(node.body)

    def visit_Constant(self, node: Constant) -> Any:
        return node.value

    def visit_List(self, node: Any) -> list[Any]:
        return [self.visit(element) for element in node.elts]

    def visit_Tuple(self, node: Any) -> list[Any]:
        return [self.visit(element) for element in node.elts]

    def visit_UnaryOp(self, node: UnaryOp) -> Any:
        if isinstance(node.op, USub):
            return -float(self.visit(node.operand))
        raise ValueError("unsupported formula operator")

    def visit_BinOp(self, node: BinOp) -> Any:
        operator_type = type(node.op)
        if operator_type not in self._binary_ops:
            raise ValueError("unsupported formula operator")
        return self._binary_ops[operator_type](_coerce_number(self.visit(node.left)), _coerce_number(self.visit(node.right)))

    def visit_Name(self, node: Name) -> Any:
        if isinstance(node.ctx, Load) and node.id.upper() in {"TRUE", "FALSE"}:
            return node.id.upper() == "TRUE"
        raise ValueError(f"unknown formula name: {node.id}")

    def visit_Call(self, node: Any) -> Any:
        name = getattr(node.func, "id", "").upper()
        if name not in self._functions:
            raise ValueError(f"unsupported formula function: {name}")
        args = [self.visit(arg) for arg in node.args]
        if name in {"SUM", "AVG", "MIN", "MAX", "COUNT"}:
            return self._functions[name](args)
        return self._functions[name](*args)

    def generic_visit(self, node: Any) -> Any:
        raise ValueError(f"unsupported formula expression: {type(node).__name__}")


def _flatten(values: Any) -> list[Any]:
    if isinstance(values, list):
        flattened: list[Any] = []
        for value in values:
            flattened.extend(_flatten(value))
        return flattened
    return [values]


def _numbers(values: Any) -> list[float]:
    numbers: list[float] = []
    for value in _flatten(values):
        try:
            numbers.append(float(value))
        except (TypeError, ValueError):
            continue
    return numbers


def _coerce_number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"formula value is not numeric: {value!r}") from exc


def _first_table(connection: sqlite3.Connection) -> str:
    cursor = connection.execute("SELECT name FROM sqlite_master WHERE type='table' ORDER BY name LIMIT 1")
    row = cursor.fetchone()
    return str(row[0]) if row else ""


def _quote_identifier(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def _stringify(value: Any) -> str:
    if value is None:
        return ""
    return str(value)


def _pandas_module() -> Any:
    try:
        import pandas
    except ImportError as exc:
        raise RuntimeError("DataClient table tools require the 'pandas' package.") from exc
    return pandas
