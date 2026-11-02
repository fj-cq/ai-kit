"""Real SVG geometry and arithmetic checks; no browser or network required."""
import copy
import importlib.util
import json
import math
from pathlib import Path
import re
import unittest
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1] / "renderers" / "consulting"
EXAMPLE_ROOT = ROOT.parents[1] / "examples"
MODULE = ROOT / "charts.py"
charts = None
if MODULE.exists():
    loader = importlib.util.spec_from_file_location("charts_under_test", MODULE)
    charts = importlib.util.module_from_spec(loader)
    loader.loader.exec_module(charts)

KINDS = {"bar", "stacked_bar", "line", "slope", "waterfall", "bullet",
         "scatter", "heatmap", "harvey", "sankey", "mekko"}


def spec(kind, data):
    return {"id": "test-" + kind, "kind": kind, "title": "合成供应链示例",
            "takeaway": "数值与几何按同一口径绘制。", "question": "数量如何比较？",
            "unit": "%" if kind == "stacked_bar" else "吨",
            "source": {"kind": "synthetic", "label": "合成演示数据，非企业实绩"},
            "boundary": "仅为合成数据，不表示企业实绩。", "data": data}


def marks(root, role):
    return [el for el in root.iter() if el.get("data-role") == role]


def nums(value):
    return [float(x) for x in re.findall(r"-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?", value)]


class ChartTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(charts, "charts.py real generator is not implemented yet")

    def render(self, kind, data):
        return ET.fromstring(charts.render(spec(kind, data)))

    def test_bar_widths_follow_ratio_and_zero_has_zero_width(self):
        root = self.render("bar", {"items": [{"label": "甲", "value": 10},
                                              {"label": "乙", "value": 20},
                                              {"label": "丙", "value": 0}]})
        bars = marks(root, "bar")
        self.assertEqual(len(bars), 3)
        self.assertAlmostEqual(float(bars[1].get("width")) / float(bars[0].get("width")), 2)
        self.assertEqual(float(bars[2].get("width")), 0)
        self.assertEqual({float(el.get("x")) for el in bars}, {float(bars[0].get("x"))})

    def test_all_zero_bar_is_finite(self):
        root = self.render("bar", {"items": [{"label": "甲", "value": 0}]})
        self.assertEqual(float(marks(root, "bar")[0].get("width")), 0)

    def test_small_bar_values_labels_and_ticks_round_trip_without_becoming_zero(self):
        for value in [1e-7, 1.234567890123456e-10, 0.12345678901234566]:
            with self.subTest(value=value):
                root = self.render("bar", {"items": [{"label": "甲", "value": value}]})
                bar = marks(root, "bar")[0]
                self.assertEqual(float(bar.get("data-value")), value)
                self.assertEqual(float(bar.get("width")), 640)
                value_text = [el.text for el in root.iter() if el.tag.endswith("}text")
                              and el.get("font-size") == "18" and el.get("y") == "165"]
                self.assertEqual([float(text) for text in value_text], [value])
                ticks = [float(el.text) for el in root.iter() if el.tag.endswith("}text")
                         and el.get("y") == "470"]
                self.assertEqual(ticks, [0, value / 2, value])

    def test_tiny_positive_bar_geometry_is_not_rounded_to_zero(self):
        root = self.render("bar", {"items": [{"label": "甲", "value": 1e-10},
                                              {"label": "乙", "value": 1}]})
        a, b = marks(root, "bar")
        self.assertGreater(float(a.get("width")), 0)
        self.assertEqual(float(a.get("width")) / float(b.get("width")), 1e-10)

    def test_stacked_percent_segments_cover_exactly_one_hundred(self):
        root = self.render("stacked_bar", {"series": ["常规", "应急"], "mode": "percent",
                                            "rows": [{"label": "甲", "values": [25, 75]}]})
        a, b = marks(root, "stack")
        self.assertAlmostEqual(float(b.get("width")) / float(a.get("width")), 3)
        self.assertAlmostEqual(float(a.get("x")) + float(a.get("width")), float(b.get("x")))
        self.assertAlmostEqual(sum(float(e.get("width")) for e in (a, b)), 640)

    def test_stacked_percent_rejects_wrong_total(self):
        with self.assertRaises(ValueError):
            self.render("stacked_bar", {"series": ["甲", "乙"], "mode": "percent",
                                        "rows": [{"label": "一", "values": [30, 60]}]})

    def test_line_points_have_shared_scale_and_even_period_spacing(self):
        root = self.render("line", {"labels": ["一", "二", "三"],
                                    "series": [{"label": "需求", "values": [0, 10, 20]}]})
        xy = nums(marks(root, "line")[0].get("points"))
        self.assertAlmostEqual(xy[2] - xy[0], xy[4] - xy[2])
        self.assertAlmostEqual(xy[1] - xy[3], xy[3] - xy[5])
        self.assertGreater(xy[1], xy[5])

    def test_slope_endpoints_use_values_not_equal_spaced_ranks(self):
        root = self.render("slope", {"periods": ["之前", "之后"], "items": [
            {"label": "甲", "start": 20, "end": 40},
            {"label": "乙", "start": 40, "end": 80}]})
        a, b = marks(root, "slope")
        self.assertEqual(float(a.get("y2")), float(b.get("y1")))
        self.assertAlmostEqual((float(b.get("y1")) - float(b.get("y2"))) /
                               (float(a.get("y1")) - float(a.get("y2"))), 2)

    def test_waterfall_signed_changes_and_total_geometry(self):
        root = self.render("waterfall", {"start": 100, "steps": [
            {"label": "到货", "delta": 30}, {"label": "消耗", "delta": -50}], "end": 80})
        start = marks(root, "waterfall-start")[0]
        total = marks(root, "waterfall-total")[0]
        plus, minus = marks(root, "waterfall-delta")
        self.assertAlmostEqual(float(total.get("height")) / float(start.get("height")), .8)
        self.assertAlmostEqual(float(minus.get("height")) / float(plus.get("height")), 5 / 3, places=5)
        self.assertAlmostEqual(float(plus.get("y")) + float(plus.get("height")), float(start.get("y")), places=4)
        self.assertAlmostEqual(float(minus.get("y")) + float(minus.get("height")), float(total.get("y")), places=4)
        texts = "".join(root.itertext())
        self.assertIn("+30", texts)
        self.assertIn("-50", texts)

    def test_waterfall_rejects_inconsistent_final_total(self):
        with self.assertRaises(ValueError):
            self.render("waterfall", {"start": 100, "steps": [{"label": "消耗", "delta": -20}], "end": 90})

    def test_bullet_actual_and_target_use_same_scale(self):
        root = self.render("bullet", {"label": "履约量", "actual": 80, "target": 100,
                                      "max": 120, "ranges": [60, 90, 120]})
        actual = marks(root, "bullet-actual")[0]
        target = marks(root, "bullet-target")[0]
        self.assertAlmostEqual(float(actual.get("width")) /
                               (float(target.get("x1")) - float(actual.get("x"))), .8, places=6)
        self.assertEqual(float(target.get("x1")), float(target.get("x2")))

    def test_bullet_rejects_actual_outside_shared_domain(self):
        with self.assertRaises(ValueError):
            self.render("bullet", {"label": "履约量", "actual": 130, "target": 100,
                                   "max": 120, "ranges": [60, 90, 120]})

    def test_scatter_bubble_area_not_radius_encodes_quantity(self):
        root = self.render("scatter", {"x_label": "交期", "y_label": "成本", "x_unit": "天",
                                       "y_unit": "元", "size_label": "采购量", "size_unit": "吨",
                                       "points": [{"label": "甲", "x": 2, "y": 4, "size": 25},
                                                  {"label": "乙", "x": 4, "y": 8, "size": 100}]})
        a, b = marks(root, "bubble")
        self.assertAlmostEqual(float(b.get("r")) / float(a.get("r")), 2)
        self.assertAlmostEqual(float(b.get("r")) ** 2 / float(a.get("r")) ** 2, 4)

    def test_heatmap_unknown_is_not_numeric_zero(self):
        root = self.render("heatmap", {"rows": ["甲"], "columns": ["一", "二"], "values": [[0, None]]})
        zero, unknown = marks(root, "heat-cell")
        self.assertEqual(zero.get("data-state"), "known")
        self.assertEqual(unknown.get("data-state"), "unknown")
        self.assertNotEqual(zero.get("fill"), unknown.get("fill"))
        self.assertIn("未知", "".join(root.itertext()))

    def test_harvey_has_explicit_five_level_legend(self):
        root = self.render("harvey", {"items": [{"label": str(i), "rating": i} for i in range(5)],
                                      "legend": ["未启动", "已准备", "实施中", "已验证", "已完成"]})
        self.assertEqual(len(marks(root, "harvey-base")), 5)
        self.assertEqual(len(marks(root, "harvey-legend")), 5)
        self.assertEqual(len(marks(root, "harvey-fill")), 4)
        self.assertIn("0/4", "".join(root.itertext()))
        self.assertIn("4/4", "".join(root.itertext()))

    def test_harvey_rejects_fractional_or_out_of_range_rating(self):
        for rating in [.5, 5, -1]:
            with self.subTest(rating=rating), self.assertRaises(ValueError):
                self.render("harvey", {"items": [{"label": "甲", "rating": rating}],
                                       "legend": ["零", "一", "二", "三", "四"]})

    def test_sankey_two_columns_conserve_thickness(self):
        root = self.render("sankey", {"sources": [{"label": "甲", "total": 60}, {"label": "乙", "total": 40}],
                                      "targets": [{"label": "一", "total": 50}, {"label": "二", "total": 50}],
                                      "flows": [[40, 20], [10, 30]]})
        nodes = marks(root, "sankey-source")
        self.assertAlmostEqual(float(nodes[0].get("height")) / float(nodes[1].get("height")), 1.5)
        flows = marks(root, "sankey-flow")
        first, second = nums(flows[0].get("d")), nums(flows[1].get("d"))
        # Closed ribbon: source low is the last y before Z, source high is the first y.
        self.assertAlmostEqual((first[-1] - first[1]) / (second[-1] - second[1]), 2)
        self.assertAlmostEqual((first[-1] - first[1]) + (second[-1] - second[1]), float(nodes[0].get("height")))
        self.assertEqual(len({el.get("x") for el in nodes}), 1)

    def test_sankey_rejects_nonconserving_matrix(self):
        with self.assertRaises(ValueError):
            self.render("sankey", {"sources": [{"label": "甲", "total": 60}],
                                   "targets": [{"label": "一", "total": 50}], "flows": [[50]]})

    def test_sankey_node_names_and_quantities_keep_readable_line_spacing(self):
        item = next(item for item in json.loads((EXAMPLE_ROOT / "quantitative-examples.json").read_text())
                    if item["kind"] == "sankey")
        root = ET.fromstring(charts.render(item))
        for x in (225, 778):
            labels = sorted([el for el in root.iter() if el.tag.endswith("}text")
                             and float(el.get("x")) == x], key=lambda el: float(el.get("y")))
            self.assertEqual(len(labels), 4)
            for name, quantity in zip(labels[::2], labels[1::2]):
                with self.subTest(node=name.text):
                    self.assertGreaterEqual(float(quantity.get("y")) - float(name.get("y")), 30)

    def test_tiny_sankey_cannot_conserve_positive_nodes_with_zero_or_wrong_flow(self):
        for wrong_flow in [0, 9e-11]:
            with self.subTest(flow=wrong_flow), self.assertRaises(ValueError):
                self.render("sankey", {"sources": [{"label": "甲", "total": 1e-10}],
                                       "targets": [{"label": "一", "total": 1e-10}],
                                       "flows": [[wrong_flow]]})

    def test_tiny_sankey_flow_values_round_trip_and_fill_node_height(self):
        root = self.render("sankey", {"sources": [{"label": "甲", "total": 3e-10}],
                                      "targets": [{"label": "一", "total": 1e-10},
                                                  {"label": "二", "total": 2e-10}],
                                      "flows": [[1e-10, 2e-10]]})
        flows = marks(root, "sankey-flow")
        self.assertEqual([float(flow.get("data-value")) for flow in flows], [1e-10, 2e-10])
        thickness = [nums(flow.get("d"))[-1] - nums(flow.get("d"))[1] for flow in flows]
        self.assertAlmostEqual(thickness[1] / thickness[0], 2)
        self.assertAlmostEqual(sum(thickness), float(marks(root, "sankey-source")[0].get("height")))

    def test_mekko_width_and_within_group_height_encode_separate_measures(self):
        root = self.render("mekko", {"series": ["常规", "应急"], "groups": [
            {"label": "甲", "total": 60, "values": [15, 45]},
            {"label": "乙", "total": 40, "values": [20, 20]}]})
        a, b, c, d = marks(root, "mekko-cell")
        self.assertAlmostEqual(float(a.get("width")) / float(c.get("width")), 1.5)
        self.assertAlmostEqual(float(b.get("height")) / float(a.get("height")), 3)
        self.assertAlmostEqual(float(c.get("height")), float(d.get("height")))
        self.assertAlmostEqual(float(a.get("width")) + float(c.get("width")), 840)

    def test_mekko_rejects_inconsistent_group_total(self):
        with self.assertRaises(ValueError):
            self.render("mekko", {"series": ["常规", "应急"], "groups": [
                {"label": "甲", "total": 60, "values": [15, 40]}]})

    def test_nonfinite_numbers_are_rejected_before_svg(self):
        for bad in [float("nan"), float("inf"), -float("inf"), True, "12"]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                self.render("bar", {"items": [{"label": "甲", "value": bad}]})

    def test_size_and_label_limits_raise_instead_of_truncating(self):
        cases = [("bar", {"items": [{"label": "甲", "value": 1}] * 9}),
                 ("line", {"labels": ["甲", "乙"], "series": [{"label": "甲", "values": [1]}]}),
                 ("heatmap", {"rows": ["甲"] * 7, "columns": ["一"], "values": [[1]] * 7}),
                 ("heatmap", {"rows": ["甲"], "columns": ["一"] * 6, "values": [[1] * 6]}),
                 ("bar", {"items": [{"label": "长" * 40, "value": 1}]})]
        for kind, data in cases:
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.render(kind, data)

    def test_user_text_is_xml_escaped_and_ids_are_namespaced(self):
        item = spec("bar", {"items": [{"label": "甲<&乙", "value": 1}]})
        item["title"] = '<script>&"'
        raw = charts.render(item)
        root = ET.fromstring(raw)
        self.assertNotIn("<script>", raw)
        self.assertIn('<script>&"', "".join(root.itertext()))
        ids = [el.get("id") for el in root.iter() if el.get("id")]
        self.assertTrue(all(value.startswith(item["id"] + "-") for value in ids))
        self.assertEqual(len(ids), len(set(ids)))

    def test_invalid_id_metadata_and_control_characters_are_rejected(self):
        original = spec("bar", {"items": [{"label": "甲", "value": 1}]})
        for field, bad in [("id", 'x" onclick="alert(1)'), ("title", "长" * 80), ("unit", ""),
                           ("title", "bad\x00text"), ("kind", "all_networks")]:
            item = copy.deepcopy(original)
            item[field] = bad
            with self.subTest(field=field), self.assertRaises(ValueError):
                charts.render(item)

    def test_unrendered_input_text_cannot_break_accessible_description(self):
        for bad in ["bad\x00text", "长" * 257]:
            item = spec("bar", {"items": [{"label": "甲", "value": 1}], "comment": bad})
            with self.subTest(bad=bad[:12]), self.assertRaises(ValueError):
                charts.render(item)

    def test_source_cannot_silently_change_synthetic_data_to_real_claim(self):
        item = spec("bar", {"items": [{"label": "甲", "value": 1}]})
        item["source"] = {"kind": "enterprise", "label": "真实业绩"}
        with self.assertRaises(ValueError):
            charts.render(item)

    def test_provided_source_is_shown_without_synthetic_or_verified_claim(self):
        item = spec("bar", {"items": [{"label": "甲", "value": 1}]})
        item.update(title="补货数量比较", boundary="仅展示用户提供数字，出处尚未核验。")
        item["source"] = {"kind": "provided", "label": '用户上传 <补货表>&附件'}
        try:
            root = ET.fromstring(charts.render(item))
        except ValueError as error:
            self.fail(f"provided source must be renderable: {error}")
        footer = next(el for el in root.iter() if el.tag.endswith("}text") and el.get("y") == "535")
        desc = root.find("{http://www.w3.org/2000/svg}desc").text
        for text in [footer.text, desc]:
            self.assertIn(item["source"]["label"], text)
            self.assertIn("用户提供来源", text)
            self.assertIn("未核验", text)
            self.assertNotIn("合成", text)

    def test_synthetic_source_with_custom_label_remains_explicitly_synthetic(self):
        item = spec("bar", {"items": [{"label": "甲", "value": 1}]})
        item["source"] = {"kind": "synthetic", "label": "数量演示输入"}
        try:
            root = ET.fromstring(charts.render(item))
        except ValueError as error:
            self.fail(f"synthetic source labels may vary: {error}")
        footer = next(el for el in root.iter() if el.tag.endswith("}text") and el.get("y") == "535")
        desc = root.find("{http://www.w3.org/2000/svg}desc").text
        for text in [footer.text, desc]:
            self.assertIn("合成示例", text)
            self.assertIn("数量演示输入", text)

    def test_source_kind_and_nonempty_bounded_label_are_required(self):
        for source in [None, {}, {"kind": "verified", "label": "凭据"},
                       {"kind": "provided", "label": " "}, {"kind": "synthetic", "label": ""},
                       {"kind": "provided", "label": "长" * 80},
                       {"kind": "provided", "label": 12}, {"kind": "provided", "label": "坏\x00字"}]:
            item = spec("bar", {"items": [{"label": "甲", "value": 1}]})
            item["source"] = source
            with self.subTest(source=source), self.assertRaises(ValueError):
                charts.render(item)

    def test_example_bullet_actual_label_has_clear_gap_below_ticks(self):
        item = next(item for item in json.loads((EXAMPLE_ROOT / "quantitative-examples.json").read_text())
                    if item["kind"] == "bullet")
        root = ET.fromstring(charts.render(item))
        actual = next(el for el in root.iter() if el.tag.endswith("}text") and el.text == "实际 88")
        zero = next(el for el in root.iter() if el.tag.endswith("}text") and el.text == "0")
        self.assertGreaterEqual(float(actual.get("y")) - float(zero.get("y")),
                                float(actual.get("font-size")) + 8)

    def test_example_line_period_labels_clear_the_y_axis_zero(self):
        item = next(item for item in json.loads((EXAMPLE_ROOT / "quantitative-examples.json").read_text())
                    if item["kind"] == "line")
        root = ET.fromstring(charts.render(item))
        first = next(el for el in root.iter() if el.tag.endswith("}text") and el.text == "第1周")
        zero = next(el for el in root.iter() if el.tag.endswith("}text") and el.text == "0")
        self.assertGreaterEqual(float(first.get("y")) - float(zero.get("y")),
                                float(first.get("font-size")) + 8)

    def test_example_scatter_axis_title_has_clear_gap_below_ticks(self):
        item = next(item for item in json.loads((EXAMPLE_ROOT / "quantitative-examples.json").read_text())
                    if item["kind"] == "scatter")
        root = ET.fromstring(charts.render(item))
        title = next(el for el in root.iter() if el.tag.endswith("}text") and el.text == "交期（天）")
        ticks = [el for el in root.iter() if el.tag.endswith("}text") and el.text == "9"
                 and float(el.get("x")) > 800]
        self.assertEqual(len(ticks), 1)
        self.assertGreaterEqual(float(title.get("y")) - float(ticks[0].get("y")),
                                float(title.get("font-size")) + 8)

    def test_example_scatter_and_mekko_units_are_above_chart_annotations(self):
        examples = json.loads((EXAMPLE_ROOT / "quantitative-examples.json").read_text())
        for kind, label in [("scatter", "气泡面积＝采购量（吨）"), ("mekko", "辅料丁")]:
            item = next(item for item in examples if item["kind"] == kind)
            with self.subTest(kind=kind):
                root = ET.fromstring(charts.render(item))
                unit = next(el for el in root.iter() if el.tag.endswith("}text")
                            and el.text.startswith("单位："))
                annotation = next(el for el in root.iter() if el.tag.endswith("}text") and el.text == label)
                self.assertGreaterEqual(float(annotation.get("y")) - float(unit.get("y")),
                                        float(annotation.get("font-size")) + 8)
                self.assertEqual(unit.get("text-anchor"), "start")
                self.assertLessEqual(float(unit.get("x")), 40)

    def test_other_chart_size_caps_and_negative_quantity_reject(self):
        cases = [("bar", {"items": [{"label": "甲", "value": -1}]}),
                 ("line", {"labels": ["一", "二"], "series": [{"label": "甲", "values": [1, 2]}] * 4}),
                 ("sankey", {"sources": [{"label": "甲", "total": 1}] * 4,
                              "targets": [{"label": "乙", "total": 4}], "flows": [[1]] * 4}),
                 ("mekko", {"series": ["甲"] * 5, "groups": [{"label": "一", "total": 5, "values": [1] * 5}]}),
                 ("harvey", {"items": [{"label": "甲", "rating": 1}] * 6,
                              "legend": ["零", "一", "二", "三", "四"]})]
        for kind, data in cases:
            with self.subTest(kind=kind), self.assertRaises(ValueError):
                self.render(kind, data)

    def test_examples_cover_all_kinds_and_are_deterministic_valid_svg(self):
        self.assertTrue((EXAMPLE_ROOT / "quantitative-examples.json").exists())
        examples = json.loads((EXAMPLE_ROOT / "quantitative-examples.json").read_text())
        self.assertEqual(charts.KINDS, KINDS)
        self.assertEqual(len(examples), 11)
        self.assertEqual({item["kind"] for item in examples}, KINDS)
        self.assertEqual(len({item["id"] for item in examples}), 11)
        for item in examples:
            with self.subTest(kind=item["kind"]):
                saved = copy.deepcopy(item)
                output = charts.render(item)
                self.assertEqual(output, charts.render(item))
                self.assertEqual(item, saved)
                root = ET.fromstring(output)
                self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
                self.assertEqual(root.get("viewBox"), "0 0 1000 560")
                self.assertEqual(root.get("id"), item["id"] + "-svg")
                self.assertEqual(root.get("role"), "img")
                self.assertEqual(item["source"]["kind"], "synthetic")
                self.assertIn("合成演示数据，非企业实绩", "".join(root.itertext()))
                self.assertIn(item["unit"], "".join(root.itertext()))
                for element in root.iter():
                    for attr in ("x", "y", "x1", "y1", "x2", "y2", "cx", "cy", "width", "height", "r"):
                        if element.get(attr) is not None:
                            self.assertTrue(math.isfinite(float(element.get(attr))))
                    if element.tag.endswith("}text"):
                        self.assertGreaterEqual(float(element.get("font-size", 18)), 15)
                    if element.tag.endswith("}rect") and element.get("data-role"):
                        x, y, w, h = [float(element.get(attr)) for attr in ("x", "y", "width", "height")]
                        self.assertGreaterEqual(x, 40)
                        self.assertGreaterEqual(y, 105)
                        self.assertLessEqual(x + w, 960.0001)
                        self.assertLessEqual(y + h, 475.0001)


if __name__ == "__main__":
    unittest.main()
