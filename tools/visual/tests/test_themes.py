"""Check all 15 themes on 19 actual diagrams without changing their content/geometry."""
from pathlib import Path
import importlib.util,json,sys,xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('visual_entry',ROOT/'render.py')
entry=importlib.util.module_from_spec(spec);spec.loader.exec_module(entry)
def signature(svg):
    node=ET.fromstring(svg)
    out=[]
    for el in node.iter():
        if el.tag.rsplit('}',1)[-1]=='style':continue
        attrs=tuple(sorted((k,v) for k,v in el.attrib.items() if k not in {'fill','stroke','color','stop-color','style'}))
        out.append((el.tag,attrs,(el.text or '').strip()))
    return out
if __name__=='__main__':
    themes=json.loads((ROOT/'themes/themes.json').read_text())['themes']
    cases=entry.engine.load_examples()
    count=0
    for case in cases:
        svg=entry.engine.render_case(case)
        for theme in themes:
            result=entry.themed_svg(svg,theme)
            assert signature(result)==signature(svg),(case['id'],theme['id'])
            count+=1
    assert count==285
    print('PASS: 285 theme/case combinations preserve text, numbers, coordinates and relationships.')
