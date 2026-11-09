"""Architecture contracts, routing geometry, exports, and semantic fixture checks."""
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'tools/visual/renderers'))
from architecture.validate import validate, load_json, ModelError
from architecture.layout import layout, hits, overlaps
from architecture.render import render, export


def sample(count=3,topology='chain'):
    ev={'status':'explicit','sources':['s1'],'note':'Synthetic test specification'}
    m={'version':'0.1.0','title':'Synthetic architecture','description':'Generated test fixture, not an actual system.','layout':'auto','sources':[{'id':'s1','text':'This test defines every component and relation below.'}],'boundaries':[],'groups':[],'nodes':[],'relations':[],'questions':[]}
    for i in range(count):
        m['groups'].append({'id':f'g{i}','label':f'Group {i}','boundary':None,'evidence':copy.deepcopy(ev)})
        m['nodes'].append({'id':f'n{i}','label':f'Node {i}','group':f'g{i}','kind':'component','responsibility':'Test component','evidence':copy.deepcopy(ev)})
    pairs=[(i,i+1) for i in range(count-1)] if topology!='hub' else [(0,i) for i in range(1,count)]
    if topology=='loops':pairs += [(count-1,0),(count-1,1),(1,0)]
    for i,(a,b) in enumerate(pairs):m['relations'].append({'id':f'r{i}','source':f'n{a}','target':f'n{b}','type':'feedback' if b<a else 'data_flow','direction':'forward','label':f'Transfer {i}','evidence':copy.deepcopy(ev)})
    return m


class ArchitectureTests(unittest.TestCase):
    def test_rejects_bad_shape_and_references(self):
        for mutate in [lambda m:m.update(extra=True),lambda m:m['nodes'][0].update(group='missing'),lambda m:m['relations'][0].update(target='missing'),lambda m:m['groups'][0].update(boundary='missing'),lambda m:m['nodes'][0].update(id='g0'),lambda m:m['nodes'][0].update(kind='microservice'),lambda m:m['nodes'][0]['evidence'].update(sources=[]),lambda m:m['relations'][0].update(type='contains'),lambda m:m['nodes'][0].update(label=' '),lambda m:m['groups'].append({'id':'empty','label':'empty','boundary':None,'evidence':m['groups'][0]['evidence']})]:
            with self.subTest(mutate=mutate):
                m=sample();mutate(m)
                with self.assertRaises(ModelError):validate(m)
    def test_unknown_requires_linked_question(self):
        m=sample();m['nodes'][0]['evidence']['status']='inferred'
        with self.assertRaises(ModelError):validate(m)
        m['questions']=[{'id':'q1','text':'Confirm inferred node','related_ids':['n0']}]
        self.assertEqual(validate(m)[0]['id'],'n0')
    def test_duplicate_relation_and_keys(self):
        m=sample();e=copy.deepcopy(m['relations'][0]);e['id']='rdup';m['relations'].append(e)
        with self.assertRaises(ModelError):validate(m)
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'bad.json';p.write_text('{"version":"0.1.0","version":"0.1.0"}')
            with self.assertRaises(ModelError):load_json(p)
    def test_review_regressions(self):
        for field,value in [('id','bad\n'),('label','Bad\uffffXML'),('label','Bad\ud800XML')]:
            m=sample();m['nodes'][0][field]=value
            with self.assertRaises(ModelError):validate(m)
        m=sample();m['relations'][0]['direction']='bidirectional'
        svg,_,_=render(m)
        self.assertIn('↔',''.join(ET.fromstring(svg).itertext()))
        m['nodes'][0]['label']='W'*180
        _,_,rep=render(m)
        self.assertTrue(all(len(line)<=13 for line in rep['geometry']['nodes']['n0']['lines']))

    def test_boundary_title_and_uncertain_style(self):
        m=sample(1);m['boundaries']=[{'id':'b1','label':'W'*52,'kind':'system','evidence':m['nodes'][0]['evidence']}];m['groups'][0]['boundary']='b1'
        svg,_,report=render(m)
        root=ET.fromstring(svg)
        titles=[el for el in root.iter() if el.get('class')=='boundary-title']
        self.assertTrue(all(len(el.text or '')<=16 for title in titles for el in title))
        m=sample();m['relations'][0]['type']='feedback';m['relations'][0]['evidence']['status']='inferred'
        m['questions']=[{'id':'q1','text':'Confirm relation','related_ids':['r0']}]
        svg,_,_=render(m)
        edge=next(el for el in ET.fromstring(svg).iter() if el.get('data-relation')=='r0')
        self.assertEqual(edge.get('style'),'stroke-dasharray:2 5')

    def test_capacity_errors(self):
        with self.assertRaises(ModelError):layout(sample(13))
    def check_geometry(self,m):
        g=layout(m)
        boxes=list(g['nodes'].values())
        for i,a in enumerate(boxes):
            for b in boxes[i+1:]:self.assertFalse(overlaps(a,b))
        groupboxes=list(g['groups'].values())
        for i,a in enumerate(groupboxes):
            for b in groupboxes[i+1:]:self.assertFalse(overlaps(a,b))
        self.assertEqual(set(g['routes']),{e['id'] for e in m['relations']})
        for e in m['relations']:
            points=g['routes'][e['id']]['points']
            self.assertGreaterEqual(len(points),2)
            for j,(a,b) in enumerate(zip(points,points[1:])):
                self.assertTrue(a[0]==b[0] or a[1]==b[1])
                for ident,r in g['nodes'].items():
                    if (ident==e['source'] and j==0) or (ident==e['target'] and j==len(points)-2):continue
                    self.assertFalse(hits(a,b,r),(e['id'],ident,a,b))
            for end,ident in [(points[0],e['source']),(points[-1],e['target'])]:
                r=g['nodes'][ident]
                self.assertTrue((end[0] in (r['x'],r['x']+r['w']) and r['y']<end[1]<r['y']+r['h']) or (end[1] in (r['y'],r['y']+r['h']) and r['x']<end[0]<r['x']+r['w']))
        return g
    def test_dynamic_sizes_and_topologies(self):
        for n in (3,6,8,12):
            for mode in ('chain','hub','loops'):
                with self.subTest(n=n,mode=mode):self.check_geometry(sample(n,mode))
    def test_explicit_modes_and_self_loop(self):
        for mode in ('linear','layered','radial'):
            m=sample(6);m['layout']=mode;self.check_geometry(m)
        m=sample(1);m['relations']=[{'id':'self','source':'n0','target':'n0','type':'feedback','direction':'bidirectional','label':'Self retry','evidence':m['nodes'][0]['evidence']}]
        self.check_geometry(m)
        svg,_,_=render(m);self.assertIn('marker-start=',svg)
    def test_boundary_membership_geometry(self):
        m=sample(3);m['boundaries']=[{'id':'b1','label':'System boundary','kind':'system','evidence':m['nodes'][0]['evidence']}]
        for g in m['groups'][:2]:g['boundary']='b1'
        geo=self.check_geometry(m);b=geo['boundaries']['b1']
        self.assertFalse(overlaps(b,geo['groups']['g2']))
        for ident in ('g0','g1'):
            r=geo['groups'][ident];self.assertTrue(b['x']<r['x'] and r['x']+r['w']<b['x']+b['w'])
    def test_long_labels_and_untrusted_text(self):
        m=sample();m['title']='长标题'*40;m['nodes'][0]['label']='超级长组件名称'*20
        m['nodes'][0]['responsibility']='LongUnbrokenComponentResponsibility'*6
        m['relations'][0]['label']='</script><script>alert(1)</script> & "quoted"'
        svg,page,rep=render(m)
        root=ET.fromstring(svg)
        self.assertNotIn('<script>',svg);self.assertNotIn(m['relations'][0]['label'],page)
        self.assertIn(m['relations'][0]['label'],''.join(root.itertext()))
        box=rep['geometry']['nodes']['n0'];self.assertGreater(box['h'],300)
    def test_theme_geometry_and_determinism(self):
        m=sample();baseline=render(m)
        self.assertEqual(baseline,render(copy.deepcopy(m)))
        themes=load_json(ROOT/'tools/visual/themes/themes.json')['themes']
        for t in themes:
            svg,page,report=render(m,t['id'])
            self.assertEqual(report['geometry'],baseline[2]['geometry'])
            ET.fromstring(svg)
    def test_export_reload_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'output';m=sample();export(m,dest)
            self.assertEqual(set(p.name for p in dest.iterdir()),{'diagram.svg','index.html','model.json','report.json'})
            self.assertEqual(load_json(dest/'model.json'),m)
            self.assertEqual(render(load_json(dest/'model.json'))[0],(dest/'diagram.svg').read_text())
            with self.assertRaises(ModelError):export(m,dest)
            with self.assertRaises(ModelError):export(m,ROOT/'tools/visual/new-output')
    def test_cli_in_clean_environment(self):
        with tempfile.TemporaryDirectory() as d:
            src=Path(d)/'model.json';src.write_text(json.dumps(sample()))
            result=subprocess.run([sys.executable,'-I',str(ROOT/'tools/visual/renderers/architecture/render.py'),'--input',str(src),'--output-dir',str(Path(d)/'bundle')],capture_output=True,text=True)
            self.assertEqual(result.returncode,0,result.stderr)
    def test_example_relationships_and_group_membership(self):
        expected={
          'autoloop': [('任务 API','计划器','calls'),('计划器','工作器','calls'),('工作器','工具适配器','calls'),('工具适配器','工作器','data_flow'),('工作器','检查器','data_flow'),('检查器','结果库','data_flow'),('检查器','计划器','feedback'),('结果库','任务 API','data_flow')],
          'supply-chain': [('采集器','预测服务','data_flow'),('库存账本','建议引擎','data_flow'),('预测服务','建议引擎','data_flow'),('建议引擎','审批台','data_flow'),('审批台','人工批准','data_flow'),('人工批准','审批台','feedback'),('审批台','仓储系统','calls'),('仓储系统','库存账本','feedback')],
          'museum': [('分发中心','策展服务','calls'),('分发中心','媒体库','calls'),('分发中心','检索服务','calls'),('分发中心','语音服务','calls'),('分发中心','终端系统','data_flow'),('分发中心','统计服务','data_flow'),('管理台','分发中心','calls'),('终端系统','分发中心','feedback')]
        }
        assignments={
          'autoloop': {'任务 API':'任务接入','计划器':'任务接入','工作器':'执行','工具适配器':'执行','检查器':'质量反馈','结果库':'质量反馈'},
          'supply-chain': {'采集器':'采集','库存账本':'库存','预测服务':'预测','建议引擎':'决策','审批台':'审批','人工批准':'审批','仓储系统':'外部履约'},
          'museum': {'分发中心':'分发','策展服务':'策展','媒体库':'存储','检索服务':'检索','终端系统':'展厅终端','语音服务':'语音','统计服务':'统计','管理台':'管理'}
        }
        for case,edges in expected.items():
            m=load_json(ROOT/'prompts/architecture-diagram/examples'/case/'model.json');validate(m)
            names={n['id']:n['label'] for n in m['nodes']};groups={g['id']:g['label'] for g in m['groups']}
            self.assertEqual({(names[e['source']],names[e['target']],e['type']) for e in m['relations']},set(edges))
            self.assertEqual({n['label']:groups[n['group']] for n in m['nodes']},assignments[case])
            self.assertTrue(all(e['direction']=='forward' for e in m['relations']))
            for n in m['nodes']:
                expected_kind='process_step' if n['label']=='人工批准' else 'external_system' if n['label'] in ('仓储系统','终端系统') else 'component'
                self.assertEqual(n['kind'],expected_kind)
            self.check_geometry(m)
            if case=='supply-chain':self.assertTrue(m['questions'])
    def test_public_entry(self):
        with tempfile.TemporaryDirectory() as d:
            r=subprocess.run([sys.executable,str(ROOT/'tools/visual/render.py'),'--architecture','--input',str(ROOT/'prompts/architecture-diagram/examples/autoloop/model.json'),'--output-dir',str(Path(d)/'result'),'--theme','midnight'],capture_output=True,text=True)
            self.assertEqual(r.returncode,0,r.stderr)
            self.assertTrue((Path(d)/'result/diagram.svg').is_file())

    def test_frozen_prompt(self):
        record=load_json(ROOT/'docs/architecture-diagram/prompt-freeze.json')
        self.assertEqual(hashlib.sha256((ROOT/'prompts/architecture-diagram/prompt.md').read_bytes()).hexdigest(),record['sha256'])


if __name__=='__main__':unittest.main()
