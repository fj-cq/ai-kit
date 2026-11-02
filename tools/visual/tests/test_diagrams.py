"""Contract tests exercise generated graphics, not source-string snapshots."""
import copy
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1] / "renderers" / "consulting"
EXAMPLE_ROOT = ROOT.parents[1] / "examples"
sys.path.insert(0, str(ROOT))
EXAMPLES = json.loads((EXAMPLE_ROOT / "diagram-examples.json").read_text())
try:
    import diagrams
except ModuleNotFoundError:
    diagrams = None
NS = {"s": "http://www.w3.org/2000/svg"}


class DiagramContracts(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(diagrams, "关系图案例绘制器尚未实现")

    def fixture(self, kind):
        return copy.deepcopy(next(s for s in EXAMPLES if s["kind"] == kind))

    def test_all_cases_are_standalone_accessible_svg(self):
        for case in EXAMPLES:
            with self.subTest(kind=case["kind"]):
                root = ET.fromstring(diagrams.render(case))
                self.assertEqual(root.attrib["viewBox"], "0 0 1000 560")
                self.assertEqual(root.attrib["role"], "img")
                self.assertEqual(root.find("s:title", NS).text, case["title"])
                self.assertIn(case["question"], root.find("s:desc", NS).text)
                visible = "".join(root.itertext())
                self.assertIn(case["source"]["label"], visible)
                self.assertIn(case["unit"], visible)
                self.assertFalse(root.findall(".//s:script", NS))

    def test_user_text_is_escaped_without_markup_execution(self):
        case = self.fixture("evidence_table")
        case["data"]["rows"][0][0] = "<x>&引用"
        root = ET.fromstring(diagrams.render(case))
        self.assertIn("<x>&引用", "".join(root.itertext()))
        self.assertFalse(root.findall(".//x"))

    def test_duplicate_nodes_are_rejected(self):
        case = self.fixture("process")
        case["data"]["nodes"][1]["id"] = "notice"
        with self.assertRaises(ValueError):
            diagrams.render(case)

    def test_unknown_edge_target_is_rejected(self):
        case = self.fixture("process")
        case["data"]["edges"][0]["to"] = "nonexistent"
        with self.assertRaises(ValueError):
            diagrams.render(case)

    def test_merge_preserves_all_required_and_single_outgoing_arrow(self):
        case = self.fixture("process")
        root = ET.fromstring(diagrams.render(case))
        arrows = [p for p in root.findall(".//s:path", NS) if "marker-end" in p.attrib]
        self.assertEqual(len(arrows), 2)  # one after merge, one plan -> review
        self.assertEqual(len(root.findall(".//s:circle", NS)), 1)
        self.assertIn("两项齐备", "".join(root.itertext()))

    def test_ambiguous_merge_is_rejected(self):
        case = self.fixture("process")
        case["data"]["merges"][0]["mode"] = "unknown"
        with self.assertRaises(ValueError):
            diagrams.render(case)

    def test_merge_label_clears_the_vertical_input_line(self):
        root = ET.fromstring(diagrams.render(self.fixture("process")))
        label = next(t for t in root.findall(".//s:text", NS) if "两项齐备" in "".join(t.itertext()))
        # Four CJK glyphs at >=15 units must lie wholly right of x=340.
        self.assertGreater(float(label.attrib["x"]) - 30, 342)

    def test_nodes_outside_drawing_area_are_rejected(self):
        case = self.fixture("process")
        case["data"]["nodes"][0]["x"] = 990
        with self.assertRaises(ValueError):
            diagrams.render(case)

    def test_node_overlap_is_rejected(self):
        case = self.fixture("process")
        case["data"]["nodes"][1]["y"] = 140
        with self.assertRaises(ValueError):
            diagrams.render(case)

    def test_swimlane_role_and_step_are_not_inferred(self):
        case = self.fixture("swimlane")
        case["data"]["nodes"][1]["lane"] = 4
        with self.assertRaises(ValueError):
            diagrams.render(case)

    def test_tree_does_not_add_causal_arrowheads(self):
        root = ET.fromstring(diagrams.render(self.fixture("issue_tree")))
        self.assertFalse([p for p in root.findall(".//s:path", NS) if "marker-end" in p.attrib])

    def test_gantt_bars_reflect_duration(self):
        root = ET.fromstring(diagrams.render(self.fixture("gantt")))
        bars = root.findall('.//s:rect[@data-role="task"]', NS)
        widths = [float(e.attrib["width"]) for e in bars]
        self.assertEqual(len(widths), 5)
        self.assertAlmostEqual(widths[1], 2 * widths[0], places=3)
        self.assertAlmostEqual(widths[2], widths[0], places=3)

    def test_gantt_rejects_predecessor_finishing_after_start(self):
        case = self.fixture("gantt")
        case["data"]["tasks"][-1]["start"] = 4
        with self.assertRaises(ValueError):
            diagrams.render(case)

    def test_gantt_rejects_invalid_range(self):
        case = self.fixture("gantt")
        case["data"]["tasks"][0]["end"] = 0
        with self.assertRaises(ValueError):
            diagrams.render(case)

    def test_raci_requires_one_accountable_per_row(self):
        case = self.fixture("raci")
        case["data"]["rows"][0][2] = "A"
        with self.assertRaises(ValueError):
            diagrams.render(case)

    def test_source_required(self):
        case = self.fixture("roadmap")
        del case["source"]
        with self.assertRaises(ValueError):
            diagrams.render(case)

    def test_source_status_is_visible_and_does_not_imply_verification(self):
        for kind, marker in [("provided", "未核验"), ("synthetic", "合成示例")]:
            case = self.fixture("evidence_table")
            case["source"] = {"kind": kind, "label": "台账摘录"}
            root = ET.fromstring(diagrams.render(case))
            visible = "".join("".join(t.itertext()) for t in root.findall(".//s:text", NS))
            self.assertIn(marker, visible)
            self.assertIn("台账摘录", visible)

    def test_footer_that_exceeds_canvas_is_rejected(self):
        case = self.fixture("evidence_table")
        case["source"]["label"] = "来源" * 35
        with self.assertRaises(ValueError):
            diagrams.render(case)

    def test_final_roadmap_gate_is_acceptance_not_an_implied_extra_phase(self):
        root = ET.fromstring(diagrams.render(self.fixture("roadmap")))
        visible = "".join("".join(t.itertext()) for t in root.findall('.//s:text[@class="label-small"]', NS))
        self.assertEqual(visible.count("进入下一阶段的条件"), 2)
        self.assertIn("本阶段的验收条件", visible)

    def test_largest_issue_tree_has_no_overlapping_child_boxes(self):
        case = self.fixture("issue_tree")
        case["data"]["branches"] = [
            {"label": str(i), "children": [f"子项{i}{j}" for j in range(3)]}
            for i in range(3)
        ]
        root = ET.fromstring(diagrams.render(case))
        boxes = [r for r in root.findall(".//s:rect", NS) if r.get("class") == "node-soft"]
        self.assertEqual(len(boxes), 9)
        for left, right in zip(boxes, boxes[1:]):
            self.assertGreaterEqual(float(right.get("y")) - float(left.get("y")) - float(left.get("height")), 6)

    def test_no_silent_label_truncation(self):
        case = self.fixture("process")
        case["data"]["nodes"][0]["label"] = "很长" * 50
        with self.assertRaises(ValueError):
            diagrams.render(case)


if __name__ == "__main__":
    unittest.main()
