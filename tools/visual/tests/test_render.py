import importlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1] / "renderers" / "consulting"
EXAMPLE_ROOT = ROOT.parents[1] / "examples"
sys.path.insert(0, str(ROOT))
try:
    renderer = importlib.import_module("render")
except ModuleNotFoundError:
    renderer = None


class OutputContracts(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(renderer, "案例导出入口尚未实现")

    def test_gallery_is_offline_and_keeps_all_source_specs(self):
        cases = json.loads((EXAMPLE_ROOT / "diagram-examples.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "gallery"
            result = renderer.build_gallery(cases, output)
            html = (output / "index.html").read_text()
            self.assertEqual(result["case_count"], 8)
            self.assertEqual(len(list((output / "svg").glob("*.svg"))), 8)
            self.assertEqual(len(list((output / "specs").glob("*.json"))), 8)
            self.assertNotIn("<script", html)
            self.assertNotIn("<iframe", html)
            self.assertNotIn("<link", html)
            self.assertEqual(html.count('class="case"'), 8)
            self.assertEqual(len(result["files"]), 17)
            self.assertIn("合成", html)

    def test_existing_user_file_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "keep.txt"
            target.write_text("user content")
            with self.assertRaises(FileExistsError):
                renderer.write_new(target, "replacement")
            self.assertEqual(target.read_text(), "user content")

    def test_gallery_does_not_mislabel_user_provided_sources_as_synthetic(self):
        cases = json.loads((EXAMPLE_ROOT / "diagram-examples.json").read_text())[:1]
        cases[0]["source"] = {"kind": "provided", "label": "用户提供的台账摘录"}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "gallery"
            renderer.build_gallery(cases, output)
            html = (output / "index.html").read_text()
            self.assertNotIn("所有示例均为合成内容", html)
            self.assertIn("来源状态见各图", html)

    def test_duplicate_ids_fail_before_writing(self):
        cases = json.loads((EXAMPLE_ROOT / "diagram-examples.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "gallery"
            with self.assertRaises(ValueError):
                renderer.build_gallery([cases[0], cases[0]], target)
            self.assertFalse(target.exists())

    def test_invalid_case_fails_before_partial_output(self):
        cases = json.loads((EXAMPLE_ROOT / "diagram-examples.json").read_text())
        cases[-1]["source"] = None
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "gallery"
            with self.assertRaises(ValueError):
                renderer.build_gallery(cases, target)
            self.assertFalse(target.exists())

    def test_single_case_command_writes_real_svg(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "process.svg"
            run = subprocess.run([sys.executable, str(ROOT / "render.py"), "--case", "process", "--output", str(target)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertIn("<svg", target.read_text())
            self.assertIn("两项齐备", target.read_text())


if __name__ == "__main__":
    unittest.main()
