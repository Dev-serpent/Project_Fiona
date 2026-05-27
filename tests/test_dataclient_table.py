from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from DataClient.table import add_column, add_row, cell_name, convert_table, evaluate_formula, load_table, save_table, table_columns


class DataClientTableTests(unittest.TestCase):
    def test_table_columns_preserve_first_seen_order(self) -> None:
        rows = [{"name": "Ada", "role": "math"}, {"role": "code", "year": 1843}]

        self.assertEqual(table_columns(rows), ["name", "role", "year"])

    def test_add_row_and_column_mutate_table(self) -> None:
        rows = [{"name": "Ada"}]

        add_column(rows, "role", "research")
        add_row(rows)

        self.assertEqual(rows, [{"name": "Ada", "role": "research"}, {"name": "", "role": ""}])

    def test_json_csv_sqlite_round_trip(self) -> None:
        rows = [{"name": "Ada", "role": "math"}, {"name": "Grace", "role": "systems"}]

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            json_path = root / "data.json"
            csv_path = root / "data.csv"
            db_path = root / "data.db"

            save_table(rows, json_path)
            convert_table(json_path, csv_path)
            convert_table(csv_path, db_path, table_name="people")
            loaded = load_table(db_path)

        self.assertEqual(loaded, rows)

    def test_rejects_unsupported_format(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                load_table(Path(tmp) / "data.txt")

    def test_cell_names_and_formula_references(self) -> None:
        rows = [{"name": "Ada", "score": "10"}, {"name": "Grace", "score": "20"}]

        self.assertEqual(cell_name(0, 0), "A1")
        self.assertEqual(cell_name(1, 27), "AB2")
        self.assertEqual(evaluate_formula("=B1 + B2", rows), 30)
        self.assertEqual(evaluate_formula("=SUM(B1:B2)", rows), 30)
        self.assertEqual(evaluate_formula("=AVG(B1:B2)", rows), 15)
        self.assertEqual(evaluate_formula("=UPPER(A1)", rows), "ADA")

    def test_formula_rejects_unsafe_expressions(self) -> None:
        rows = [{"value": "1"}]

        with self.assertRaises(ValueError):
            evaluate_formula("=__import__('os').system('date')", rows)


if __name__ == "__main__":
    unittest.main()
