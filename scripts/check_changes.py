#!/usr/bin/env python3
"""Plan/run checks for an explicit task file list. Never starts a browser."""
import argparse
import ast
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
# Cross-component contracts that are not apparent from a file's own test name.
RELATED = {
    'auto_pilot': ['auto_pilot'],
    'reglue_recheck': ['reglue_recheck', 'auto_pilot'],
    'reglue_title_h1': ['reglue_title_h1', 'reglue_recheck'],
    'homepage_headings': ['homepage_headings', 'reglue_title_h1'],
    'reglue_reserves': ['reglue_reserves'],
    'pilot_schemes': ['pilot_variations', 'auto_pilot'],
    'pilot_variations': ['pilot_variations', 'auto_pilot'],
    'subdomain_naming': ['subdomain_naming', 'pilot_subdomain_names'],
    'transfer_confirmation': ['transfer_confirmation'],
}
SHARED = {'backend/app/models.py', 'backend/app/db.py', 'backend/requirements.txt',
          'backend/tests/conftest.py', 'backend/pytest.ini'}


def module_tests(module):
    selected = set()
    own = ROOT / f'backend/tests/test_{module}.py'
    if own.exists():
        selected.add(own.relative_to(ROOT).as_posix())
    # Direct imports also cover API functions exercised from differently named tests.
    for file in sorted((ROOT / 'backend/tests').glob('test_*.py')):
        tree = ast.parse(file.read_text())
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and (
                node.module == f'app.{module}' or
                node.module == 'app' and any(a.name == module for a in node.names)
            ):
                selected.add(file.relative_to(ROOT).as_posix())
            elif isinstance(node, ast.Import) and any(a.name == f'app.{module}' for a in node.names):
                selected.add(file.relative_to(ROOT).as_posix())
    return selected


def plan(files, extra_tests=()):
    selected = set(extra_tests)
    node_tests = set()
    build = False
    selector_tests = False
    notes = []
    unresolved = []
    for name in sorted(set(files)):
        name = Path(name).as_posix().removeprefix('./')
        if name == 'scripts/check_changes.py' or name.startswith('scripts/tests/test_check_changes'):
            selector_tests = True
        elif name in SHARED or name.startswith('backend/migrations/'):
            selected.update(p.relative_to(ROOT).as_posix() for p in (ROOT / 'backend/tests').glob('test_*.py'))
            notes.append(f'{name}: изменена общая основа backend — требуется полный backend-набор.')
        elif name.startswith('backend/tests/test_') and name.endswith('.py'):
            selected.add(name)
        elif name.startswith('backend/app/') and name.endswith('.py'):
            module = Path(name).stem
            names = RELATED.get(module)
            tests = {f'backend/tests/test_{n}.py' for n in names} if names else module_tests(module)
            tests = {p for p in tests if (ROOT / p).exists()}
            if not tests and not extra_tests:
                unresolved.append(name)
            selected.update(tests)
        elif name.startswith('frontend/src/') or name in {'frontend/package.json', 'frontend/package-lock.json', 'frontend/tsconfig.json', 'frontend/vite.config.ts'}:
            build = True
            if name.endswith(('.mjs', '.ts', '.tsx')):
                stem = Path(name).stem
                test = f'frontend/tests/{stem}.test.mjs'
                if (ROOT / test).exists():node_tests.add(test)
        elif name.startswith('frontend/tests/') and name.endswith('.test.mjs'):
            node_tests.add(name)
        elif name.endswith('_browser.py') or name.startswith('frontend/tests/'):
            notes.append(f'{name}: браузерный сценарий исключён из локального автоматического запуска.')
        elif name in {'AGENTS.md','README.md'} or name.startswith(('docs/','reports/')):
            pass
        elif not extra_tests:
            unresolved.append(name)
    for test in selected:
        if not test.startswith('backend/tests/test_') or not test.endswith('.py') or not (ROOT / test).exists():
            raise ValueError(f'Недопустимый backend-тест: {test}')
    commands=[]
    if selector_tests:commands.append([sys.executable, '-m', 'unittest', 'discover', '-s', 'scripts/tests', '-p', 'test_check_changes.py'])
    if selected:commands.append([sys.executable, '-m', 'pytest', '-o', 'addopts=', *sorted(selected)])
    if node_tests:commands.append(['node', '--experimental-strip-types', '--test', *sorted(node_tests)])
    if build:commands.append(['npm', '--prefix', 'frontend', 'run', 'build'])
    return {'backend_tests':sorted(selected),'node_tests':sorted(node_tests),'frontend_build':build,
            'browser':False,'unresolved':unresolved,'notes':notes,'commands':commands}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files',nargs='+',help='Файлы только текущей задачи')
    parser.add_argument('--test',action='append',default=[],help='Дополнительный связанный backend-тест')
    parser.add_argument('--run',action='store_true')
    args=parser.parse_args()
    result=plan(args.files,args.test)
    print(json.dumps(result,ensure_ascii=False,indent=2),flush=True)
    if result['unresolved']:
        print('Укажите связанные тесты через --test для нераспознанных файлов.',file=sys.stderr)
        return 2
    if args.run:
        import os
        env={**os.environ,'PYTHONPATH':str(ROOT/'backend')}
        for command in result['commands']:
            subprocess.run(command,cwd=ROOT,env=env,check=True)
    return 0


if __name__=='__main__':
    raise SystemExit(main())
