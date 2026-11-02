"""Regenerate themes.css from the reviewed themes.json; Python standard library only."""
from pathlib import Path
import json
root = Path(__file__).resolve().parent
data = json.loads((root / "themes.json").read_text())
css = []
for theme in data["themes"]:
    css.append('[data-theme="' + theme["id"] + '"] {\n' + ''.join('  --' + k + ': ' + v + ';\n' for k, v in theme["tokens"].items()) + '}\n')
(root / "themes.css").write_text('\n'.join(css))
