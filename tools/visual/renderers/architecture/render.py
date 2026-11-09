#!/usr/bin/env python3
"""Offline architecture exports. Standard library only; writes a NEW directory."""
import argparse
import hashlib
import html
import json
from pathlib import Path
import sys
import xml.etree.ElementTree as ET

VISUAL = Path(__file__).resolve().parents[2]
if str(VISUAL / 'renderers') not in sys.path: sys.path.insert(0,str(VISUAL / 'renderers'))
from svg_diagram import Diagram
from architecture.validate import load_json, validate, ModelError
from architecture.layout import layout, wrap

KINDS={'component':'组件','external_system':'外部系统','capability':'能力','process_step':'处理步骤'}
TYPES={'calls':'调用','depends_on':'依赖','data_flow':'数据流','feedback':'反馈'}
STATUS={'explicit':'材料明确','inferred':'推断待确认','unknown':'未知待确认'}
NS='http://www.w3.org/2000/svg'
def esc(x): return html.escape(str(x),quote=True)
def dump(x): return json.dumps(x,ensure_ascii=False,indent=2)+'\n'


def theme_for(name):
    themes=load_json(VISUAL/'themes/themes.json')['themes']
    found=[t for t in themes if name in (t['id'],t['name'])]
    if len(found)!=1:raise ModelError('Unknown theme; see --list-themes')
    return found[0]


def render(model, theme='white'):
    geom=layout(model);t=theme_for(theme)['tokens']
    ident='arch-'+hashlib.sha256(dump(model).encode()).hexdigest()[:12]
    # Full relation labels are kept in a separate ledger, never squeezed onto crossing lines.
    ledger=[];names={n['id']:n['label'] for n in model['nodes']}
    for e in sorted(model['relations'],key=lambda x:x['id']):
        num=geom['routes'][e['id']]['number'];arrow='↔' if e['direction']=='bidirectional' else '→'
        ledger.append((e['id'],wrap(f"{num:02d}  {names[e['source']]} {arrow} {names[e['target']]}",42)+wrap(f"{TYPES[e['type']]} · {e['label']} · {STATUS[e['evidence']['status']]}",42)))
    ledgerheight=sum(28+len(lines)*22 for _,lines in ledger)
    titlelines=wrap(model['title'],min(70,int(geom['width']/11)))
    titleheight=max(100,len(titlelines)*30+48)
    # Shift complete geometry together when a long title needs more room.
    shift=titleheight-100
    for key in ('nodes','groups','boundaries'):
        for r in geom[key].values():r['y']+=shift
    for r in geom['routes'].values():
        r['points']=[(x,y+shift) for x,y in r['points']]
        if r['badge']:r['badge']['y']+=shift
    geom['height']+=shift
    width=geom['width']+510;height=max(geom['height'],titleheight+ledgerheight+100)
    d=Diagram(ident,width,height,model['title'],model['description'])
    for name,dash in [('calls',None),('data_flow',None),('depends_on','3 5'),('feedback','9 5')]:
        d.linetype(name,t['accent-text'],dash=dash,width=1.8)
    raw=[f'<rect width="100%" height="100%" fill="{t["bg"]}"/>']
    d.text(52,42,titlelines,cls='arch-title',anchor='start',gap=30)
    for b in model['boundaries']:
        r=geom['boundaries'][b['id']]
        raw.append(f'<rect class="boundary" x="{r["x"]}" y="{r["y"]}" width="{r["w"]}" height="{r["h"]}" rx="12"/>')
        d.text(r['x']+16,r['y']+27,wrap(b['label'],32),'boundary-title',anchor='start',gap=20)
    for g in model['groups']:
        r=geom['groups'][g['id']]
        raw.append(f'<rect class="group" data-group="{g["id"]}" x="{r["x"]}" y="{r["y"]}" width="{r["w"]}" height="{r["h"]}" rx="9"/>')
        d.text(r['x']+16,r['y']+27,r['lines'],'group-title',anchor='start',gap=22)
    for e in sorted(model['relations'],key=lambda x:x['id']):
        route=geom['routes'][e['id']];pts=route['points']
        path=f'M{pts[0][0]} {pts[0][1]}'
        for a,b in zip(pts,pts[1:]):path+=f' H{b[0]}' if a[1]==b[1] else f' V{b[1]}'
        d.path(path,e['type'])
        # Attach identity and both arrowheads while retaining shared SVG primitives.
        el=ET.fromstring(d._parts.pop())
        el.set('data-relation',e['id']);el.set('tabindex','0')
        if e['direction']=='bidirectional':el.set('marker-start',f'url(#{ident}-{e["type"]}-start)')
        if e['evidence']['status']!='explicit':el.set('style','stroke-dasharray:2 5')
        title=ET.SubElement(el,'title');title.text=f"{route['number']:02d} · {names[e['source']]} {'↔' if e['direction']=='bidirectional' else '→'} {names[e['target']]} · {e['label']} · {STATUS[e['evidence']['status']]}"
        d._parts.append(ET.tostring(el,encoding='unicode'))
    for n in model['nodes']:
        r=geom['nodes'][n['id']]
        cls='external' if n['kind']=='external_system' else 'node'
        d.box(r['x'],r['y'],r['w'],r['h'],[],cls=cls)
        # Explicit text baselines make height depend on measured line estimates.
        d.text(r['x']+14,r['y']+23,KINDS[n['kind']]+' · '+STATUS[n['evidence']['status']],'node-kind',anchor='start')
        d.text(r['x']+14,r['y']+49,r['lines'],'arch-node-title',anchor='start',gap=22)
        d.text(r['x']+14,r['y']+49+22*len(r['lines']),r['body'],'arch-body',anchor='start',gap=19)
    for r in geom['routes'].values():
        if not r['badge']:continue
        b=r['badge'];d.box(b['x'],b['y'],b['w'],b['h'],f'{r["number"]:02d}',cls='edge-badge',font_shift=5)
    lx=geom['width']+10;ly=titleheight
    d.text(lx,ly-28,'关系索引 · 编号对应连线','group-title',anchor='start')
    for eid,lines in ledger:
        d.text(lx,ly,lines,'ledger',anchor='start',gap=22);ly+=len(lines)*22+28
    if not ledger:d.text(lx,ly,'材料未给出关系；未补造连线。','ledger',anchor='start')
    css=d.css()+f'''\ntext{{font-family:system-ui,-apple-system,"PingFang SC",sans-serif;fill:{t['text']}}}
.arch-title{{font-size:24px;font-weight:700}}.group-title,.boundary-title{{font-size:16px;font-weight:650}}
.node,.external{{fill:{t['bg-card']};stroke:{t['accent-text']};stroke-width:1.4}}.external{{stroke-dasharray:6 4}}
.group{{fill:{t['bg']};stroke:{t['text-secondary']};stroke-width:1}}.boundary{{fill:none;stroke:{t['accent-text']};stroke-dasharray:8 5}}
.node-kind{{font-size:11px}}.arch-node-title{{font-size:17px;font-weight:650}}.arch-body{{font-size:14px}}
.ledger{{font-size:15px}}.edge-badge{{fill:{t['bg']};stroke:{t['accent-text']}}}.node-text{{font-size:13px;fill:{t['text']}}}
path:focus,path:hover{{stroke-width:4}}'''
    svg=d.render();root=ET.fromstring(svg)
    defs=root.find('{'+NS+'}defs')
    for mark in list(defs):
        clone=ET.fromstring(ET.tostring(mark));clone.set('id',clone.get('id')+'-start');clone.set('orient','auto-start-reverse');defs.append(clone)
    # Background and containers must be behind titles, paths and nodes.
    style=ET.Element('{'+NS+'}style');style.text=css
    root.insert(0,style)
    for i,part in enumerate(raw):root.insert(i+1,ET.fromstring(part))
    ET.register_namespace('',NS);svg=ET.tostring(root,encoding='unicode')
    report={'version':'0.1.0-draft','model_sha256':hashlib.sha256(dump(model).encode()).hexdigest(),'nodes':len(model['nodes']),'groups':len(model['groups']),'relations':len(model['relations']),'rendered_relations':len(geom['routes']),'layout_modes':geom['modes'],'warnings':geom['warnings'],'semantic_acceptance':'pending-human-review','browser_acceptance':'not-assessed-by-renderer','geometry':geom}
    warning_items=''.join('<li>'+esc(dump(x))+'</li>' for x in geom['warnings']) or '<li>未发现自动布局告警；仍需检查视觉与业务语义。</li>'
    relation_rows=''.join('<tr>'+''.join('<td>'+esc(v)+'</td>' for v in (e['id'],names[e['source']],names[e['target']],e['direction'],TYPES[e['type']],e['label'],STATUS[e['evidence']['status']],', '.join(e['evidence']['sources']),e['evidence']['note']))+'</tr>' for e in model['relations'])
    question_items=''.join('<li>'+esc(q['text'])+'（'+esc(', '.join(q['related_ids']))+'）</li>' for q in model['questions']) or '<li>模型未列待确认项；不等于人工验收通过。</li>'
    evidence_items=''.join('<li><strong>'+esc(item['id'])+'</strong> · '+esc(STATUS[item['evidence']['status']])+' · '+esc(item['evidence']['note'])+' · '+esc(', '.join(item['evidence']['sources']))+'</li>' for section in ('boundaries','groups','nodes') for item in model[section])
    page=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>{esc(model['title'])}</title>
<style>body{{margin:0;background:{t['bg']};color:{t['text']};font:16px/1.65 system-ui,sans-serif}}main{{max-width:1500px;margin:auto;padding:28px}}h1{{font-size:28px}}button,a{{font:inherit;color:inherit}}button{{padding:7px 14px;margin:4px;border:1px solid {t['text-secondary']};border-radius:6px;background:{t['bg-card']}}}.viewport{{overflow:auto;border:1px solid {t['text-secondary']};max-height:78vh;background:{t['bg']}}}.viewport svg{{display:block;width:{width}px;height:auto;max-width:none}}table{{border-collapse:collapse;min-width:800px}}td,th{{border-bottom:1px solid {t['text-secondary']};padding:10px;text-align:left;overflow-wrap:anywhere}}.table-wrap{{overflow:auto}}li{{overflow-wrap:anywhere}}@media print{{button{{display:none}}.viewport{{max-height:none;overflow:visible}}.viewport svg{{width:100%!important}}}}</style>
<main><h1>{esc(model['title'])}</h1><p>{esc(model['description'])}</p><p>节点类型与证据状态分别标注；箭头表示关系方向。反馈使用长虚线，依赖使用短虚线。完整关系见索引及下表。</p>
<nav aria-label="图形操作"><button id="fit">适应宽度</button><button id="actual">实际大小</button><button id="zoom-in">放大</button><button id="zoom-out">缩小</button> <a href="diagram.svg" download>SVG</a> · <a href="model.json" download>可编辑 JSON</a> · <a href="report.json" download>检查报告</a></nav>
<div class="viewport" id="viewport" tabindex="0">{svg}</div><h2>检查提示</h2><ul>{warning_items}</ul><h2>关系与证据</h2><div class="table-wrap"><table><thead><tr>{''.join('<th>'+x+'</th>' for x in ['ID','起点','终点','方向','类型','含义','证据状态','来源','证据说明'])}</tr></thead><tbody>{relation_rows}</tbody></table></div><h2>实体与边界证据</h2><ul>{evidence_items}</ul><h2>待确认</h2><ul>{question_items}</ul><h2>输入材料</h2><ul>{''.join('<li>'+esc(s['id'])+'：'+esc(s['text'])+'</li>' for s in model['sources'])}</ul><p>编辑 model.json 后重新运行同一命令输出到新目录。图形检查不替代人工语义验收。</p></main>
<script>const view=document.getElementById('viewport'),svg=view.querySelector('svg');const base={width};let size=base;function setSize(n){{size=Math.max(300,Math.min(base*3,n));svg.style.width=size+'px'}}document.getElementById('fit').onclick=()=>setSize(view.clientWidth);document.getElementById('actual').onclick=()=>setSize(base);document.getElementById('zoom-in').onclick=()=>setSize(size*1.25);document.getElementById('zoom-out').onclick=()=>setSize(size/1.25);</script></html>'''
    return svg,page,report


def export(model,output,theme='white'):
    output=Path(output).expanduser().resolve()
    if output==VISUAL or VISUAL in output.parents:raise ModelError('Output must be outside tools/visual')
    if output.exists():raise ModelError('Output directory already exists; choose a new directory')
    svg,page,report=render(model,theme)
    output.mkdir(parents=True,exist_ok=False)
    for name,data in [('diagram.svg',svg),('index.html',page),('model.json',dump(model)),('report.json',dump(report))]:
        (output/name).write_text(data,encoding='utf-8')
    return report


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input',required=True);p.add_argument('--output-dir',required=True);p.add_argument('--theme',default='white')
    args=p.parse_args(argv)
    try:report=export(load_json(args.input),args.output_dir,args.theme)
    except (ValueError,OSError) as exc:p.exit(2,'Architecture export failed: '+str(exc)+'\n')
    print(dump({k:v for k,v in report.items() if k!='geometry'}))
    return 0

if __name__=='__main__':raise SystemExit(main())
