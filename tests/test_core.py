import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from src.database import StateDatabase
from src.manim_validator import validate_code
from src.prompt_manager import PromptManager


class CoreTests(unittest.TestCase):
    def test_excel_import_and_status(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            workbook = Workbook()
            workbook.active.append(["Prompts"])
            workbook.active.append(["Animate 6174"])
            path = root / "prompts.xlsx"
            workbook.save(path)
            database = StateDatabase(root / "state.db")
            manager = PromptManager(path, database)
            self.assertEqual(manager.import_prompts(), 1)
            self.assertEqual(database.next_pending()["prompt"], "Animate 6174")

    def test_duplicate_topic_is_reused(self):
        with tempfile.TemporaryDirectory() as directory:
            database = StateDatabase(Path(directory) / "state.db")
            first = database.add_topic("Kaprekar 6174")
            second = database.add_topic("  kaprekar   6174 ")
            self.assertEqual(first, second)

    def test_safe_scene_is_accepted(self):
        code = "from manim import *\nclass Demo(Scene):\n def construct(self):\n  self.add(Text('safe'))"
        self.assertEqual(validate_code(code), "Demo")

    def test_unsafe_code_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_code("import subprocess\nfrom manim import *\nclass X(Scene): pass")


if __name__ == "__main__":
    unittest.main()
