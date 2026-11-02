"""坐标契约式 SVG 流程图原语。

坐标与连线说明见 ../README.md；完整使用方法保留于本模块文档。

核心约定：
1. 框和线在同一个 SVG 坐标系里，坐标手算写死，不用自动布局。
2. 折线只走直角，d 里只出现 M / H / V。
3. 多条线汇合时显式画圆点，箭头只加在汇合之后那一段。
4. 线型即语义：先定线型词典，一种线型只有一个意思。
5. 规整的行列用公式生成，不手写每一行。

用法::

    from svg_diagram import Diagram
    d = Diagram("chain", 1005, 665, title="...", desc="...")
    d.linetype("material", color="#87694b")
    a = d.box(20, 200, 136, 76, ["自有采购", "生豆供货"], "material-node")
    b = d.box(235, 200, 151, 76, ["生豆验收", "先验原料"], "material-node")
    d.connect(a, b, "material")
    print(d.render())

自检：python3 svg_diagram.py --self-test
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


@dataclass(frozen=True)
class Box:
    """一个矩形节点。四条边的坐标由 x/y/w/h 推出，是所有连线的锚点。"""
    x: float
    y: float
    w: float
    h: float

    @property
    def left(self) -> float: return self.x
    @property
    def right(self) -> float: return self.x + self.w
    @property
    def top(self) -> float: return self.y
    @property
    def bottom(self) -> float: return self.y + self.h
    @property
    def cx(self) -> float: return self.x + self.w / 2
    @property
    def cy(self) -> float: return self.y + self.h / 2

    def anchor(self, side: str) -> tuple[float, float]:
        """取某条边的中点。side 用 left/right/top/bottom。"""
        if side == "right": return (self.right, self.cy)
        if side == "left": return (self.left, self.cy)
        if side == "top": return (self.cx, self.top)
        if side == "bottom": return (self.cx, self.bottom)
        raise ValueError("side 只能是 left/right/top/bottom，收到 " + repr(side))


@dataclass
class LineType:
    name: str
    color: str
    dash: str | None = None
    width: float = 1.8


@dataclass
class Diagram:
    ident: str
    width: float
    height: float
    title: str = ""
    desc: str = ""
    _parts: list[str] = field(default_factory=list)
    _types: dict[str, LineType] = field(default_factory=dict)

    # ---------- 线型词典 ----------
    def linetype(self, name: str, color: str, dash: str | None = None, width: float = 1.8) -> "Diagram":
        """定义一种线型。一种线型只能有一个意思——不够用时重新切分图，不要加第三种。"""
        self._types[name] = LineType(name, color, dash, width)
        return self

    def _t(self, name: str) -> LineType:
        if name not in self._types:
            raise KeyError(f"线型 {name!r} 未定义，先调用 linetype() 建词典；已有：{sorted(self._types)}")
        return self._types[name]

    # ---------- 原语 ----------
    def box(self, x, y, w, h, lines, cls="node", line_gap=None, font_shift=6,
            label=None, label_gap=17) -> Box:
        """画矩形并把多行文字垂直居中。居中由算式定，不靠 CSS。

        label 给一行小号说明（如环节编号），排在正文上方，用 .node-label 样式。
        它是「框内两个字号」的唯一允许形式——再多层级就该换 HTML+SVG。
        """
        if isinstance(lines, str):
            lines = [lines]
        gap = line_gap if line_gap is not None else (23 if len(lines) > 2 else 26)
        total = (len(lines) - 1) * gap + (label_gap if label else 0)
        cy = y + h / 2 - total / 2 + font_shift
        cx = x + w / 2
        parts = [f'<rect class="{cls}" x="{_n(x)}" y="{_n(y)}" width="{_n(w)}" '
                 f'height="{_n(h)}" rx="2"/>']
        if label:
            parts.append(f'<text x="{_n(cx)}" y="{_n(cy)}" class="node-label" '
                         f'text-anchor="middle">{esc(label)}</text>')
            cy += label_gap
        spans = "".join(f'<tspan x="{_n(cx)}" dy="{gap if i else 0}">{esc(t)}</tspan>'
                        for i, t in enumerate(lines))
        parts.append(f'<text x="{_n(cx)}" y="{_n(cy)}" class="node-text" '
                     f'text-anchor="middle">{spans}</text>')
        self._parts.append("".join(parts))
        return Box(x, y, w, h)

    def text(self, x, y, lines, cls="diagram-note", anchor="middle", gap=24) -> "Diagram":
        if isinstance(lines, str):
            lines = [lines]
        spans = "".join(f'<tspan x="{_n(x)}" dy="{gap if i else 0}">{esc(t)}</tspan>'
                        for i, t in enumerate(lines))
        self._parts.append(f'<text x="{_n(x)}" y="{_n(y)}" class="{cls}" text-anchor="{anchor}">{spans}</text>')
        return self

    def path(self, d: str, linetype: str, arrow: bool = True) -> "Diagram":
        """画折线。d 只允许 M / H / V，出现别的命令直接报错。"""
        _assert_orthogonal(d)
        t = self._t(linetype)
        marker = f' marker-end="url(#{self.ident}-{t.name})"' if arrow else ""
        self._parts.append(f'<path class="flow-{t.name}" d="{d}"{marker}/>')
        return self

    def dot(self, x, y, linetype: str, r: float = 4) -> "Diagram":
        t = self._t(linetype)
        self._parts.append(f'<circle cx="{_n(x)}" cy="{_n(y)}" r="{_n(r)}" fill="{t.color}"/>')
        return self

    # ---------- 组合动作：把纪律变成代码保证 ----------
    def connect(self, a: Box, b: Box, linetype: str,
                from_side: str | None = None, to_side: str | None = None,
                via: float | None = None) -> "Diagram":
        """连两个框。端点自动落在框的边缘中点，走直角折线。

        from_side / to_side 不给时按两框相对位置自动选。
        via 给一个中间坐标（仅在起止边同向时用到）：横向连接时是折点的 x，纵向连接时是折点的 y。
        起止边不同向时路径只有两段，折点由两框坐标唯一确定，via 被忽略。
        """
        if from_side is None or to_side is None:
            dx, dy = b.cx - a.cx, b.cy - a.cy
            if abs(dx) >= abs(dy):
                from_side = from_side or ("right" if dx > 0 else "left")
                to_side = to_side or ("left" if dx > 0 else "right")
            else:
                from_side = from_side or ("bottom" if dy > 0 else "top")
                to_side = to_side or ("top" if dy > 0 else "bottom")
        x1, y1 = a.anchor(from_side)
        x2, y2 = b.anchor(to_side)
        # 关键：第一段必须垂直于起点边，最后一段必须垂直于目标边，
        # 否则箭头会从侧面擦过目标框而不是插进它的边。
        h_from = from_side in ("right", "left")
        h_to = to_side in ("right", "left")
        if y1 == y2 and h_from and h_to:
            d = f"M{_n(x1)} {_n(y1)} H{_n(x2)}"
        elif x1 == x2 and not h_from and not h_to:
            d = f"M{_n(x1)} {_n(y1)} V{_n(y2)}"
        elif h_from and h_to:
            mid = via if via is not None else (x1 + x2) / 2
            d = f"M{_n(x1)} {_n(y1)} H{_n(mid)} V{_n(y2)} H{_n(x2)}"
        elif h_from and not h_to:
            d = f"M{_n(x1)} {_n(y1)} H{_n(x2)} V{_n(y2)}"
        elif not h_from and h_to:
            d = f"M{_n(x1)} {_n(y1)} V{_n(y2)} H{_n(x2)}"
        else:
            mid = via if via is not None else (y1 + y2) / 2
            d = f"M{_n(x1)} {_n(y1)} V{_n(mid)} H{_n(x2)} V{_n(y2)}"
        return self.path(d, linetype)

    def merge(self, sources: list[tuple[float, float]], point: tuple[float, float],
              target: tuple[float, float], linetype: str) -> "Diagram":
        """多条线汇合成一条。

        每条 source 各自走到汇合点（不带箭头）→ 画出汇合点 → 从汇合点出发一条带箭头的线。
        箭头只加在汇合之后那一段，读者才看得出是「汇合后共同进入」而不是「各自到达」。
        """
        px, py = point
        for sx, sy in sources:
            if sy == py:
                d = f"M{_n(sx)} {_n(sy)} H{_n(px)}"
            elif sx == px:
                d = f"M{_n(sx)} {_n(sy)} V{_n(py)}"
            else:
                d = f"M{_n(sx)} {_n(sy)} H{_n(px)} V{_n(py)}"
            self.path(d, linetype, arrow=False)
        self.dot(px, py, linetype)
        tx, ty = target
        if ty == py:
            d = f"M{_n(px)} {_n(py)} H{_n(tx)}"
        elif tx == px:
            d = f"M{_n(px)} {_n(py)} V{_n(ty)}"
        else:
            d = f"M{_n(px)} {_n(py)} V{_n(ty)} H{_n(tx)}"
        return self.path(d, linetype, arrow=True)

    def grid(self, x0, y0, dx, dy, cols, rows, draw):
        """规整行列用公式生成。draw(col, row, x, y) 由调用方决定画什么。"""
        for r in range(rows):
            for c in range(cols):
                draw(c, r, x0 + dx * c, y0 + dy * r)
        return self

    # ---------- 输出 ----------
    def css(self) -> str:
        """线型对应的 CSS，贴进页面的 <style> 里。"""
        out = [".node-text{font-size:18px}", ".node-label{font-size:11.5px;fill:#7b86a8;letter-spacing:.06em}",
               ".node{fill:#fff;stroke:#174a8b;stroke-width:1.3}",
               ".node-soft{fill:#edf3f9;stroke:none}",
               ".node-outline{fill:#fff;stroke:#174a8b;stroke-width:2}"]
        for t in self._types.values():
            dash = f";stroke-dasharray:{t.dash}" if t.dash else ""
            out.append(f".flow-{t.name}{{fill:none;stroke:{t.color};stroke-width:{t.width};"
                       f"stroke-linejoin:round{dash}}}")
        return "\n".join(out)

    def render(self) -> str:
        if not self.desc:
            raise ValueError("desc 不能为空——写不出这张图的关系复述，说明关系还没想清楚，回去改图")
        markers = "".join(
            f'<marker id="{self.ident}-{t.name}" viewBox="0 0 10 10" refX="8" refY="5" '
            f'markerWidth="7" markerHeight="7" orient="auto">'
            f'<path d="M0 0 L10 5 L0 10z" fill="{t.color}"/></marker>' for t in self._types.values())
        return (f'<svg class="diagram" viewBox="0 0 {_n(self.width)} {_n(self.height)}" '
                f'xmlns="http://www.w3.org/2000/svg" role="img" '
                f'aria-labelledby="{self.ident}-title {self.ident}-desc">'
                f'<title id="{self.ident}-title">{esc(self.title)}</title>'
                f'<desc id="{self.ident}-desc">{esc(self.desc)}</desc>'
                f'<defs>{markers}</defs>{"".join(self._parts)}</svg>')


def _n(v) -> str:
    f = float(v)
    return str(int(f)) if f == int(f) else f"{f:g}"


def _assert_orthogonal(d: str) -> None:
    bad = [ch for ch in d if ch.isalpha() and ch.upper() not in ("M", "H", "V")]
    if bad:
        raise ValueError(f"折线只走直角，d 里只允许 M/H/V，发现 {sorted(set(bad))}；"
                         f"要画斜线或曲线说明这张图的关系还没切清楚：{d}")


# ---------------------------------------------------------------- self test
def _self_test() -> None:
    import xml.etree.ElementTree as ET

    d = Diagram("t", 600, 300, title="测试", desc="两条货流在中点汇合后进入下游。")
    d.linetype("material", "#87694b").linetype("info", "#174a8b", dash="6 5")

    a = d.box(20, 40, 120, 60, ["自有采购", "生豆"], "node")
    b = d.box(20, 160, 120, 60, ["代工采购", "成品"], "node")
    c = d.box(360, 100, 120, 60, ["仓储"], "node")
    assert a.right == 140 and a.cy == 70, "框的边界坐标算错"
    assert a.anchor("right") == (140, 70)

    d.connect(a, c, "material")
    d.merge([(140, 70), (140, 190)], (250, 130), (360, 130), "material")
    d.text(300, 280, "图注", "diagram-note")

    out = d.render()
    ET.fromstring(out)                                    # 结构可解析
    assert out.count("<circle") == 1, "汇合点应恰好一个"
    arrows = out.count('marker-end=')
    assert arrows == 2, f"连接一条 + 汇合后一条 = 2 个箭头，实得 {arrows}"
    assert 'role="img"' in out and "<desc" in out, "缺无障碍属性"
    assert ".flow-material" in d.css() and "stroke-dasharray:6 5" in d.css()

    for bad in ("M0 0 L10 10", "M0 0 C1 1 2 2 3 3"):
        try:
            d.path(bad, "material")
        except ValueError:
            pass
        else:
            raise AssertionError(f"应拒绝非直角路径：{bad}")

    try:
        Diagram("x", 10, 10, title="t").render()
    except ValueError:
        pass
    else:
        raise AssertionError("desc 为空时应报错")

    try:
        Diagram("y", 10, 10, desc="d").path("M0 0 H1", "没定义过")
    except KeyError:
        pass
    else:
        raise AssertionError("未定义的线型应报错")

    e = Diagram("e", 400, 400, desc="d"); e.linetype("f", "#000")
    p1 = e.box(0, 0, 100, 40, "甲"); p2 = e.box(200, 200, 100, 40, "乙")
    e.connect(p1, p2, "f", from_side="right", to_side="top")
    assert 'd="M100 20 H250 V200"' in e.render(), "右出顶进时最后一段必须垂直，实际：" + e.render()[-260:]
    e2 = Diagram("e2", 400, 400, desc="d"); e2.linetype("f", "#000")
    q1 = e2.box(0, 0, 100, 40, "甲"); q2 = e2.box(200, 200, 100, 40, "乙")
    e2.connect(q1, q2, "f", from_side="bottom", to_side="left")
    assert 'd="M50 40 V220 H200"' in e2.render(), "下出左进时最后一段必须水平"

    lb = Diagram("lb", 200, 100, desc="d"); lb.linetype("f", "#000")
    lb.box(0, 0, 120, 60, ["仓储", "批次与状态"], label="环节 6")
    r = lb.render()
    assert 'class="node-label"' in r and "环节 6" in r, "label 未渲染"
    assert r.index("环节 6") < r.index("仓储"), "label 应排在正文之上"
    assert ".node-label" in lb.css(), "css 缺 node-label"

    n = []
    Diagram("g", 10, 10, desc="d").grid(0, 0, 10, 5, 3, 2, lambda c, r, x, y: n.append((c, r, x, y)))
    assert n == [(0,0,0,0),(1,0,10,0),(2,0,20,0),(0,1,0,5),(1,1,10,5),(2,1,20,5)], "grid 坐标公式错"

    print("svg_diagram self-test 全部通过：14 组断言")


if __name__ == "__main__":
    import sys
    if "--self-test" in sys.argv:
        _self_test()
    else:
        print(__doc__)
