#!/usr/bin/env python3
"""Render consulting examples to standalone SVG and an offline HTML atlas.

Outputs are written only to explicitly chosen, new locations outside the tool source tree.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import sys
import unittest
import xml.etree.ElementTree as ET

import diagrams

ROOT = Path(__file__).resolve().parent
GROUPS = [
    ("compare", "比较与差距", "谁高谁低，与目标差多少", ["bar", "slope", "bullet"]),
    ("change", "趋势与贡献", "怎样变化，变化来自哪里", ["line", "waterfall", "stacked_bar"]),
    ("prioritize", "诊断与取舍", "缺口在哪，先看哪些对象", ["scatter", "heatmap", "harvey"]),
    ("logic", "流程与结构", "顺序、分工、分解和支撑关系", ["process", "swimlane", "issue_tree", "layers"]),
    ("delivery", "证据与实施", "依据是什么，谁在何时负责", ["evidence_table", "raci", "roadmap", "gantt"]),
    ("conditional", "有条件的进阶图", "同时呈现规模、占比与数量流向", ["sankey", "mekko"]),
]
NAMES = {
    "bar": "排序条形图", "stacked_bar": "100% 堆积条形图", "line": "趋势折线图",
    "slope": "前后变化斜率图", "waterfall": "贡献瀑布图", "bullet": "目标对照子弹图",
    "scatter": "二维气泡组合图", "heatmap": "能力热力矩阵", "harvey": "Harvey 状态圆点",
    "sankey": "两列桑基图", "mekko": "Mekko 规模构成图", "evidence_table": "证据对照表",
    "raci": "责任分工矩阵", "process": "必要输入汇合图", "swimlane": "跨部门泳道图",
    "issue_tree": "问题拆解树", "layers": "职责分层图", "roadmap": "阶段路线图", "gantt": "依赖甘特图",
}


def render_case(case):
    if case.get("kind") in diagrams.KINDS:
        svg = diagrams.render(case)
    else:
        try:
            import charts
        except ImportError as exc:
            raise ValueError("定量案例模块不可用；不可静默替换或跳过图形") from exc
        if case.get("kind") not in charts.KINDS:
            raise ValueError("未知图形类型")
        svg = charts.render(case)
    root = ET.fromstring(svg)
    ns = {"s": "http://www.w3.org/2000/svg"}
    if root.attrib.get("role") != "img" or root.find("s:desc", ns) is None:
        raise ValueError("SVG 缺少可访问的说明")
    if root.attrib.get("id") != case["id"] + "-svg":
        raise ValueError("SVG 命名空间与案例不一致")
    for el in root.iter():
        if el.tag.rsplit("}", 1)[-1] in {"script", "foreignObject", "image"}:
            raise ValueError("案例要求纯矢量且没有主动加载内容")
        if any(key.lower().startswith("on") for key in el.attrib):
            raise ValueError("SVG 不允许事件处理器")
        if any(key.rsplit("}", 1)[-1] == "href" and not value.startswith("#") for key, value in el.attrib.items()):
            raise ValueError("SVG 不允许外部资源")
    return svg


def write_new(path, text):
    path = Path(path).resolve()
    if path == ROOT.parents[1] or ROOT.parents[1] in path.parents:
        raise ValueError("请将渲染产物保存到 tools/visual 之外的新目录")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(text)


def load_examples(subset="all", allow_partial=False):
    names = {"all": ["diagram-examples.json", "quantitative-examples.json"],
             "diagrams": ["diagram-examples.json"], "charts": ["quantitative-examples.json"]}[subset]
    cases = []
    for name in names:
        path = ROOT.parents[1] / "examples" / name
        if not path.exists() and allow_partial:
            continue
        cases.extend(json.loads(path.read_text(encoding="utf-8")))
    return cases


STYLE = """
:root{color-scheme:light;--ink:#1A1F36;--blue:#1E2878;--soft:#4A5068;--line:#E2E5ED;--wash:#E8EBF4}
*{box-sizing:border-box}html{scroll-behavior:auto}body{margin:0;background:#F4F5F8;color:var(--ink);font:17px/1.65 'PingFang SC','Microsoft YaHei',sans-serif}
a{color:var(--blue);text-underline-offset:4px}a:focus-visible,summary:focus-visible{outline:3px solid #C9A227;outline-offset:5px}
header,main,footer{max-width:1400px;margin:auto;padding:32px}header{padding-top:48px;background:#FFFFFF;border-bottom:5px solid var(--blue)}
h1{font-size:44px;line-height:1.25;margin:0 0 16px;letter-spacing:-1px;color:var(--blue)}.intro{max-width:850px;margin:0 0 22px;font-size:19px}
.status{display:flex;gap:25px;flex-wrap:wrap;border-top:1px solid var(--line);padding-top:15px;color:var(--soft);font-size:15px}
nav{display:flex;gap:10px 24px;flex-wrap:wrap;margin-top:23px}nav a{white-space:nowrap;font-weight:600}
.group{scroll-margin-top:20px;margin:20px 0 58px}.group-head{display:flex;align-items:baseline;gap:22px;flex-wrap:wrap;margin:0 0 20px}.group-head h2{font-size:29px;line-height:1.3;margin:0}.group-head p{margin:0;color:var(--soft)}
.case{background:#FFFFFF;margin-bottom:24px;border:1px solid var(--line)}.case-heading{display:flex;gap:22px;align-items:baseline;flex-wrap:wrap;padding:18px 24px 12px;border-bottom:1px solid var(--line)}
.case-heading h3{font-size:23px;line-height:1.4;margin:0}.tag{font-size:14px;color:var(--soft)}.case-body{display:grid;grid-template-columns:minmax(0,1fr) 260px;align-items:start}
.artwork{overflow:auto;max-width:100%;background:#FFFFFF;padding:5px 0}.artwork svg{display:block;width:100%;min-width:780px;height:auto}
aside{padding:20px 20px 22px;border-left:1px solid var(--line);font-size:16px}aside h4{font-size:15px;color:var(--blue);margin:0 0 5px}aside p{margin:0 0 18px}
.links{display:flex;gap:18px;margin-top:5px;flex-wrap:wrap}details{border-top:1px solid var(--line);padding:12px 24px}summary{cursor:pointer;color:var(--blue);font-size:15px}pre{overflow:auto;font-size:13px;line-height:1.55;background:#F4F5F8;padding:16px;white-space:pre-wrap;overflow-wrap:anywhere}
.note{color:var(--soft);font-size:15px;max-width:1000px}footer{padding-top:0}.mobile-note{display:none}
@media(max-width:1000px){header,main,footer{padding:22px}.case-body{grid-template-columns:1fr}aside{border-left:none;border-top:1px solid var(--line);display:grid;grid-template-columns:1fr 1fr;gap:0 22px}.links{grid-column:1/-1}.artwork svg{min-width:780px}.mobile-note{display:block;font-size:14px;color:var(--soft)}}
@media(max-width:600px){header,main,footer{padding:17px}h1{font-size:32px}.intro{font-size:17px}.case-heading{padding:14px 16px}.case-heading h3{font-size:21px}aside{padding:16px;display:block}.group-head h2{font-size:26px}nav{gap:10px 16px}.status{gap:8px 20px}}
@media print{body{background:#FFFFFF}header,main,footer{padding:0}nav,details,.links,.mobile-note{display:none}.case{break-inside:avoid;page-break-inside:avoid;margin:0 0 20mm;border:0}.case-body{grid-template-columns:1fr}.artwork{overflow:visible}.artwork svg{min-width:0;width:100%}aside{display:block;border:0;padding:0;font-size:11pt}.group{break-before:page}.group-head{margin-bottom:8mm}h1{font-size:26pt}.status,.intro{font-size:11pt}}
"""


def _atlas(cases, svgs):
    e = html.escape
    data_note = "所有示例均为合成内容" if all(c["source"]["kind"] == "synthetic" for c in cases) else "来源状态见各图；用户提供不等于已核验"
    navigation, sections = [], []
    for slug, name, purpose, kinds in GROUPS:
        matching = [c for kind in kinds for c in cases if c["kind"] == kind]
        if not matching:
            continue
        navigation.append(f'<a href="#{slug}">{name}</a>')
        cards = []
        for case in matching:
            ident, kind = case["id"], case["kind"]
            conditional = "限两列非负流量" if kind == "sankey" else "限小规模构成数据" if kind == "mekko" else "有限规模案例"
            spec = e(json.dumps(case, ensure_ascii=False, indent=2))
            cards.append(f'''<article class="case" id="{e(ident)}">
<div class="case-heading"><h3>{e(NAMES.get(kind, kind))}</h3><span class="tag">{conditional}</span></div>
<div class="case-body"><div class="artwork">{svgs[ident]}</div><aside>
<div><h4>它回答什么</h4><p>{e(case['question'])}</p></div>
<div><h4>使用边界</h4><p>{e(case['boundary'])}</p></div>
<div class="links"><a href="svg/{e(ident)}.svg" target="_blank" rel="noopener">单独看大图</a><a href="specs/{e(ident)}.json">源数据</a></div>
</aside></div><details><summary>查看可复用的输入样例</summary><pre><code>{spec}</code></pre></details></article>''')
        sections.append(f'<section class="group" id="{slug}"><div class="group-head"><h2>{name}</h2><p>{purpose}</p></div>' + "".join(cards) + '</section>')
    return f'''<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; img-src 'self' data:; font-src 'none'; base-uri 'none'; form-action 'none'">
<title>咨询汇报图形案例：先选问题，再选图形</title><style>{STYLE}</style></head>
<body><header><h1>先选问题，再选图形</h1><p class="intro">一套可以改数据、重画、复核的咨询汇报图形案例。图形只负责把证据与关系说清楚，不替代数据核验或业务判断。</p>
<div class="status"><span>{len(cases)} 个可复用案例</span><span>纯 SVG 与 HTML，无外部加载</span><span>{data_note}</span></div>
<nav aria-label="图形分类">{''.join(navigation)}</nav><p class="mobile-note">窄屏可左右移动图形查看，或打开单图放大；不通过压小中文字来挤满页面。</p></header>
<main>{''.join(sections)}</main><footer><p class="note">这些是随工具提供的有限规模示例。案例通过不代表任意长文、任意网络或所有字体均已通过；SVG 可编辑源码，也不等于 PowerPoint 原生图表与流程对象。来源与验证边界见工具说明。</p></footer></body></html>'''


def build_gallery(cases, output):
    ids = [c.get("id") for c in cases]
    if not cases or len(ids) != len(set(ids)):
        raise ValueError("案例为空或 id 重复")
    # Validate everything before the first write, so malformed inputs leave no partial output.
    svgs = {c["id"]: render_case(c) for c in cases}
    page = _atlas(cases, svgs)
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("图册目录已存在；请换一个新目录，保留旧结果")
    payloads = {"index.html": page}
    for case in cases:
        payloads[f'svg/{case["id"]}.svg'] = svgs[case["id"]]
        payloads[f'specs/{case["id"]}.json'] = json.dumps(case, ensure_ascii=False, indent=2) + "\n"
    manifest = {"schema_version": 1, "created_at": datetime.now(timezone.utc).isoformat(),
                "case_count": len(cases), "research_cutoff": "2026-08-31", "engine": "Python stdlib + inline SVG + existing svg_diagram",
                "data_status": "synthetic examples" if all(c["source"]["kind"] == "synthetic" for c in cases) else "provided and/or synthetic; see each spec",
                "case_ids": ids, "files": {name: hashlib.sha256(text.encode()).hexdigest() for name, text in payloads.items()},
                "validation_boundary": "生成与SVG合同检查；浏览器、盲读、PPT及跨机验证单独记录"}
    for name, text in payloads.items():
        write_new(output / name, text)
    write_new(output / "manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--list", action="store_true")
    mode.add_argument("--gallery", type=Path, metavar="NEW_DIRECTORY")
    mode.add_argument("--case", metavar="ID")
    mode.add_argument("--input", type=Path, metavar="SPEC_JSON")
    mode.add_argument("--self-test", action="store_true")
    parser.add_argument("--output", type=Path, help="单图输出 SVG 的新文件路径")
    parser.add_argument("--subset", choices=["all", "diagrams", "charts"], default="all")
    args = parser.parse_args(argv)
    try:
        if args.self_test:
            suite = unittest.defaultTestLoader.discover(str(ROOT.parents[1] / "tests"), pattern="test_*.py")
            return 0 if unittest.TextTestRunner(verbosity=2).run(suite).wasSuccessful() else 1
        if args.input:
            case = json.loads(args.input.read_text(encoding="utf-8"))
        elif args.case:
            candidates = [c for c in load_examples(allow_partial=True) if c["id"] == args.case]
            if len(candidates) != 1:
                raise ValueError("没有唯一匹配的案例 id；先用 --list 查看")
            case = candidates[0]
        else:
            cases = load_examples(args.subset)
            if args.list:
                for case in cases:
                    print(f'{case["id"]}\t{case["kind"]}\t{case["question"]}')
                return 0
            manifest = build_gallery(cases, args.gallery)
            print(json.dumps({"case_count": manifest["case_count"], "index": str(args.gallery.resolve() / "index.html")}, ensure_ascii=False))
            return 0
        if not args.output:
            raise ValueError("单图必须显式指定 --output")
        write_new(args.output, render_case(case))
        print(str(args.output.resolve()))
        return 0
    except (ValueError, KeyError, FileNotFoundError, FileExistsError, ET.ParseError) as exc:
        print(f"未生成：{exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
