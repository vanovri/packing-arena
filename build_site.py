"""Build only public, linked static assets. Never include Git metadata or scratch files."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import render

ROOT = Path(__file__).resolve().parent
FILES = ['index.html', 'README.txt', 'RULES.txt', 'cases.json', 'results.json',
         'judge.py', 'scarlet.py', 'cobalt.py', 'jade.py', 'preview.png']


def main():
    render.main()
    target = ROOT / '_site'
    target.mkdir(exist_ok=True)
    for name in FILES:
        shutil.copyfile(ROOT / name, target / name)
    (target / '.nojekyll').touch()
    commit = os.environ.get('GITHUB_SHA') or subprocess.check_output(
        ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip()
    info = {'commit': commit, 'assets': {
        name: hashlib.sha256((target / name).read_bytes()).hexdigest() for name in FILES}}
    (target / 'build_info.json').write_text(json.dumps(info, indent=2), encoding='utf-8')
    print('Static build:', len(FILES), 'assets; source commit', commit)


if __name__ == '__main__':
    main()
