#!/usr/bin/env python3
"""Public visual entry: original layout/validation with explicit theme selection."""
import argparse
import json
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'renderers/consulting'))
import render as engine

def palette(theme):
    t=theme['tokens']
    return {'#FFFFFF':t['bg-card'],'#1A1F36':t['text'],'#1E2878':t['accent-text'],
            '#4A5068':t['text-secondary'],'#8B93C7':t['text-secondary'],
            '#E2E5ED':t['border'] if t['border']!='transparent' else t['text-secondary'],
            '#E8EBF4':t['highlight-bg'],'#F4F5F8':t['bg'],'#C9A227':'#C9A227'}

def recolor_css(value, colors):
    return re.sub(r'#[0-9A-Fa-f]{6}\b',lambda m: colors.get(m.group().upper(),m.group()),value)

def themed_svg(svg,theme):
    colors=palette(theme)
    # Replace paint attributes and style only: user text and accessible descriptions stay intact.
    node=ET.fromstring(svg)
    ET.register_namespace('', 'http://www.w3.org/2000/svg')
    for el in node.iter():
        if el.tag.rsplit('}',1)[-1]=='style' and el.text:
            el.text=recolor_css(el.text,colors)
        for key,value in list(el.attrib.items()):
            if key in {'fill','stroke','color','stop-color','style'}:
                el.set(key,recolor_css(value,colors))
    return ET.tostring(node,encoding='unicode')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--theme',default='white')
    parser.add_argument('--list-themes',action='store_true')
    args,rest=parser.parse_known_args()
    themes=json.loads((ROOT/'themes/themes.json').read_text())['themes']
    if args.list_themes:
        for t in themes: print(t['id']+'\t'+t['name'])
        return 0
    matches=[t for t in themes if t['id']==args.theme or t['name']==args.theme]
    if len(matches)!=1: parser.error('Unknown theme; use --list-themes')
    theme=matches[0]
    original=engine.render_case
    engine.render_case=lambda case: themed_svg(original(case),theme)
    engine.STYLE=recolor_css(engine.STYLE,palette(theme))
    return engine.main(rest)
if __name__=='__main__':raise SystemExit(main())
