"""Validate the shipped JSON Schema subset, then architecture references.

No external packages. Unsupported schema keywords fail closed so a schema edit
cannot silently weaken validation. This is not a general JSON Schema engine.
"""
import argparse
import json
from pathlib import Path
import re

SCHEMA = Path(__file__).with_name('schema.json')

class ModelError(ValueError):
    pass


def load_json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ModelError('duplicate JSON key: ' + key)
            result[key] = value
        return result
    return json.loads(Path(path).read_text(encoding='utf-8'), object_pairs_hook=pairs)


def _shape(value, spec, root, path='$'):
    allowed = {'$schema', '$defs', '$ref', 'type', 'const', 'enum', 'properties',
               'additionalProperties', 'required', 'items', 'minItems', 'maxItems',
               'minLength', 'maxLength', 'pattern'}
    if set(spec) - allowed:
        raise ModelError('unsupported schema keyword')
    if '$ref' in spec:
        return _shape(value, root['$defs'][spec['$ref'].split('/')[-1]], root, path)
    if 'const' in spec and value != spec['const']:
        raise ModelError(path + ': incorrect version/value')
    if 'enum' in spec and value not in spec['enum']:
        raise ModelError(path + ': invalid enum')
    kinds = spec.get('type', [])
    if isinstance(kinds, str): kinds = [kinds]
    checks = {'object': type(value) is dict, 'array': type(value) is list,
              'string': type(value) is str, 'null': value is None}
    if kinds and not any(checks.get(k, False) for k in kinds):
        raise ModelError(path + ': incorrect type')
    if isinstance(value, dict):
        props = spec.get('properties', {})
        if set(spec.get('required', [])) - value.keys():
            raise ModelError(path + ': missing required fields')
        if spec.get('additionalProperties') is False and value.keys() - props.keys():
            raise ModelError(path + ': unknown fields')
        for key, item in value.items():
            if key in props: _shape(item, props[key], root, path + '.' + key)
    if isinstance(value, list):
        if not spec.get('minItems', 0) <= len(value) <= spec.get('maxItems', 100000):
            raise ModelError(path + ': unsupported size')
        for index, item in enumerate(value):
            _shape(item, spec['items'], root, f'{path}[{index}]')
    if isinstance(value, str):
        if not spec.get('minLength', 0) <= len(value) <= spec.get('maxLength', 100000):
            raise ModelError(path + ': invalid text length')
        if 'pattern' in spec and re.search(spec['pattern'], value) is None:
            raise ModelError(path + ': invalid identifier')
        if not value.strip() or any(not (c in '\n\t\r' or 0x20 <= ord(c) <= 0xD7FF or 0xE000 <= ord(c) <= 0xFFFD or 0x10000 <= ord(c) <= 0x10FFFF) for c in value):
            raise ModelError(path + ': empty text or control characters')


def validate(model):
    schema = load_json(SCHEMA)
    _shape(model, schema, schema)
    all_ids = {}
    for section in ('sources', 'boundaries', 'groups', 'nodes', 'relations', 'questions'):
        for item in model[section]:
            if item['id'] in all_ids: raise ModelError('IDs must be globally unique: ' + item['id'])
            all_ids[item['id']] = item
    sources = {x['id'] for x in model['sources']}
    boundaries = {x['id'] for x in model['boundaries']}
    groups = {x['id'] for x in model['groups']}
    nodes = {x['id'] for x in model['nodes']}
    issues = []
    uncertain = set()
    for section in ('boundaries', 'groups', 'nodes', 'relations'):
        for item in model[section]:
            ev = item['evidence']
            if not set(ev['sources']) <= sources: raise ModelError('unknown evidence source: ' + item['id'])
            if ev['status'] == 'explicit' and not ev['sources']:
                raise ModelError('explicit evidence needs source: ' + item['id'])
            if ev['status'] != 'explicit':
                uncertain.add(item['id'])
                issues.append({'code':'unconfirmed-evidence', 'id':item['id'], 'status':ev['status']})
    for group in model['groups']:
        if group['boundary'] is not None and group['boundary'] not in boundaries:
            raise ModelError('unknown boundary: ' + group['id'])
        if not any(n['group'] == group['id'] for n in model['nodes']):
            raise ModelError('empty group: ' + group['id'])
    for boundary in boundaries:
        if not any(g['boundary'] == boundary for g in model['groups']):
            raise ModelError('empty boundary: ' + boundary)
    for node in model['nodes']:
        if node['group'] not in groups: raise ModelError('unknown group: ' + node['id'])
    signatures = set()
    for edge in model['relations']:
        if edge['source'] not in nodes or edge['target'] not in nodes:
            raise ModelError('dangling relation: ' + edge['id'])
        if edge['type'] == 'contains':
            raise ModelError('use node.group and group.boundary for containment, not a flow edge')
        ends = (edge['source'], edge['target'])
        if edge['direction'] == 'bidirectional': ends = tuple(sorted(ends))
        signature = (*ends, edge['type'], edge['direction'], edge['label'])
        if signature in signatures: raise ModelError('duplicate relation: ' + edge['id'])
        signatures.add(signature)
    covered = set()
    for question in model['questions']:
        if not set(question['related_ids']) <= all_ids.keys(): raise ModelError('question references missing ID')
        covered.update(question['related_ids'])
    if uncertain - covered:
        raise ModelError('inferred/unknown items require a linked question: ' + ', '.join(sorted(uncertain-covered)))
    return issues


def main():
    p = argparse.ArgumentParser(description=__doc__); p.add_argument('input')
    args = p.parse_args()
    try:
        warnings = validate(load_json(args.input))
    except (ValueError, OSError) as exc:
        p.exit(2, 'Invalid model: ' + str(exc) + '\n')
    print(json.dumps({'valid':True,'warnings':warnings}, ensure_ascii=False, indent=2))

if __name__ == '__main__': main()
