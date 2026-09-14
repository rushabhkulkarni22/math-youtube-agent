import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from openpyxl import Workbook
from groq import BadRequestError

from src.database import StateDatabase
from src.manim_validator import validate_code
from src.llm.groq_provider import GroqProvider
from src.prompt_manager import PromptManager
from src.youtube_uploader import sanitize_description


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

    def test_actionable_prompt_can_exclude_failed_attempt_in_same_run(self):
        with tempfile.TemporaryDirectory() as directory:
            database = StateDatabase(Path(directory) / "state.db")
            first = database.add_topic("First topic")
            second = database.add_topic("Second topic")
            self.assertEqual(database.next_actionable({first})["id"], second)

    def test_safe_scene_is_accepted(self):
        code = "from manim import *\nclass Demo(Scene):\n def construct(self):\n  self.add(Text('safe'))"
        self.assertEqual(validate_code(code), "Demo")

    def test_unsafe_code_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_code("import subprocess\nfrom manim import *\nclass X(Scene): pass")

    def test_youtube_description_is_sanitized(self):
        unsafe = "Proof <script>\x00" + ("x" * 6000)
        cleaned = sanitize_description(unsafe)
        self.assertNotIn("<", cleaned)
        self.assertNotIn(">", cleaned)
        self.assertNotIn("\x00", cleaned)
        self.assertLessEqual(len(cleaned), 4900)

    def test_groq_retry_delay_parses_minutes_and_seconds(self):
        error = Mock()
        error.__str__ = Mock(return_value="try again in 23m50.5s")
        self.assertAlmostEqual(GroqProvider._retry_delay(error, 0), 1432.5)

    def test_groq_provider_requests_native_json_mode(self):
        provider = object.__new__(GroqProvider)
        provider._complete = Mock(return_value='{"answer": 42}')
        self.assertEqual(provider.generate_json("system", "user"), {"answer": 42})
        provider._complete.assert_called_once_with(
            "system", "user", 4500, json_mode=True
        )

    def test_invalid_native_json_is_retried(self):
        provider = object.__new__(GroqProvider)
        provider.client = Mock()
        provider.models = ["openai/gpt-oss-20b"]
        provider.unavailable_models = set()
        bad = BadRequestError(
            "json_validate_failed", response=Mock(status_code=400), body=None
        )
        provider.client.chat.completions.create.side_effect = [
            bad,
            Mock(choices=[Mock(message=Mock(content='{"answer": 42}'))]),
        ]
        self.assertEqual(provider.generate_json("system", "user"), {"answer": 42})
        self.assertEqual(provider.client.chat.completions.create.call_count, 2)


if __name__ == "__main__":
    unittest.main()
