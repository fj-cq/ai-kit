"""Small, explicit consulting-diagram cases built on the existing SVG primitives.

No business inference, general graph layout, network calls or file writes.
Install beside svg_diagram.py, or point VISUAL_LIB at that module's directory.
"""
from __future__ import annotations

import math
import os
from pathlib import Path
import re
import sys
import unicodedata

_lib = Path(os.environ.get("VISUAL_LIB", str(Path(__file__).resolve().parent.parent)))
sys.path.insert(0, str(_lib))
try:
    from svg_diagram import Diagram, esc
except ImportError as exc:
    raise ImportError("找不到 svg_diagram.py；将案例包放在 renderers 下或设置 VISUAL_LIB。") from exc

KINDS = {"evidence_table", "raci", "process", "swimlane", "issue_tree", "layers", "roadmap", "gantt"}
BLUE, LIGHT, INK, SOFT, GOLD = "#1E2878", "#E8EBF4", "#1A1F36", "#8B93C7", "#C9A227"


def _num(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("坐标与时段必须是有限数值")
    return float(value)


def _string(value, field, max_chars=100):
    if not isinstance(value, str) or not value.strip() or len(value) > max_chars:
        raise ValueError(f"{field} 必须是非空短文字（最多 {max_chars} 字符）")
    return value


def _ident(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-z][a-z0-9-]{0,47}", value):
        raise ValueError("id 只用小写英文字母、数字与连字符，且以字母开头")
    return value


def _items(value, name, low=1, high=6):
    if not isinstance(value, list) or not low <= len(value) <= high:
        raise ValueError(f"{name} 要求 {low}–{high} 项；更多内容请拆图")
    return value


def _width(text, size):
    return sum(size if unicodedata.east_asian_width(c) in "WF" else size * 0.57 for c in text)


def _wrap(value, width, size=20, max_lines=2):
    value = _string(value, "标签", 100)
    lines, current = [], ""
    for char in value:
        if char == "\n" or (current and _width(current + char, size) > width):
            lines.append(current)
            current = "" if char == "\n" else char
        else:
            current += char
    if current:
        lines.append(current)
    if len(lines) > max_lines:
        raise ValueError("标签超出案例的可读容量；请缩短内容或拆图，不能自动截断")
    return lines


def _rect(d, x, y, w, h, fill=LIGHT, stroke="none", role=None):
    attrs = f' data-role="{esc(role)}"' if role else ""
    d._parts.append(f'<rect x="{x:g}" y="{y:g}" width="{w:g}" height="{h:g}" '
                    f'fill="{fill}" stroke="{stroke}"{attrs}/>')


def _base(spec):
    ident = _ident(spec.get("id"))
    title = _string(spec.get("title"), "title", 34)
    takeaway = _string(spec.get("takeaway"), "takeaway", 49)
    question = _string(spec.get("question"), "question", 100)
    boundary = _string(spec.get("boundary"), "boundary", 180)
    unit = _string(spec.get("unit"), "unit", 18)
    source = spec.get("source")
    if not isinstance(source, dict) or source.get("kind") not in {"synthetic", "provided"}:
        raise ValueError("source 必须显式说明 synthetic 合成数据或 provided 有出处数据")
    source_label = _string(source.get("label"), "source.label", 70)
    source_status = "合成示例" if source["kind"] == "synthetic" else "用户提供，未核验"
    footer = f"{source_status} · {source_label}；单位：{unit}"
    if _width(footer, 15) > 925:
        raise ValueError("来源与单位超出页脚容量；请缩短来源名称并在正文保留完整出处")
    if _width(title, 28) > 925 or _width(takeaway, 18) > 925:
        raise ValueError("图题/副标题过长，需压缩或拆图")
    d = Diagram(ident, 1000, 560, title=title,
                desc=f"{question} {takeaway} {boundary} {footer}。")
    d.linetype("transfer", BLUE, width=2)
    d.linetype("dependency", SOFT, dash="5 4", width=1.7)
    _rect(d, 0, 0, 1000, 560, "#FFFFFF")
    d.text(36, 40, title, "headline", anchor="start")
    d.text(36, 74, takeaway, "caption", anchor="start")
    d.text(36, 535, footer, "footer", anchor="start")
    return d


def _finish(d):
    prefix = f"#{d.ident}-svg"
    css = d.css() + "\n" + "\n".join([
        '.headline{font-size:28px;font-weight:650}',
        '.caption{font-size:18px;fill:#4A5068}',
        '.footer{font-size:15px;fill:#4A5068}',
        '.node-text{font-size:20px;fill:#1A1F36}',
        '.label{font-size:20px;fill:#1A1F36}',
        '.label-small{font-size:17px;fill:#4A5068}',
        '.merge-label{font-size:15px;fill:#4A5068}',
        '.heading{font-size:21px;font-weight:650;fill:#1E2878}',
        '.table-heading{font-size:20px;font-weight:650;fill:#FFFFFF}',
        '.node{fill:#FFFFFF;stroke:#1E2878;stroke-width:1.5}',
        '.node-soft{fill:#E8EBF4;stroke:none}',
        '.node-outline{fill:#FFFFFF;stroke:#1E2878;stroke-width:2.5}',
    ])
    css = re.sub(r"(^|\n)([^{}\n]+)\{", lambda m: m.group(1) + prefix + " " + m.group(2) + "{", css)
    css = prefix + '{font-family:"PingFang SC","Microsoft YaHei",sans-serif;fill:#1A1F36}\n' + css
    return d.render().replace('<svg ', f'<svg id="{d.ident}-svg" ', 1).replace('</defs>', '</defs><style>' + css + '</style>', 1)


def _table(d, data, raci=False):
    columns = _items(data.get("columns"), "columns", 2, 5)
    rows = _items(data.get("rows"), "rows", 1, 5)
    if any(not isinstance(row, list) or len(row) != len(columns) for row in rows):
        raise ValueError("每行字段数必须与表头一致")
    if raci:
        allowed = {"", "R", "A", "C", "I", "A/R"}
        for row in rows:
            if any(cell not in allowed for cell in row[1:]):
                raise ValueError("RACI 只接受空白、R、A、C、I 或 A/R")
            if sum("A" in cell for cell in row[1:]) != 1:
                raise ValueError("每项工作必须且只能有一个最终负责 A")
    x0, y0, total_width = 36, 120, 928
    cw = total_width / len(columns)
    row_h = min(78, 310 / len(rows))
    _rect(d, x0, y0, total_width, 54, BLUE)
    for c, label in enumerate(columns):
        d.text(x0 + c * cw + 14, y0 + 34, _wrap(label, cw - 28, 20, 1), "table-heading", anchor="start")
    for r, row in enumerate(rows):
        y = y0 + 54 + r * row_h
        _rect(d, x0, y, total_width, row_h, "#F4F5F8" if r % 2 == 0 else "#FFFFFF")
        d._parts.append(f'<path d="M{x0} {y + row_h:g} H964" stroke="#E2E5ED" fill="none"/>')
        for c, label in enumerate(row):
            if label == "":
                continue
            lines = _wrap(label, cw - 28, 20, 2)
            d.text(x0 + c * cw + 14, y + row_h / 2 + 7 - (len(lines)-1)*12,
                   lines, "heading" if raci and c else "label", anchor="start", gap=24)


def _process(d, data):
    nodes = _items(data.get("nodes"), "nodes", 2, 8)
    boxes, rectangles = {}, []
    for node in nodes:
        ident = _ident(node.get("id"))
        if ident in boxes:
            raise ValueError("节点 id 重复")
        x, y, w, h = [_num(node.get(k)) for k in ("x", "y", "w", "h")]
        if x < 30 or x+w > 970 or y < 110 or y+h > 490 or w < 100 or h < 50:
            raise ValueError("节点越界或过小")
        for px, py, pw, ph in rectangles:
            if x < px+pw and x+w > px and y < py+ph and y+h > py:
                raise ValueError("节点框发生重叠")
        rectangles.append((x, y, w, h))
        boxes[ident] = d.box(x, y, w, h, _wrap(node.get("label"), w-28, 20, max(1, int(h/27)-1)), "node")
    edges = _items(data.get("edges", []), "edges", 0, 12)
    used = set()
    for edge in edges:
        a, b = edge.get("from"), edge.get("to")
        _string(edge.get("meaning"), "edge.meaning")
        if a not in boxes or b not in boxes or a == b or (a, b) in used:
            raise ValueError("边引用不存在、自环或重复")
        used.add((a, b))
        d.connect(boxes[a], boxes[b], "transfer")
    for merge in _items(data.get("merges", []), "merges", 0, 2):
        sources = _items(merge.get("from"), "merge.from", 2, 3)
        target = merge.get("to")
        if merge.get("mode") != "all_required":
            raise ValueError("本案例汇合只表示 all_required 共同必要，选择分支须另画")
        if target not in boxes or len(set(sources)) != len(sources) or any(s not in boxes or s == target for s in sources):
            raise ValueError("汇合关系引用错误")
        point = _items(merge.get("point"), "merge.point", 2, 2)
        px, py = map(_num, point)
        if not 30 <= px <= 970 or not 110 <= py <= 490:
            raise ValueError("汇合点越界")
        if any(boxes[s].right >= px for s in sources) or px >= boxes[target].left:
            raise ValueError("案例汇合要求输入在左、汇合点在中、输出在右")
        d.merge([boxes[s].anchor("right") for s in sources], (px, py), boxes[target].anchor("left"), "transfer")
        label_width = boxes[target].left - px - 10
        d.text((px + boxes[target].left)/2, py - 23,
               _wrap(merge.get("label"), label_width, 15, 1), "merge-label")


def _swimlane(d, data):
    lanes = _items(data.get("lanes"), "lanes", 2, 3)
    stages = _items(data.get("stages"), "stages", 2, 4)
    nodes = _items(data.get("nodes"), "nodes", 2, 8)
    colw = 780 / len(stages)
    rowh = 330 / len(lanes)
    for row, label in enumerate(lanes):
        y = 146 + rowh * row
        _rect(d, 36, y, 928, rowh, "#F4F5F8" if row % 2 == 0 else "#FFFFFF")
        d.text(100, y+rowh/2+7, _wrap(label, 112, 20, 2), "heading")
    for col, label in enumerate(stages):
        d.text(176 + colw*col + (colw-22)/2, 125, _wrap(label, colw-24, 20, 1), "heading")
    boxes, coordinates = {}, {}
    for node in nodes:
        ident = _ident(node.get("id"))
        row, col = node.get("lane"), node.get("step")
        if not isinstance(row, int) or not isinstance(col, int) or not 0 <= row < len(lanes) or not 0 <= col < len(stages):
            raise ValueError("泳道角色或步骤索引越界")
        if ident in boxes or (row, col) in coordinates.values():
            raise ValueError("泳道节点重复或占用相同位置")
        coordinates[ident] = (row, col)
        boxes[ident] = d.box(176 + colw*col, 146 + rowh*row + (rowh-64)/2, colw-22, 64,
                            _wrap(node.get("label"), colw-46, 20, 2), "node")
    for edge in _items(data.get("edges"), "edges", 1, 10):
        a, b = edge.get("from"), edge.get("to")
        _string(edge.get("meaning"), "edge.meaning")
        if a not in boxes or b not in boxes or coordinates[b][1] <= coordinates[a][1]:
            raise ValueError("本泳道案例只支持明确向后推进的步骤；复杂回流请另定坐标")
        d.connect(boxes[a], boxes[b], "transfer", from_side="right", to_side="left")


def _tree(d, data):
    branches = _items(data.get("branches"), "branches", 2, 3)
    children_by_branch = [_items(b.get("children"), "children", 1, 3) for b in branches]
    step = 360 / sum(len(children) for children in children_by_branch)
    child_height = min(46, step - 10)
    root = d.box(40, 258, 220, 80, _wrap(data.get("root"), 190), "node-outline")
    leaf_index = 0
    for branch, children in zip(branches, children_by_branch):
        cy = 118 + step * (leaf_index + len(children)/2)
        box = d.box(390, cy-32, 200, 64, _wrap(branch.get("label"), 170), "node")
        d.path(f"M{root.right:g} {root.cy:g} H325 V{box.cy:g} H{box.left:g}", "transfer", arrow=False)
        for j, label in enumerate(children):
            subcy = 118 + step * (leaf_index+j+.5)
            child = d.box(710, subcy-child_height/2, 250, child_height, _wrap(label, 220, 20, 1), "node-soft")
            d.path(f"M{box.right:g} {box.cy:g} H650 V{child.cy:g} H{child.left:g}", "transfer", arrow=False)
        leaf_index += len(children)


def _layers(d, data):
    layers = _items(data.get("layers"), "layers", 2, 4)
    rowh = 360 / len(layers)
    for i, layer in enumerate(layers):
        y = 115 + i * rowh
        _rect(d, 36, y, 928, rowh-12, "#F4F5F8" if i % 2 else LIGHT)
        d.text(118, y+(rowh-12)/2+7, _wrap(layer.get("label"), 130, 21, 2), "heading")
        items = _items(layer.get("items"), "layer.items", 1, 3)
        colw = 730 / len(items)
        for j, label in enumerate(items):
            d.box(215+j*colw, y+10, colw-18, rowh-32, _wrap(label, colw-42, 20, 2), "node")


def _roadmap(d, data):
    phases = _items(data.get("phases"), "phases", 2, 3)
    colw = 950 / len(phases)
    last = None
    for i, phase in enumerate(phases):
        x, w = 36 + colw * i, colw-24
        d.text(x+w/2, 125, _wrap(phase.get("time"), w-20, 21, 1), "heading")
        name = d.box(x, 145, w, 68, _wrap(phase.get("name"), w-24, 20, 2), "node-outline")
        if last is not None:
            d.connect(last, name, "transfer")
        last = name
        outputs = _items(phase.get("outputs"), "phase.outputs", 1, 3)
        _rect(d, x, 238, w, 112, LIGHT)
        for j, label in enumerate(outputs):
            d.text(x+w/2, 269+j*28, _wrap(label, w-28, 20, 1), "label")
        gate_label = "本阶段的验收条件" if i == len(phases)-1 else "进入下一阶段的条件"
        d.text(x+w/2, 390, gate_label, "label-small")
        d.box(x, 404, w, 60, _wrap(phase.get("gate"), w-28, 20, 1), "node")


def _gantt(d, data):
    periods = _items(data.get("periods"), "periods", 2, 8)
    tasks = _items(data.get("tasks"), "tasks", 1, 5)
    cw, rh = 696 / len(periods), 310 / len(tasks)
    taskmap = {}
    for i, task in enumerate(tasks):
        ident = _ident(task.get("id"))
        start, end = task.get("start"), task.get("end")
        if ident in taskmap or not isinstance(start, int) or not isinstance(end, int) or not 0 <= start < end <= len(periods):
            raise ValueError("任务 id 重复或时段范围错误；end 为不含该时段的右边界")
        taskmap[ident] = (i, task)
    for ident, (i, task) in taskmap.items():
        for dep in _items(task.get("depends_on", []), "depends_on", 0, 4):
            if dep not in taskmap or taskmap[dep][0] >= i or taskmap[dep][1]["end"] > task["start"]:
                raise ValueError("前置任务不存在、顺序错误或未完成就启动后续任务")
    for col, label in enumerate(periods):
        d.text(240+cw*(col+.5), 129, _wrap(label, cw-8, 18, 1), "label-small")
        d._parts.append(f'<path d="M{240+cw*col:g} 142 V478" stroke="#E2E5ED" fill="none"/>')
    for i, task in enumerate(tasks):
        y = 157 + rh * i
        d.text(220, y+19, _wrap(task["label"], 180, 20, 1), "label", anchor="end")
        x, w = 240+cw*task["start"], cw*(task["end"]-task["start"])
        _rect(d, x, y, w, 24, BLUE if i % 2 == 0 else SOFT, role="task")
        for dep in task.get("depends_on", []):
            previous_i, previous = taskmap[dep]
            startx = 240+cw*previous["end"]-12
            starty = 157+rh*previous_i+24
            d.path(f"M{startx:g} {starty:g} V{y+12:g} H{x:g}", "dependency")


def render(spec):
    """Return a self-contained SVG, or reject input exceeding case contracts."""
    if not isinstance(spec, dict) or spec.get("kind") not in KINDS or not isinstance(spec.get("data"), dict):
        raise ValueError("未知关系图类型或 data 不是对象")
    d = _base(spec)
    kind, data = spec["kind"], spec["data"]
    if kind in {"evidence_table", "raci"}:
        _table(d, data, raci=kind == "raci")
    else:
        {"process": _process, "swimlane": _swimlane, "issue_tree": _tree,
         "layers": _layers, "roadmap": _roadmap, "gantt": _gantt}[kind](d, data)
    return _finish(d)
