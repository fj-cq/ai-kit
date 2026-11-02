#!/usr/bin/env python3
"""Independent, stdlib-only checks for two synthetic visual-entry exercises.

--artifacts DIR is read-only and verifies a/b.json, a/b.svg, a/b.html.
--fixture NEW_DIR uses handwritten inputs and the real render.py CLI, then runs
the same checks plus mutation tests. It refuses an existing output directory.

This is a fixed exercise oracle, not a general business-truth validator. It does
not import renderer functions or derive expected business values from outputs.
Browser layout, full CSS visibility, editorial quality, real adoption, model
calls, PPT and cross-machine behavior remain separate acceptance boundaries.
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import html
from html.parser import HTMLParser
import json
import math
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1] / "renderers" / "consulting"
FILES = tuple(f"{case}.{extension}" for case in "ab" for extension in ("json", "svg", "html"))
BOUNDARY = {
    "proves": ["fixed synthetic input contract", "SVG content and relationship geometry",
               "actual inline SVG equivalence", "static offline and no-script checks"],
    "does_not_prove": ["business truth or adoption", "complete natural-language claim detection",
                       "HTML sanitization or general SVG interpretation", "browser layout or full CSS visibility",
                       "model success", "PPT", "cross-machine compatibility"],
}

# Handwritten before rendering; these values are the fixed exercise, not a
# renderer snapshot. Wording and local IDs of submitted artifacts may differ.
FIXTURES = {
    "a": {
        "id": "cost-change", "kind": "waterfall", "title": "成本净增加20万元，来自三项增减",
        "takeaway": "运输与损耗合计增加27万元，分拣减少7万元。",
        "question": "成本从基准到结果经过哪些增减？", "unit": "万元",
        "source": {"kind": "synthetic", "label": "合成演示数据，非企业实绩"},
        "boundary": "示例用于解释成本变化构成，不代表真实经营成果。",
        "data": {"start": 100, "steps": [{"label": "运输", "delta": 18},
                    {"label": "分拣", "delta": -7}, {"label": "损耗", "delta": 9}], "end": 120},
    },
    "b": {
        "id": "necessary-inputs", "kind": "process", "title": "两份输入齐备，建议经人工确认后执行",
        "takeaway": "需求预测与库存信息缺一不可；人工确认是执行前置条件。",
        "question": "哪些输入共同必要，建议何时才能执行？", "unit": "步骤",
        "source": {"kind": "synthetic", "label": "合成流程示例，非真实业务上线"},
        "boundary": "流程说明方案关系，不代表实际采用，也不推算收益。",
        "data": {
            "nodes": [
                {"id": "forecast", "label": "需求预测", "x": 40, "y": 160, "w": 170, "h": 72},
                {"id": "inventory", "label": "库存信息", "x": 40, "y": 330, "w": 170, "h": 72},
                {"id": "calculate", "label": "计算建议", "x": 420, "y": 245, "w": 150, "h": 72},
                {"id": "confirm", "label": "人工确认", "x": 630, "y": 245, "w": 150, "h": 72},
                {"id": "execute", "label": "执行", "x": 840, "y": 245, "w": 120, "h": 72}],
            "edges": [{"from": "calculate", "to": "confirm", "meaning": "建议提交人工确认"},
                      {"from": "confirm", "to": "execute", "meaning": "人工确认后才能执行"}],
            "merges": [{"from": ["forecast", "inventory"], "to": "calculate",
                        "point": [290, 281], "mode": "all_required", "label": "两项齐备"}],
        },
    },
}


def compact(value):
    return re.sub(r"\s+", "", str(value)).replace("−", "-").replace("＋", "+")


def tag(element):
    return element.tag.rsplit("}", 1)[-1].lower()


def close(actual, expected):
    try:
        return math.isfinite(float(actual)) and math.isclose(float(actual), expected, rel_tol=1e-7, abs_tol=1e-5)
    except (TypeError, ValueError):
        return False


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def text_of(element):
    return compact("".join(element.itertext()))


def hidden(attrs):
    normalized = {key.lower(): str(value).lower() for key, value in attrs.items()}
    return ("hidden" in normalized or normalized.get("aria-hidden") == "true"
            or normalized.get("display") == "none" or normalized.get("visibility") == "hidden"
            or normalized.get("opacity") == "0"
            or bool(re.search(r"(?:display\s*:\s*none|visibility\s*:\s*hidden|opacity\s*:\s*0(?:[;} ]|$))",
                              normalized.get("style", ""))))


def visible_svg_texts(root):
    result = []
    def walk(node, concealed=False):
        concealed = concealed or hidden(node.attrib)
        if not concealed and tag(node) == "text":
            result.append(node)
        for child in node:
            walk(child, concealed)
    walk(root)
    return result


def resource_issues(name, attrs, css=""):
    issues = []
    attrs = {key.rsplit("}", 1)[-1].lower(): value or "" for key, value in attrs.items()}
    if name in {"script", "iframe", "object", "embed", "foreignobject", "base"}:
        issues.append("forbidden active/embedded element: " + name)
    for key, value in attrs.items():
        if key.startswith("on"):
            issues.append("event handler: " + key)
        if key in {"src", "href", "poster", "data", "action", "formaction", "srcset", "ping", "background"}:
            if value and not value.strip().startswith("#"):
                issues.append("non-fragment resource/reference: " + key)
        if key == "srcdoc":
            issues.append("embedded HTML: srcdoc")
    if name == "meta" and attrs.get("http-equiv", "").lower() == "refresh":
        issues.append("automatic navigation: meta refresh")
    # SVG presentation attributes (fill, filter, marker-end, etc.) can also
    # load url(...), so checking only a style attribute would miss resources.
    style = css + " " + " ".join(attrs.values())
    if re.search(r"@import\b|@font-face\b|expression\s*\(|-moz-binding|javascript\s*:", style, re.I):
        issues.append("active/imported CSS")
    # CSS escape sequences can hide a URL from a static scanner. This narrowly
    # scoped exercise needs none, so reject rather than pretend to decode CSS.
    if "\\" in style:
        issues.append("escaped CSS unsupported by offline scanner")
    for match in re.finditer(r"url\s*\((.*?)\)", style, re.I | re.S):
        if not match.group(1).strip(" \t\r\n\"'").startswith("#"):
            issues.append("non-fragment CSS URL")
    return issues


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__(convert_charrefs=False)
        self.issues, self.words, self.svgs = [], [], []
        self.stack, self.svg_parts, self.svg_depth = [], [], 0
        self.feed(source)
        self.close()

    def attributes(self, pairs):
        names = [name.lower() for name, _ in pairs]
        if len(names) != len(set(names)):
            self.issues.append("duplicate HTML attributes are unsupported")
        return dict(pairs)

    def handle_starttag(self, name, pairs):
        attrs = self.attributes(pairs)
        self.issues.extend(resource_issues(name, attrs))
        if name == "svg":
            self.svg_depth += 1
        if self.svg_depth:
            self.svg_parts.append(self.get_starttag_text())
        if name not in {"meta", "link", "img", "br", "hr", "input", "source", "wbr", "area", "base", "embed"}:
            self.stack.append((name, hidden(attrs)))

    def handle_startendtag(self, name, pairs):
        self.issues.extend(resource_issues(name, self.attributes(pairs)))
        if self.svg_depth:
            self.svg_parts.append(self.get_starttag_text())

    def handle_endtag(self, name):
        if self.svg_depth:
            self.svg_parts.append(f"</{name}>")
        if name == "svg" and self.svg_depth:
            self.svg_depth -= 1
            if not self.svg_depth:
                self.svgs.append("".join(self.svg_parts))
                self.svg_parts = []
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index][0] == name:
                del self.stack[index:]
                break

    def handle_data(self, value):
        if self.svg_depth:
            self.svg_parts.append(value)
        if self.stack and self.stack[-1][0] == "style":
            self.issues.extend(resource_issues("style", {}, value))
        if not any(is_hidden or name in {"head", "script", "style", "title", "desc", "metadata"}
                   for name, is_hidden in self.stack):
            self.words.append(value)

    def handle_entityref(self, name):
        if self.svg_depth:
            self.svg_parts.append("&" + name + ";")
        if not any(is_hidden or node in {"head", "style", "script", "title", "desc", "metadata"}
                   for node, is_hidden in self.stack):
            self.words.append(html.unescape("&" + name + ";"))

    def handle_charref(self, name):
        self.handle_entityref("#" + name)


def canonical_svg(root):
    """Ignore XML declaration, insignificant whitespace and consistent local ID renaming."""
    ids = [node.get("id") for node in root.iter() if node.get("id")]
    mapping = {value: f"local-{index}" for index, value in enumerate(ids)}
    def normalize(value):
        for original in sorted(mapping, key=len, reverse=True):
            value = re.sub(r"(?<![\w-])" + re.escape(original) + r"(?![\w-])", mapping[original], value)
        return re.sub(r"\s+", " ", value).strip()
    def visit(node):
        # Qualified names are semantic: fake:width is not SVG's width.
        return (node.tag, tuple(sorted((key, normalize(value))
                                       for key, value in node.attrib.items())),
                normalize(node.text or ""), tuple((visit(child), normalize(child.tail or "")) for child in node))
    return visit(root)


def claim_issues(text):
    """Conservative explicit-claim screen, not a semantic truth classifier."""
    text = compact(text)
    pattern = re.compile(r"已(?:经)?(?:上线|投产|落地|采用|应用|产生收益|实现收益)|真实(?:经营成果|经营数据|业务成果|生产数据)|企业实绩")
    issues = []
    for match in pattern.finditer(text):
        prefix = text[max(0, match.start() - 14):match.start()]
        if not re.search(r"非|不代表|不构成|不证明|不等于|不是|尚未|未|不得|不能|没有|不意味着|不声称", prefix):
            issues.append(match.group())
    return issues


class Checks:
    def __init__(self, directory):
        self.directory, self.items = str(directory), []

    def add(self, identifier, description, passed, detail=None):
        record = {"id": identifier, "description": description, "pass": bool(passed)}
        if not passed:
            record["detail"] = detail if detail is not None else "condition not satisfied"
        self.items.append(record)

    def report(self):
        failures = [item for item in self.items if not item["pass"]]
        return {"schema_version": 1, "artifacts": self.directory, "pass": not failures,
                "assertion_count": len(self.items), "passed": len(self.items) - len(failures),
                "failed": len(failures), "checks": self.items, "failures": failures, "boundary": BOUNDARY}


def load_case(directory, case, checks):
    ident = case.upper()
    payload = {}
    for extension in ("json", "svg", "html"):
        path = directory / f"{case}.{extension}"
        try:
            payload[extension] = path.read_text(encoding="utf-8")
            error = None
        except (OSError, UnicodeError) as exc:
            error = str(exc)
        checks.add(f"{ident}-FILE-{extension.upper()}", f"{path.name} is readable", error is None, error)
    if len(payload) != 3:
        return None
    try:
        spec = json.loads(payload["json"])
        if not isinstance(spec, dict):
            raise ValueError("top-level JSON must be an object")
        checks.add(f"{ident}-JSON-01", "structured input parses", True)
    except (ValueError, TypeError) as exc:
        checks.add(f"{ident}-JSON-01", "structured input parses", False, str(exc))
        return None
    try:
        root = ET.fromstring(payload["svg"])
        valid = tag(root) == "svg"
        checks.add(f"{ident}-SVG-01", "actual SVG parses", valid)
        if not valid:
            return None
    except ET.ParseError as exc:
        checks.add(f"{ident}-SVG-01", "actual SVG parses", False, str(exc))
        return None
    titles = [node for node in root if tag(node) == "title"]
    descriptions = [node for node in root if tag(node) == "desc"]
    checks.add(f"{ident}-SVG-02", "SVG has nonempty accessible title and description",
               len(titles) == len(descriptions) == 1 and bool(text_of(titles[0]))
               and bool(text_of(descriptions[0])) and root.get("role") == "img")
    checks.add(f"{ident}-SVG-03", "SVG title matches its own input, not an oracle headline",
               len(titles) == 1 and text_of(titles[0]) == compact(spec.get("title", "")))
    ids = [node.get("id") for node in root.iter() if node.get("id")]
    labelled = root.get("aria-labelledby", "").split()
    checks.add(f"{ident}-SVG-04", "local SVG IDs are unique and accessibility references resolve",
               len(ids) == len(set(ids)) and bool(labelled) and all(value in ids for value in labelled))
    issues = []
    for node in root.iter():
        issues.extend(resource_issues(tag(node), node.attrib, "".join(node.itertext()) if tag(node) == "style" else ""))
    checks.add(f"{ident}-SVG-05", "SVG has no external resource or active content", not issues, issues)
    checks.add(f"{ident}-SVG-06", "SVG uses the required 1000 by 560 canvas",
               root.get("viewBox", "").split() == ["0", "0", "1000", "560"])
    page = Page(payload["html"])
    checks.add(f"{ident}-HTML-01", "HTML includes a document and body",
               bool(re.search(r"<html\b", payload["html"], re.I)) and bool(re.search(r"<body\b", payload["html"], re.I)))
    checks.add(f"{ident}-HTML-02", "HTML is self-contained and has no scripts or active content", not page.issues, page.issues)
    checks.add(f"{ident}-HTML-03", "HTML contains exactly one actual inline SVG", len(page.svgs) == 1, {"inline_svg_count": len(page.svgs)})
    try:
        embedded = ET.fromstring(page.svgs[0]) if len(page.svgs) == 1 else None
        same = embedded is not None and canonical_svg(root) == canonical_svg(embedded)
        detail = "embedded SVG differs from actual SVG file"
    except ET.ParseError as exc:
        same, detail = False, str(exc)
    checks.add(f"{ident}-HTML-04", "HTML embeds the real SVG; consistent local-ID prefixes are allowed", same, detail)
    glyphs = visible_svg_texts(root)
    svg_text = "".join(text_of(node) for node in glyphs)
    page_text = compact("".join(page.words))
    source = spec.get("source", {})
    source = source if isinstance(source, dict) else {}
    label = compact(source.get("label", ""))
    checks.add(f"{ident}-SOURCE-01", "input explicitly declares a noncontradictory synthetic source",
               source.get("kind") == "synthetic" and bool(re.search(r"合成|synthetic", label, re.I))
               and not claim_issues(label), {"source": source})
    checks.add(f"{ident}-SOURCE-02", "synthetic provenance is in actual visible SVG text",
               bool(label) and label in svg_text and "合成" in svg_text)
    checks.add(f"{ident}-SOURCE-03", "synthetic provenance is in visible page content",
               bool(label) and label in page_text and "合成" in page_text)
    claims = claim_issues(page_text) + claim_issues(svg_text)
    checks.add(f"{ident}-CLAIM-01", "no explicit real-business achievement claim", not claims, claims)
    return spec, root, glyphs, page_text


def verify_a(loaded, checks):
    spec, root, glyphs, page_text = loaded
    data = spec.get("data", {})
    data = data if isinstance(data, dict) else {}
    steps = data.get("steps", [])
    steps = steps if isinstance(steps, list) else []
    actual = [(item.get("label"), item.get("delta")) for item in steps if isinstance(item, dict)]
    checks.add("A-SPEC-01", "cost contribution uses waterfall and 万元", spec.get("kind") == "waterfall" and spec.get("unit") == "万元")
    original_steps = {"运输": 18, "分拣": -7, "损耗": 9}
    valid_steps = (len(actual) == 3 and all(finite(value) for _, value in actual)
                   and all(isinstance(label, str) for label, _ in actual) and dict(actual) == original_steps)
    checks.add("A-SPEC-02", "baseline and signed contributions preserve original values",
               finite(data.get("start")) and data["start"] == 100 and valid_steps,
               {"start": data.get("start"), "steps": actual})
    checks.add("A-SPEC-03", "declared result is 120 万元", finite(data.get("end")) and data["end"] == 120, {"end": data.get("end")})
    arithmetic = (finite(data.get("start")) and finite(data.get("end")) and len(actual) == 3
                  and all(finite(value) for _, value in actual)
                  and data["start"] + sum(value for _, value in actual) == data["end"])
    checks.add("A-SPEC-04", "baseline plus signed changes equals declared result", arithmetic)
    # Input ordering is an editorial choice. The hardcoded source facts remain
    # the oracle; only their placement follows the submitted input ordering.
    order = [label for label, _ in actual] if valid_steps else list(original_steps)
    expected, running = [("waterfall-start", 0, 100, 100)], 100
    for label in order:
        delta = original_steps[label]
        expected.append(("waterfall-delta", running, running + delta, delta))
        running += delta
    expected.append(("waterfall-total", 0, 120, 120))
    bars = [node for node in root.iter() if (node.get("data-role") or "").startswith("waterfall-")]
    checks.add("A-CONTENT-01", "five actual waterfall bars preserve start, deltas and result",
               len(bars) == 5 and all(tag(node) == "rect" and node.get("data-role") == role
                   and close(node.get("data-start"), start) and close(node.get("data-end"), end)
                   and close(node.get("data-value"), value)
                   for node, (role, start, end, value) in zip(bars, expected)))
    expected_glyphs = ([("100", "期初")] + [(f"{original_steps[label]:+d}", label) for label in order]
                       + [("120", "期末")])
    matched = len(bars) == 5
    for bar, (number, label) in zip(bars, expected_glyphs):
        try:
            center = float(bar.get("x")) + float(bar.get("width")) / 2
        except (TypeError, ValueError):
            matched = False
            continue
        words = {text_of(node) for node in glyphs if close(node.get("x"), center)}
        matched = matched and number in words and label in words
    checks.add("A-CONTENT-02", "original numeric glyphs and plus/minus signs belong to corresponding bars", matched)
    geometry = len(bars) == 5
    try:
        scale = float(bars[0].get("height")) / 100
        zero = float(bars[0].get("y")) + float(bars[0].get("height"))
        geometry = geometry and scale > 0
        for bar, (_, start, end, _) in zip(bars, expected):
            geometry = geometry and close(bar.get("height"), abs(end - start) * scale)
            geometry = geometry and close(bar.get("y"), zero - max(start, end) * scale)
    except (IndexError, TypeError, ValueError):
        geometry = False
    checks.add("A-CONTENT-03", "actual bar geometry uses one consistent linear value scale", geometry)
    checks.add("A-CONTENT-04", "万元 is visible in both the SVG and page",
               any("万元" in text_of(node) for node in glyphs) and "万元" in page_text)
    widths_ok = len(bars) == 5
    for bar in bars:
        try:
            x, width = float(bar.get("x")), float(bar.get("width"))
            widths_ok = widths_ok and math.isfinite(x) and math.isfinite(width) and width > 0 and 0 <= x < x + width <= 1000
        except (TypeError, ValueError):
            widths_ok = False
    checks.add("A-CONTENT-05", "actual bars have finite positive width and fit the canvas", widths_ok)


def point_equal(left, right):
    return len(left) == len(right) == 2 and all(close(a, b) for a, b in zip(left, right))


def path_points(path):
    """Read the actual orthogonal polyline; do not reconstruct a renderer path."""
    value = path.get("d", "")
    tokens = re.findall(r"[MHV]|[-+]?(?:\d*\.\d+|\d+\.?)(?:[eE][-+]?\d+)?", value)
    if re.sub(r"[\s,]+", "", "".join(tokens)) != re.sub(r"[\s,]+", "", value):
        raise ValueError("unsupported nonorthogonal path")
    cursor, points, index = [0.0, 0.0], [], 0
    while index < len(tokens):
        command = tokens[index]
        if command == "M":
            if index != 0:
                raise ValueError("disconnected subpaths are not allowed; exactly one initial M is required")
            cursor = [float(tokens[index + 1]), float(tokens[index + 2])]
            index += 3
        elif command in {"H", "V"}:
            if not points:
                raise ValueError("flow path must begin with M")
            cursor[0 if command == "H" else 1] = float(tokens[index + 1])
            index += 2
        else:
            raise ValueError("missing path command")
        if not all(math.isfinite(value) for value in cursor):
            raise ValueError("non-finite flow path coordinate")
        points.append(tuple(cursor))
    if len(points) < 2:
        raise ValueError("flow path needs two endpoints")
    return points


def transfer_marker_contract(root, identifier):
    """Check only this renderer's explicit, opaque, forward transfer marker.

    This deliberately rejects alternate SVG marker constructions; it is not a
    general SVG or CSS visibility interpreter. Local ID renaming is permitted.
    """
    namespace = "{http://www.w3.org/2000/svg}"
    matches = [node for node in root.iter() if node.get("id") == identifier]
    if len(matches) != 1 or matches[0].tag != namespace + "marker":
        return False, "arrow reference must resolve to one SVG marker, not another element"
    marker = matches[0]
    fields = {"id", "viewBox", "refX", "refY", "markerWidth", "markerHeight", "orient"}
    if set(marker.attrib) != fields or marker.get("orient") != "auto":
        return False, "marker requires the renderer's explicit auto orientation and unmodified attributes"
    if marker.get("viewBox", "").split() != ["0", "0", "10", "10"] or not all(
            close(marker.get(key), value) for key, value in [("refX", 8), ("refY", 5), ("markerWidth", 7), ("markerHeight", 7)]):
        return False, "marker viewport, reference point or visible dimensions differ from the finite contract"
    if len(marker) != 1 or marker[0].tag != namespace + "path" or set(marker[0].attrib) != {"d", "fill"}:
        return False, "marker must contain exactly the renderer's unmodified filled arrow path"
    arrow = marker[0]
    if not re.fullmatch(r"M\s*0[ ,]+0\s*L\s*10[ ,]+5\s*L\s*0[ ,]+10\s*[zZ]", arrow.get("d", "").strip()) or arrow.get("fill", "").lower() != "#1e2878":
        return False, "marker must use the opaque, forward-facing transfer triangle"
    parents = {child: parent for parent in root.iter() for child in parent}
    if parents.get(marker) is None or parents[marker].tag != namespace + "defs":
        return False, "marker must be declared in SVG defs"
    ancestor = parents.get(marker)
    while ancestor is not None:
        if hidden(ancestor.attrib):
            return False, "marker has an explicitly hidden ancestor"
        ancestor = parents.get(ancestor)
    return True, None


def anchors(node):
    x, y, w, h = [float(node[key]) for key in ("x", "y", "w", "h")]
    return [(x + w, y + h / 2), (x, y + h / 2), (x + w / 2, y), (x + w / 2, y + h)]


def verify_b(loaded, checks):
    spec, root, glyphs, page_text = loaded
    data = spec.get("data", {})
    data = data if isinstance(data, dict) else {}
    nodes = data.get("nodes", [])
    nodes = nodes if isinstance(nodes, list) else []
    nodes = [node for node in nodes if isinstance(node, dict)]
    labels = [node.get("label") for node in nodes]
    required = ["需求预测", "库存信息", "计算建议", "人工确认", "执行"]
    unique = len({node.get("id") for node in nodes}) == 5
    checks.add("B-SPEC-01", "process has exactly five uniquely identified required node labels",
               spec.get("kind") == "process" and Counter(labels) == Counter(required) and unique, {"labels": labels})
    by_label = {node.get("label"): node for node in nodes}
    by_id = {node.get("id"): node.get("label") for node in nodes}
    edges = data.get("edges", [])
    edges = edges if isinstance(edges, list) else []
    pairs = [(by_id.get(edge.get("from")), by_id.get(edge.get("to"))) for edge in edges if isinstance(edge, dict)]
    expected_pairs = [("计算建议", "人工确认"), ("人工确认", "执行")]
    checks.add("B-SPEC-02", "calculation precedes human confirmation, then execution without bypass",
               Counter(pairs) == Counter(expected_pairs), {"edges": pairs})
    serial = ("需求预测", "库存信息") in pairs or ("库存信息", "需求预测") in pairs
    checks.add("B-SPEC-03", "independent inputs are not made sequential", not serial)
    merges = data.get("merges", [])
    merges = merges if isinstance(merges, list) else []
    merge = merges[0] if len(merges) == 1 and isinstance(merges[0], dict) else {}
    from_ids = merge.get("from", [])
    source_labels = [by_id.get(value) for value in from_ids] if isinstance(from_ids, list) else []
    all_required = (len(merges) == 1 and merge.get("mode") == "all_required"
                    and Counter(source_labels) == Counter(["需求预测", "库存信息"])
                    and by_id.get(merge.get("to")) == "计算建议")
    checks.add("B-SPEC-04", "both inputs are jointly necessary for calculation (all_required)", all_required)
    boxes = [node for node in root.iter() if tag(node) == "rect" and "node" in node.get("class", "").split()]
    boxes_ok, glyphs_ok = len(boxes) == 5, True
    coordinates_ok = len(nodes) == 5
    for node in nodes:
        values = [node.get(key) for key in ("x", "y", "w", "h")]
        if not all(finite(value) for value in values):
            coordinates_ok = boxes_ok = glyphs_ok = False
            continue
        x, y, width, height = values
        coordinates_ok = coordinates_ok and 0 <= x < x + width <= 1000 and 0 <= y < y + height <= 560
        boxes_ok = boxes_ok and any(all(close(box.get(key), expected) for key, expected in
                                        [("x", x), ("y", y), ("width", width), ("height", height)]) for box in boxes)
        def inside_label(glyph):
            if text_of(glyph) != compact(node.get("label", "")) or not close(glyph.get("x"), x + width / 2):
                return False
            try:
                baseline = float(glyph.get("y"))
                baselines = []
                for span in glyph:
                    baseline += float(span.get("dy", 0))
                    baselines.append(baseline)
                return all(y <= value <= y + height for value in baselines or [baseline])
            except (TypeError, ValueError):
                return False
        glyphs_ok = glyphs_ok and any(inside_label(glyph) for glyph in glyphs)
    checks.add("B-CONTENT-01", "input node rectangles lie within the canvas", coordinates_ok)
    checks.add("B-CONTENT-02", "actual SVG node rectangles match structured input", boxes_ok)
    checks.add("B-CONTENT-03", "all required labels are drawn inside their actual node rectangles",
               glyphs_ok and all(label in "".join(text_of(node) for node in glyphs) for label in required))
    flows = [node for node in root.iter() if tag(node) == "path" and "flow-transfer" in node.get("class", "").split()]
    parsed, errors, marker_errors = [], [], []
    for flow in flows:
        try:
            points = path_points(flow)
            marker = flow.get("marker-end", "")
            match = re.fullmatch(r"url\(#([^\)]+)\)", marker)
            arrow = False
            if marker:
                arrow, reason = transfer_marker_contract(root, match.group(1)) if match else (False, "malformed marker reference")
                if not arrow:
                    marker_errors.append(reason)
            parsed.append((points[0], points[-1], arrow))
        except (ValueError, IndexError) as exc:
            errors.append(str(exc))
    checks.add("B-CONTENT-04", "actual relationship paths are five valid orthogonal lines", len(parsed) == 5 and not errors, errors)
    checks.add("B-CONTENT-09", "three arrow references use opaque forward markers under the finite renderer contract",
               sum(bool(flow.get("marker-end")) for flow in flows) == 3 and not marker_errors, marker_errors)
    def connects(source, target, arrow):
        return sum(point_equal(start, source) and point_equal(end, target) and has_arrow == arrow
                   for start, end, has_arrow in parsed)
    edge_ok, merge_ok, no_serial = False, False, False
    try:
        edge_ok = all(sum(connects(start, end, True) for start in anchors(by_label[source])
                           for end in anchors(by_label[target])) == 1 for source, target in expected_pairs)
        point = merge.get("point", [])
        merge_ok = all_required and isinstance(point, list) and len(point) == 2 and all(finite(v) for v in point)
        if merge_ok:
            merge_ok = (all(connects(anchors(by_label[label])[0], point, False) == 1 for label in ["需求预测", "库存信息"])
                        and connects(point, anchors(by_label["计算建议"])[1], True) == 1
                        and any(tag(node) == "circle" and close(node.get("cx"), point[0]) and close(node.get("cy"), point[1])
                                for node in root.iter()))
        no_serial = not any(point_equal(start, left) and point_equal(end, right)
                            for start, end, _ in parsed
                            for source, target in [("需求预测", "库存信息"), ("库存信息", "需求预测")]
                            for left in anchors(by_label[source]) for right in anchors(by_label[target]))
    except (KeyError, TypeError, ValueError):
        pass
    checks.add("B-CONTENT-05", "SVG arrows actually show calculation to confirmation to execution", edge_ok)
    checks.add("B-CONTENT-06", "two actual input branches meet before one arrow enters calculation", merge_ok)
    checks.add("B-CONTENT-07", "SVG has no serial line between independent inputs", no_serial)
    label = compact(merge.get("label", ""))
    visible_merge = [text_of(node) for node in glyphs if "merge-label" in node.get("class", "").split()]
    checks.add("B-CONTENT-08", "joint necessity is visibly labelled at the merge",
               bool(label) and label in visible_merge and bool(re.search(r"齐备|共同必要|缺一不可|全部|同时|都|双输入|AND", label, re.I)))
    benefits = re.findall(r"(?:收益|降本|节约|节省|提升|提高|降低|改善)[^。；，]{0,12}\d+(?:\.\d+)?(?:\s*(?:%|％|万元|亿元|元|倍))?|\d+(?:\.\d+)?\s*(?:%|％|万元|亿元|元|倍)[^。；，]{0,12}(?:收益|降本|节约|节省)", page_text)
    checks.add("B-CLAIM-02", "no invented numeric benefit is added to the process page", not benefits, benefits)


def verify(directory):
    directory = Path(directory).resolve()
    checks = Checks(directory)
    for case, function in [("a", verify_a), ("b", verify_b)]:
        loaded = load_case(directory, case, checks)
        if loaded is not None:
            try:
                function(loaded, checks)
            except (KeyError, TypeError, ValueError, IndexError) as exc:
                checks.add(case.upper() + "-INPUT-SHAPE", "malformed exercise data fails closed", False, str(exc))
    return checks.report()


def write_new(path, value):
    with path.open("x", encoding="utf-8") as stream:
        stream.write(value)


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def page_html(case, svg):
    heading = "成本增加来自哪里" if case == "a" else "输入齐备并经人工确认后执行"
    paragraph = ("基准100万元，运输增加18万元、分拣减少7万元、损耗增加9万元，结果为120万元，净增加20万元。"
                 if case == "a" else "需求预测与库存信息是两份独立且缺一不可的输入。两份齐备后计算建议，建议经人工确认后才能执行。")
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{heading}</title><style>*{{box-sizing:border-box}}body{{margin:0;background:#f4f5f8;color:#1a1f36;font:18px/1.65 'PingFang SC',sans-serif}}main{{max-width:1080px;margin:auto;padding:28px}}h1{{font-size:30px;line-height:1.3;color:#1e2878}}figure{{margin:22px 0;background:white}}svg{{display:block;width:100%;height:auto}}p{{overflow-wrap:anywhere}}.source{{font-size:15px;color:#4a5068}}</style></head>
<body><main><h1>{heading}</h1><p>{paragraph}</p><figure>{svg}</figure><p class="source">合成示例，仅说明数值与方案关系，不代表真实经营成果或业务采用。</p></main></body></html>\n'''


REPAIR_CASES = [
    ("disconnected_paths", "B-CONTENT-04"), ("title_as_marker", "B-CONTENT-09"),
    ("zero_width_bars", "A-CONTENT-05"), ("duplicate_html_resource_attribute", "B-HTML-02"),
    ("html_background_resource", "B-HTML-02"), ("namespaced_width_in_embed", "A-HTML-04"),
    ("missing_marker", "B-CONTENT-09"), ("rect_as_marker", "B-CONTENT-09"),
    ("empty_marker", "B-CONTENT-09"), ("nonpath_marker", "B-CONTENT-09"),
    ("transparent_arrow", "B-CONTENT-09"), ("transparent_arrow_style", "B-CONTENT-09"),
    ("reversed_arrow", "B-CONTENT-09"), ("reverse_marker_orientation", "B-CONTENT-09"),
]


def apply_repair_mutation(target, name):
    """Alter temporary copies of both SVG and HTML, avoiding mismatch-only tests."""
    if name in {"duplicate_html_resource_attribute", "html_background_resource"}:
        addition = ('<img src="https://example.invalid/x.png" src="#local">' if name.startswith("duplicate")
                    else '<table background="https://example.invalid/x.png"><tr><td>x</td></tr></table>')
        page = target / "b.html"
        page.write_text(page.read_text(encoding="utf-8").replace("</main>", addition + "</main>"), encoding="utf-8")
        return
    if name == "namespaced_width_in_embed":
        page = target / "a.html"
        original = page.read_text(encoding="utf-8")
        if 'width="78"' not in original:
            raise ValueError("namespaced-width test fixture no longer has the expected 78-unit bars")
        page.write_text(original.replace('width="78"', 'xmlns:fake="urn:fake" fake:width="78"'), encoding="utf-8")
        return
    case = "a" if name == "zero_width_bars" else "b"
    svg_path, page_path = target / f"{case}.svg", target / f"{case}.html"
    original = svg_path.read_text(encoding="utf-8")
    root = ET.fromstring(original)
    namespace = "{http://www.w3.org/2000/svg}"
    if name == "zero_width_bars":
        for node in root.iter():
            if (node.get("data-role") or "").startswith("waterfall-"):
                node.set("x", str(float(node.get("x")) + float(node.get("width")) / 2))
                node.set("width", "0")
    elif name in {"disconnected_paths", "title_as_marker", "missing_marker"}:
        title_id = next(node.get("id") for node in root if tag(node) == "title")
        for flow in root.iter():
            if tag(flow) != "path" or "flow-transfer" not in flow.get("class", "").split():
                continue
            if name == "disconnected_paths":
                points = path_points(flow)
                flow.set("d", f"M{points[0][0]} {points[0][1]} M{points[-1][0]} {points[-1][1]}")
            elif flow.get("marker-end"):
                flow.set("marker-end", f"url(#{title_id if name == 'title_as_marker' else 'missing-arrow'})")
    else:
        for marker in [node for node in root.iter() if tag(node) == "marker"]:
            if name == "rect_as_marker":
                marker.tag = namespace + "rect"
            elif name == "empty_marker":
                for child in list(marker):
                    marker.remove(child)
            elif name == "nonpath_marker":
                marker[0].tag = namespace + "circle"
            elif name == "transparent_arrow":
                marker[0].set("fill", "none")
            elif name == "transparent_arrow_style":
                marker[0].set("style", "opacity:0")
            elif name == "reversed_arrow":
                marker[0].set("d", "M10 0 L0 5 L10 10z")
            elif name == "reverse_marker_orientation":
                marker.set("orient", "180")
            else:
                raise ValueError("unknown repair mutation: " + name)
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    changed = ET.tostring(root, encoding="unicode")
    svg_path.write_text(changed, encoding="utf-8")
    page_path.write_text(page_path.read_text(encoding="utf-8").replace(original, changed), encoding="utf-8")


def mutation_tests(directory):
    cases = [("tampered_end", "A-SPEC-03"), ("deleted_confirmation", "B-SPEC-01"),
             ("missing_svg_embed", "A-HTML-03"), ("remote_resource", "B-HTML-02"),
             ("fake_synthetic_source", "A-SOURCE-01")] + REPAIR_CASES
    results = []
    with tempfile.TemporaryDirectory(prefix=".negative-tests-", dir=directory) as temporary:
        for name, expected_failure in cases:
            target = Path(temporary) / name
            target.mkdir()
            for filename in FILES:
                shutil.copyfile(directory / filename, target / filename)
            if name == "tampered_end":
                data = json.loads((target / "a.json").read_text(encoding="utf-8"))
                data["data"]["end"] = 121
                (target / "a.json").write_text(json_text(data), encoding="utf-8")
            elif name == "deleted_confirmation":
                data = json.loads((target / "b.json").read_text(encoding="utf-8"))
                data["data"]["nodes"] = [node for node in data["data"]["nodes"] if node["label"] != "人工确认"]
                (target / "b.json").write_text(json_text(data), encoding="utf-8")
            elif name == "missing_svg_embed":
                source = (target / "a.html").read_text(encoding="utf-8")
                (target / "a.html").write_text(re.sub(r"<svg\b[\s\S]*?</svg>", "", source), encoding="utf-8")
            elif name == "remote_resource":
                source = (target / "b.html").read_text(encoding="utf-8")
                (target / "b.html").write_text(source.replace("</main>", '<img src="https://example.invalid/remote.png"></main>'), encoding="utf-8")
            elif name == "fake_synthetic_source":
                old_label = FIXTURES["a"]["source"]["label"]
                for suffix in ("json", "svg", "html"):
                    path = target / ("a." + suffix)
                    path.write_text(path.read_text(encoding="utf-8").replace(old_label, "真实经营数据"), encoding="utf-8")
            else:
                apply_repair_mutation(target, name)
            report = verify(target)
            failure_ids = [item["id"] for item in report["failures"]]
            results.append({"mutation": name, "expected_failure": expected_failure,
                            "pass": not report["pass"] and expected_failure in failure_ids,
                            "actual_failed_checks": failure_ids, "failures": report["failures"]})
        # A valid local ID prefix may be introduced while embedding an SVG.
        target = Path(temporary) / "local_id_prefix"
        target.mkdir()
        for filename in FILES:
            shutil.copyfile(directory / filename, target / filename)
        for case in "ab":
            path = target / f"{case}.html"
            path.write_text(path.read_text(encoding="utf-8").replace(FIXTURES[case]["id"], "page-" + FIXTURES[case]["id"]), encoding="utf-8")
        report = verify(target)
        results.append({"mutation": "local_id_prefix", "expected": "pass", "pass": report["pass"], "failures": report["failures"]})
    return {"pass": all(item["pass"] for item in results), "test_count": len(results), "tests": results,
            "temporary_artifacts_removed": True}


def fixture(directory):
    directory = directory.resolve()
    if directory.exists() or directory.is_symlink():
        raise FileExistsError("fixture directory already exists; refusing to overwrite: " + str(directory))
    directory.mkdir(parents=True, exist_ok=False)
    calls = []
    for case, spec in FIXTURES.items():
        write_new(directory / f"{case}.json", json_text(spec))
        command = [sys.executable, "-B", str(ROOT / "render.py"), "--input", str(directory / f"{case}.json"),
                   "--output", str(directory / f"{case}.svg")]
        result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
        calls.append({"case": case, "command": command, "returncode": result.returncode,
                      "stdout": result.stdout, "stderr": result.stderr})
        if result.returncode:
            write_new(directory / "render-calls.json", json_text(calls))
            raise RuntimeError(f"real renderer failed for {case}: {result.stderr.strip()}")
        svg = (directory / f"{case}.svg").read_text(encoding="utf-8")
        write_new(directory / f"{case}.html", page_html(case, svg))
    write_new(directory / "render-calls.json", json_text(calls))
    report = verify(directory)
    self_tests = mutation_tests(directory)
    before = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in FILES}
    rejected = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--fixture", str(directory)],
                              capture_output=True, text=True, timeout=30, check=False)
    after = {name: hashlib.sha256((directory / name).read_bytes()).hexdigest() for name in FILES}
    try:
        rejection = json.loads(rejected.stdout)
    except ValueError:
        rejection = {}
    self_tests["tests"].append({"mutation": "existing_fixture_directory", "expected": "JSON error without any overwrite",
                                "pass": rejected.returncode == 2 and rejection.get("error_type") == "FileExistsError" and before == after,
                                "returncode": rejected.returncode, "unchanged_hashes": before == after})
    self_tests["test_count"] = len(self_tests["tests"])
    self_tests["pass"] = all(item["pass"] for item in self_tests["tests"])
    report["self_tests"] = self_tests
    report["pass"] = report["pass"] and self_tests["pass"]
    report["artifact_sha256"] = before
    write_new(directory / "mutation-evidence.json", json_text(self_tests))
    write_new(directory / "validation.json", json_text(report))
    return report


class JSONArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None):
    try:
        parser = JSONArgumentParser(description=__doc__)
        modes = parser.add_mutually_exclusive_group(required=True)
        modes.add_argument("--artifacts", type=Path, metavar="DIR")
        modes.add_argument("--fixture", type=Path, metavar="NEW_DIR")
        args = parser.parse_args(argv)
        report = fixture(args.fixture) if args.fixture else verify(args.artifacts)
        print(json_text(report), end="")
        return 0 if report["pass"] else 1
    except (OSError, ValueError, RuntimeError, subprocess.TimeoutExpired) as exc:
        print(json_text({"schema_version": 1, "pass": False, "error_type": type(exc).__name__,
                         "error": str(exc), "boundary": BOUNDARY}), end="")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
