"""Tests for the scripting console and script execution."""

from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from cad.core.document import Document
from cad.commands.registry import CommandRegistry, CommandError
from cad.commands.builtins import register_builtin_commands
from cad.scripting.console import ScriptingConsole, execute_script


class TestScriptingConsole(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = Document("test")
        self.registry = CommandRegistry()
        register_builtin_commands(self.registry)
        self.console = ScriptingConsole(self.registry, self.doc)

    def test_execute_expression(self) -> None:
        result = self.console.execute("1 + 1")
        # Expression result is not captured; only stdout
        # The console captures stdout, not return values
        self.assertIsNotNone(result)

    def test_execute_simple_statement(self) -> None:
        result = self.console.execute("x = 42")
        self.assertEqual(self.console.get_var("x"), 42)

    def test_execute_print(self) -> None:
        result = self.console.execute("print('hello world')")
        self.assertIn("hello", result)

    def test_create_box_via_script(self) -> None:
        result = self.console.execute('b = create_box(width=10, height=20, depth=30, name="ScriptBox")')
        box = self.doc.find_by_name("ScriptBox")
        self.assertIsNotNone(box)
        self.assertEqual(box.get_property_value("width"), 10)

    def test_recompute_via_script(self) -> None:
        self.console.execute('create_box(width=5, height=5, depth=5, name="B")')
        self.console.execute('recompute()')
        self.assertEqual(self.doc.object_count, 1)

    def test_script_history(self) -> None:
        self.console.execute("a = 1")
        self.console.execute("b = 2")
        self.assertEqual(len(self.console.history), 2)
        self.assertEqual(self.console.history[0], "a = 1")

    def test_output_collection(self) -> None:
        self.console.execute("print('line1')")
        self.console.execute("print('line2')")
        outputs = self.console.output
        self.assertTrue(any("line1" in o for o in outputs))
        self.assertTrue(any("line2" in o for o in outputs))

    def test_clear_output(self) -> None:
        self.console.execute("print('test')")
        self.assertGreater(len(self.console.output), 0)
        self.console.clear_output()
        self.assertEqual(len(self.console.output), 0)

    def test_reset_environment(self) -> None:
        self.console.execute("my_var = 99")
        self.assertEqual(self.console.get_var("my_var"), 99)
        self.console.reset_environment()
        self.assertIsNone(self.console.get_var("my_var"))

    def test_syntax_error_returns_error_message(self) -> None:
        result = self.console.execute("if True")
        self.assertIn("Error", result)

    def test_runtime_error_returns_error_message(self) -> None:
        result = self.console.execute("1 / 0")
        self.assertIn("Error", result)

    def test_undefined_variable(self) -> None:
        result = self.console.execute("print(undefined_var)")
        self.assertIn("Error", result)

    def test_list_objects_via_script(self) -> None:
        self.console.execute('create_box(width=1, height=1, depth=1, name="A")')
        result = self.console.execute('list_objects()')
        # list_objects prints the list
        # Since it returns a value, it should appear in output
        self.assertIn("A", result)

    def test_doc_is_accessible(self) -> None:
        result = self.console.execute("doc.name")
        # The return value is not captured
        # But doc is accessible in the environment
        self.assertIsNotNone(self.console.get_var("doc"))

    def test_cmd_is_accessible(self) -> None:
        self.assertIsNotNone(self.console.get_var("cmd"))

    def test_vector2_accessible(self) -> None:
        result = self.console.execute("v = Vector2(3, 4); print(v.length())")
        self.assertIn("5", result)

    def test_execute_file(self) -> None:
        with TemporaryDirectory() as tmp:
            script = Path(tmp) / "test_script.py"
            script.write_text('create_box(width=10, height=20, depth=30, name="FileBox")\nrecompute()\n')
            result = self.console.execute_file(str(script))
            box = self.doc.find_by_name("FileBox")
            self.assertIsNotNone(box)

    def test_execute_file_not_found(self) -> None:
        with self.assertRaises(FileNotFoundError):
            self.console.execute_file("/nonexistent/script.py")

    def test_create_cylinder_via_script(self) -> None:
        self.console.execute('create_cylinder(radius=5, height=15, name="Cyl")')
        cyl = self.doc.find_by_name("Cyl")
        self.assertIsNotNone(cyl)
        self.assertEqual(cyl.get_property_value("radius"), 5)


class TestExecuteScript(unittest.TestCase):
    def test_execute_script_function(self) -> None:
        with TemporaryDirectory() as tmp:
            script = Path(tmp) / "script.py"
            script.write_text('print("hello from script")\n')
            doc = Document("test")
            registry = CommandRegistry()
            register_builtin_commands(registry)
            result = execute_script(str(script), registry, doc)
            self.assertIn("hello from script", result)


if __name__ == "__main__":
    unittest.main()
