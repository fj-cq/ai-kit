"""Small, deterministic, standard-library SVG charts with explicit provenance.

Public API: KINDS and render(spec) -> complete SVG string. No IO, fonts,
network, animation, global CSS, chart library, or random layout is used.
This is deliberately not a general charting library. Numerical values are
bounded to +/- 1e12; text and row limits reject rather than silently truncate.
All text is single-line. Actual font metrics require a separate browser check.
"""
import html
import json
import math
import re

KINDS = {"bar", "stacked_bar", "line", "slope", "waterfall", "bullet",
         "scatter", "heatmap", "harvey", "sankey", "mekko"}
WHITE, INK, BLUE = "#FFFFFF", "#1A1F36", "#1E2878"
SECONDARY, PALE, GOLD = "#8B93C7", "#E8EBF4", "#C9A227"
COLORS = (BLUE, SECONDARY, GOLD, PALE)
SOURCE = "合成演示数据，非企业实绩"


def _s(value, maximum=10, name="label"):
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ValueError(f"{name}: expected nonempty text of at most {maximum} characters")
    if any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF or ord(c) in (0xFFFE, 0xFFFF) for c in value):
        raise ValueError(f"{name}: control characters and invalid XML characters are not supported")
    return value


def _num(value, nonnegative=True):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("expected a number, not text or boolean")
    if not math.isfinite(value) or abs(value) > 1e12 or (nonnegative and value < 0):
        raise ValueError("number must be finite, within +/- 1e12, and within the chart domain")
    return float(value)


def _ls(value, maximum, minimum=1, name="items"):
    if not isinstance(value, list) or not minimum <= len(value) <= maximum:
        raise ValueError(f"{name}: expected {minimum}..{maximum} items")
    return value


def _same(actual, expected, label):
    # A fixed absolute tolerance would incorrectly equate tiny totals to zero.
    if not math.isclose(actual, expected, rel_tol=1e-14, abs_tol=0):
        raise ValueError(f"{label}: {actual:g} != {expected:g}")


def _f(value):
    if not math.isfinite(value):
        raise ValueError("non-finite derived geometry")
    # repr keeps floats round-trippable, including small values in scientific
    # notation. Fixed decimal precision can turn a valid value or width into 0.
    return str(int(value)) if value == int(value) else repr(value)


def _guard(value, depth=0):
    if depth > 10:
        raise ValueError("spec is too deeply nested")
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError("non-finite input")
    if isinstance(value, str):
        if len(value) > 256 or any(ord(c) < 32 or 0xD800 <= ord(c) <= 0xDFFF or ord(c) in (0xFFFE, 0xFFFF) for c in value):
            raise ValueError("input text is too long or contains invalid XML characters")
    if isinstance(value, dict):
        for key, item in value.items():
            _guard(key, depth + 1)
            _guard(item, depth + 1)
    elif isinstance(value, list):
        if len(value) > 40:
            raise ValueError("oversized input list")
        for item in value:
            _guard(item, depth + 1)


class _SVG:
    def __init__(self, spec):
        self.spec, self.parts = spec, []

    def element(self, tag, text=None, **attrs):
        pairs = []
        for key, value in attrs.items():
            if value is None:
                continue
            key = key.replace("_", "-")
            value = _f(value) if isinstance(value, (int, float)) else str(value)
            pairs.append(f'{key}="{html.escape(value, quote=True)}"')
        opening = "<" + tag + (" " + " ".join(pairs) if pairs else "")
        self.parts.append(opening + ("/>" if text is None else ">" + html.escape(str(text)) + "</" + tag + ">"))

    def text(self, x, y, value, size=18, color=INK, anchor="start", **attrs):
        self.element("text", value, x=x, y=y, font_size=size, fill=color, text_anchor=anchor, **attrs)

    def rect(self, x, y, w, h, fill=BLUE, **attrs):
        self.element("rect", x=x, y=y, width=max(0, w), height=max(0, h), fill=fill, **attrs)

    def line(self, x1, y1, x2, y2, color=SECONDARY, **attrs):
        self.element("line", x1=x1, y1=y1, x2=x2, y2=y2, stroke=color, **attrs)

    def circle(self, x, y, radius, fill=BLUE, **attrs):
        self.element("circle", cx=x, cy=y, r=radius, fill=fill, **attrs)

    def legend(self, labels, y=122, x=160, width=750):
        for i, label in enumerate(labels):
            px = x + i * width / len(labels)
            self.rect(px, y - 13, 16, 16, COLORS[i])
            self.text(px + 24, y, label, 18)

    def y_axis(self, maximum, left=120, right=900, top=155, bottom=425):
        self.line(left, top, left, bottom, BLUE)
        self.line(left, bottom, right, bottom, BLUE)
        for value in (0, maximum / 2, maximum):
            y = bottom - value / maximum * (bottom - top)
            self.line(left, y, right, y, PALE)
            self.text(left - 12, y + 5, _f(value), 15, anchor="end")

    def finish(self):
        s = self.spec
        identifier = s["id"]
        source = ("合成示例；来源：" if s["source"]["kind"] == "synthetic" else "用户提供来源（未核验）：") + s["source"]["label"]
        description = s["question"] + " " + s["boundary"] + " " + source + " 数据：" + json.dumps(s["data"], ensure_ascii=False)
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1000 560" '
                f'id="{identifier}-svg" role="img" aria-labelledby="{identifier}-title {identifier}-desc" '
                'style="font-family:Noto Sans CJK SC,PingFang SC,Microsoft YaHei,sans-serif;background:#FFFFFF">'
                f'<title id="{identifier}-title">{html.escape(s["title"])}</title>'
                f'<desc id="{identifier}-desc">{html.escape(description)}</desc>'
                '<rect x="0" y="0" width="1000" height="560" fill="#FFFFFF"/>')
        body = "".join(self.parts)
        self.parts = []
        self.text(36, 40, s["title"], 28, font_weight="700")
        self.text(36, 74, s["takeaway"], 18)
        self.text(36, 105, "单位：" + s["unit"], 15)
        self.text(36, 506, s["boundary"], 15)
        self.text(36, 535, source, 15)
        return head + "".join(self.parts) + body + "</svg>"


def _bar(svg, data):
    items = _ls(data["items"], 8)
    values = [_num(item["value"]) for item in items]
    labels = [_s(item["label"], 8) for item in items]
    maximum = max(values) or 1
    for i, (label, value) in enumerate(zip(labels, values)):
        y = 145 + i * 300 / len(items)
        svg.text(192, y + 20, label, 19, anchor="end")
        svg.rect(210, y, value / maximum * 640, 26, data_role="bar", data_index=i, data_value=value)
        svg.text(220 + value / maximum * 640, y + 20, _f(value), 18)
    svg.line(210, 135, 210, 447, BLUE)
    for value in (0, maximum / 2, maximum):
        svg.text(210 + value / maximum * 640, 470, _f(value), 15, anchor="middle")


def _stacked(svg, data):
    if data.get("mode") != "percent" or svg.spec["unit"] != "%":
        raise ValueError("stacked_bar supports only percent mode with unit '%' ")
    series = [_s(label, 8) for label in _ls(data["series"], 3)]
    rows = _ls(data["rows"], 8)
    svg.legend(series, x=210, width=640)
    for i, row in enumerate(rows):
        label = _s(row["label"], 8)
        values = [_num(value) for value in _ls(row["values"], len(series), len(series))]
        _same(sum(values), 100, "percentage row must total 100")
        y, x = 155 + i * 280 / len(rows), 210
        svg.text(192, y + 18, label, 19, anchor="end")
        for j, value in enumerate(values):
            width = value * 6.4
            svg.rect(x, y, width, 25, COLORS[j], data_role="stack", data_row=i, data_series=j, data_value=value)
            if width >= 42:
                svg.text(x + width / 2, y + 18, _f(value) + "%", 15, WHITE if j < 2 else INK, "middle")
            x += width
    for value in (0, 25, 50, 75, 100):
        svg.text(210 + value * 6.4, 471, str(value) + "%", 15, anchor="middle")


def _line_chart(svg, data):
    labels = [_s(label, 6) for label in _ls(data["labels"], 8, 2)]
    series = _ls(data["series"], 3)
    names = [_s(item["label"], 8) for item in series]
    values = [[_num(value) for value in _ls(item["values"], len(labels), len(labels))] for item in series]
    maximum = max(max(row) for row in values) or 1
    svg.legend(names, x=140, width=720)
    svg.y_axis(maximum)
    for i, row in enumerate(values):
        points = [(120 + j * 780 / (len(labels) - 1), 425 - value / maximum * 270) for j, value in enumerate(row)]
        svg.element("polyline", points=" ".join(_f(x) + "," + _f(y) for x, y in points),
                    fill="none", stroke=COLORS[i], stroke_width=3, data_role="line", data_series=i)
        for j, (x, y) in enumerate(points):
            svg.circle(x, y, 4, COLORS[i], data_role="line-point", data_series=i, data_index=j)
    for i, label in enumerate(labels):
        svg.text(120 + i * 780 / (len(labels) - 1), 468, label, 18, anchor="middle")


def _spread(values, top=165, bottom=445, gap=25):
    ordered = sorted(enumerate(values), key=lambda pair: (pair[1], pair[0]))
    adjusted = []
    for _, y in ordered:
        adjusted.append(max(top, y, adjusted[-1] + gap if adjusted else top))
    if adjusted[-1] > bottom:
        adjusted[-1] = bottom
        for i in range(len(adjusted) - 2, -1, -1):
            adjusted[i] = min(adjusted[i], adjusted[i + 1] - gap)
    return {index: value for (index, _), value in zip(ordered, adjusted)}


def _slope(svg, data):
    periods = [_s(p, 10) for p in _ls(data["periods"], 2, 2)]
    items = _ls(data["items"], 8)
    labels = [_s(item["label"], 8) for item in items]
    starts = [_num(item["start"]) for item in items]
    ends = [_num(item["end"]) for item in items]
    maximum = max(starts + ends) or 1
    y1 = [440 - v / maximum * 260 for v in starts]
    y2 = [440 - v / maximum * 260 for v in ends]
    left_labels, right_labels = _spread(y1), _spread(y2)
    svg.text(330, 135, periods[0], 20, anchor="middle")
    svg.text(670, 135, periods[1], 20, anchor="middle")
    svg.line(330, 165, 330, 447, PALE)
    svg.line(670, 165, 670, 447, PALE)
    for i, label in enumerate(labels):
        color = COLORS[i % 3]
        svg.line(330, y1[i], 670, y2[i], color, stroke_width=3, data_role="slope", data_index=i)
        svg.circle(330, y1[i], 5, color)
        svg.circle(670, y2[i], 5, color)
        svg.line(303, left_labels[i], 323, y1[i], color)
        svg.line(677, y2[i], 697, right_labels[i], color)
        svg.text(298, left_labels[i] + 6, label + " " + _f(starts[i]), 18, anchor="end")
        svg.text(702, right_labels[i] + 6, label + " " + _f(ends[i]), 18)


def _waterfall(svg, data):
    start, end = _num(data["start"], False), _num(data["end"], False)
    steps = _ls(data["steps"], 6)
    labels = [_s(step["label"], 5) for step in steps]
    changes = [_num(step["delta"], False) for step in steps]
    totals = [start]
    for value in changes:
        totals.append(totals[-1] + value)
    _same(totals[-1], end, "waterfall final total")
    low, high = min([0] + totals), max([0] + totals)
    if high == low:
        high = low + 1
    y = lambda value: 435 - (value - low) / (high - low) * 265
    count = len(steps) + 2
    spacing, width = 840 / count, min(78, 840 / count - 24)
    svg.line(90, y(0), 950, y(0), SECONDARY)
    for i, label in enumerate(["期初"] + labels + ["期末"]):
        x = 90 + spacing * i + (spacing - width) / 2
        if i == 0:
            before, after, role = 0, start, "waterfall-start"
        elif i == count - 1:
            before, after, role = 0, end, "waterfall-total"
        else:
            before, after, role = totals[i - 1], totals[i], "waterfall-delta"
        value = after - before
        fill = BLUE if role != "waterfall-delta" or value >= 0 else SECONDARY
        svg.rect(x, min(y(before), y(after)), width, abs(y(after) - y(before)), fill,
                 data_role=role, data_start=before, data_end=after, data_value=value)
        value_label = ("+" if value >= 0 else "") + _f(value) if role == "waterfall-delta" else _f(after)
        svg.text(x + width / 2, min(y(before), y(after)) - 11, value_label, 18, anchor="middle")
        svg.text(x + width / 2, 468, label, 18, anchor="middle")
        if i < count - 1:
            level = start if i == 0 else totals[i]
            svg.line(x + width, y(level), x + spacing, y(level), SECONDARY, stroke_dasharray="4 3")


def _bullet(svg, data):
    label = _s(data["label"], 16)
    actual, target, maximum = [_num(data[key]) for key in ("actual", "target", "max")]
    ranges = [_num(v) for v in _ls(data["ranges"], 3)]
    if maximum <= 0 or actual > maximum or target > maximum or ranges != sorted(set(ranges)) or ranges[0] <= 0:
        raise ValueError("bullet values and ordered ranges must share a positive max domain")
    _same(ranges[-1], maximum, "bullet final range")
    svg.text(130, 150, label, 21)
    previous = 0
    for i, value in enumerate(ranges):
        svg.rect(130 + previous / maximum * 770, 220, (value - previous) / maximum * 770, 82,
                 (PALE, SECONDARY, GOLD)[i], fill_opacity=.45, data_role="bullet-range")
        previous = value
    svg.rect(130, 243, actual / maximum * 770, 36, BLUE, data_role="bullet-actual", data_value=actual)
    target_x = 130 + target / maximum * 770
    svg.line(target_x, 207, target_x, 316, GOLD, stroke_width=5, data_role="bullet-target", data_value=target)
    svg.text(target_x, 192, "目标 " + _f(target), 18, anchor="middle")
    svg.text(130, 382, "实际 " + _f(actual), 21, BLUE)
    for value in [0] + ranges:
        svg.text(130 + value / maximum * 770, 338, _f(value), 15, anchor="middle")
    svg.text(130, 418, "参考带阈值：" + " / ".join(_f(v) for v in ranges), 18)


def _scatter(svg, data):
    for key in ("x_label", "y_label", "size_label"):
        _s(data[key], 8, key)
    for key in ("x_unit", "y_unit", "size_unit"):
        _s(data[key], 8, key)
    points = _ls(data["points"], 7)
    labels = [_s(p["label"], 6) for p in points]
    xs, ys, sizes = [[_num(p[key]) for p in points] for key in ("x", "y", "size")]
    xmax, ymax, smax = max(xs) or 1, max(ys) or 1, max(sizes) or 1
    svg.y_axis(ymax, left=140, right=860, top=160, bottom=430)
    svg.text(140, 132, data["y_label"] + "（" + data["y_unit"] + "）", 18)
    svg.text(500, 475, data["x_label"] + "（" + data["x_unit"] + "）", 18, anchor="middle")
    svg.text(560, 132, "气泡面积＝" + data["size_label"] + "（" + data["size_unit"] + "）", 18)
    for value in (0, xmax / 2, xmax):
        svg.text(140 + value / xmax * 720, 445, _f(value), 15, anchor="middle")
    for i, label in enumerate(labels):
        x, y, r = 140 + xs[i] / xmax * 720, 430 - ys[i] / ymax * 270, math.sqrt(sizes[i] / smax) * 34
        svg.circle(x, y, r, COLORS[i % 3], fill_opacity=.65, stroke=BLUE, data_role="bubble", data_index=i, data_size=sizes[i])
        left = x > 710
        svg.text(x - r - 8 if left else x + r + 8, y + 6, label, 18, anchor="end" if left else "start")


def _heatmap(svg, data):
    rows = [_s(label, 8) for label in _ls(data["rows"], 6)]
    columns = [_s(label, 6) for label in _ls(data["columns"], 5)]
    matrix = _ls(data["values"], len(rows), len(rows))
    values = []
    for row in matrix:
        values.append([None if value is None else _num(value) for value in _ls(row, len(columns), len(columns))])
    maximum = max([value for row in values for value in row if value is not None] or [1]) or 1
    width, height = 720 / len(columns), 258 / len(rows)
    for j, label in enumerate(columns):
        svg.text(200 + (j + .5) * width, 144, label, 18, anchor="middle")
    for i, label in enumerate(rows):
        svg.text(185, 164 + (i + .5) * height + 6, label, 18, anchor="end")
        for j, value in enumerate(values[i]):
            level = 0 if value is None else min(2, int(value / maximum * 3))
            fill = WHITE if value is None else (PALE, SECONDARY, BLUE)[level]
            svg.rect(200 + j * width, 164 + i * height, width, height, fill,
                     stroke=SECONDARY if value is None else WHITE, stroke_width=2,
                     stroke_dasharray="5 3" if value is None else None,
                     data_role="heat-cell", data_row=i, data_column=j,
                     data_state="unknown" if value is None else "known")
            svg.text(200 + (j + .5) * width, 164 + (i + .5) * height + 6,
                     "未知" if value is None else _f(value), 18, WHITE if value is not None and level == 2 else INK, "middle")
    svg.text(200, 461, "格内为原值；颜色按本图范围分为低、中、高；未知单列。", 16)


def _harvey(svg, data):
    items = _ls(data["items"], 5)
    legend = [_s(label, 6) for label in _ls(data["legend"], 5, 5)]
    for i, item in enumerate(items):
        label, rating = _s(item["label"], 8), _num(item["rating"])
        if rating != int(rating) or not 0 <= rating <= 4:
            raise ValueError("Harvey rating must be an integer 0..4")
        x, y, radius = 50 + (i + .5) * 900 / len(items), 245, 42
        svg.circle(x, y, radius, WHITE, stroke=BLUE, stroke_width=2, data_role="harvey-base", data_rating=rating)
        if rating == 4:
            svg.circle(x, y, radius, BLUE, data_role="harvey-fill", data_rating=rating)
        elif rating:
            angle = -math.pi / 2 + rating / 4 * math.tau
            ex, ey = x + radius * math.cos(angle), y + radius * math.sin(angle)
            path = f"M {_f(x)} {_f(y)} L {_f(x)} {_f(y-radius)} A {radius} {radius} 0 {int(rating > 2)} 1 {_f(ex)} {_f(ey)} Z"
            svg.element("path", d=path, fill=BLUE, data_role="harvey-fill", data_rating=rating)
        svg.text(x, 330, label, 19, anchor="middle")
        svg.text(x, 365, str(int(rating)) + "/4", 18, anchor="middle")
    for i, label in enumerate(legend):
        svg.text(50 + i * 180, 442, str(i) + "＝" + label, 16, data_role="harvey-legend")


def _sankey(svg, data):
    sources, targets = _ls(data["sources"], 3), _ls(data["targets"], 3)
    source_labels, target_labels = [[_s(node["label"], 8) for node in nodes] for nodes in (sources, targets)]
    st, tt = [[_num(node["total"]) for node in nodes] for nodes in (sources, targets)]
    if min(st + tt) <= 0:
        raise ValueError("two-column Sankey nodes must have positive totals")
    matrix = [[_num(v) for v in _ls(row, len(targets), len(targets))]
              for row in _ls(data["flows"], len(sources), len(sources))]
    for i, total in enumerate(st):
        _same(sum(matrix[i]), total, "Sankey source conservation")
    for j, total in enumerate(tt):
        _same(sum(row[j] for row in matrix), total, "Sankey target conservation")
    _same(sum(st), sum(tt), "Sankey grand total")
    scale, gap = (230 - 20 * (max(len(st), len(tt)) - 1)) / sum(st), 20

    def tops(totals):
        y = 157 + (230 - (sum(totals) * scale + gap * (len(totals) - 1))) / 2
        result = []
        for value in totals:
            result.append(y)
            y += value * scale + gap
        return result

    sy, ty = tops(st), tops(tt)
    so, to = sy[:], ty[:]
    entries = []
    for i, row in enumerate(matrix):
        for j, value in enumerate(row):
            if value == 0:
                continue
            y0, z0, height = so[i], to[j], value * scale
            path = (f"M 260 {_f(y0)} C 420 {_f(y0)} 580 {_f(z0)} 740 {_f(z0)} "
                    f"L 740 {_f(z0+height)} C 580 {_f(z0+height)} 420 {_f(y0+height)} 260 {_f(y0+height)} Z")
            svg.element("path", d=path, fill=COLORS[i], fill_opacity=.55, data_role="sankey-flow",
                        data_source=i, data_target=j, data_value=value)
            so[i] += height
            to[j] += height
            entries.append(source_labels[i] + "→" + target_labels[j] + "：" + _f(value))
    for nodes, labels, totals, offsets, x, role in [(sources, source_labels, st, sy, 240, "source"),
                                                   (targets, target_labels, tt, ty, 740, "target")]:
        for i, (label, total, y) in enumerate(zip(labels, totals, offsets)):
            svg.rect(x, y, 20, total * scale, BLUE, data_role="sankey-" + role, data_index=i)
            label_x, anchor = (225, "end") if role == "source" else (778, "start")
            svg.text(label_x, y + total * scale / 2 - 8, label, 18, anchor=anchor)
            svg.text(label_x, y + total * scale / 2 + 24, _f(total), 15, anchor=anchor)
    for i, entry in enumerate(entries):
        svg.text(60 + i % 3 * 307, 424 + i // 3 * 23, entry, 15)


def _mekko(svg, data):
    series = [_s(label, 8) for label in _ls(data["series"], 4)]
    groups = _ls(data["groups"], 5)
    totals, values, labels = [], [], []
    for group in groups:
        label, total = _s(group["label"], 8), _num(group["total"])
        row = [_num(v) for v in _ls(group["values"], len(series), len(series))]
        if total <= 0:
            raise ValueError("Mekko groups must have positive totals")
        _same(sum(row), total, "Mekko group total")
        labels.append(label)
        totals.append(total)
        values.append(row)
    grand_total, x = sum(totals), 100
    for i, (label, total, row) in enumerate(zip(labels, totals, values)):
        width, y = total / grand_total * 840, 420
        label_x = 100 + (i + .5) * 840 / len(groups)
        svg.text(label_x, 131, label, 18, anchor="middle")
        svg.text(label_x, 153, _f(total), 15, anchor="middle")
        svg.line(label_x, 158, x + width / 2, 168, SECONDARY)
        for j, value in enumerate(row):
            height = value / total * 250
            y -= height
            svg.rect(x, y, width, height, COLORS[j], stroke=WHITE, stroke_width=2,
                     data_role="mekko-cell", data_group=i, data_series=j, data_value=value)
            if height >= 24 and width >= 60:
                svg.text(x + width / 2, y + height / 2 + 6, _f(value / total * 100) + "%", 16,
                         WHITE if j < 2 else INK, "middle")
        x += width
    for percent, y in [(100, 175), (50, 300), (0, 425)]:
        svg.text(88, y, str(percent) + "%", 15, anchor="end")
    svg.legend(series, y=466, x=100, width=840)


_RENDERERS = {"bar": _bar, "stacked_bar": _stacked, "line": _line_chart, "slope": _slope,
              "waterfall": _waterfall, "bullet": _bullet, "scatter": _scatter, "heatmap": _heatmap,
              "harvey": _harvey, "sankey": _sankey, "mekko": _mekko}


def render(spec: dict) -> str:
    """Validate a small spec and return a self-contained SVG.

    Raises ValueError for unsupported kinds, malformed shape/size, long text,
    non-finite or out-of-domain numbers, and inconsistent totals. Does not
    mutate the input. Labels omitted inside tiny cells remain in SVG <desc>.
    Source kind is synthetic or provided; provided provenance is not verified.
    Source labels are nonempty single-line text, at most 48 characters.
    """
    try:
        if not isinstance(spec, dict):
            raise ValueError("spec must be a dictionary")
        _guard(spec)
        identifier = _s(spec["id"], 64, "id")
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", identifier, flags=re.ASCII):
            raise ValueError("id must be ASCII and safe for an SVG namespace")
        if spec["kind"] not in KINDS:
            raise ValueError("unsupported chart kind")
        for key, maximum in [("title", 32), ("takeaway", 48), ("question", 70), ("unit", 32), ("boundary", 58)]:
            _s(spec[key], maximum, key)
        source = spec["source"]
        if not isinstance(source, dict) or source.get("kind") not in {"synthetic", "provided"}:
            raise ValueError("source kind must be synthetic or provided; provided does not mean verified")
        _s(source.get("label"), 48, "source.label")
        if not isinstance(spec["data"], dict):
            raise ValueError("data must be an object")
        svg = _SVG(spec)
        _RENDERERS[spec["kind"]](svg, spec["data"])
        return svg.finish()
    except (KeyError, TypeError, IndexError, OverflowError) as error:
        raise ValueError("malformed chart specification: " + str(error)) from error
