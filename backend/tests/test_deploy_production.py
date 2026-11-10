"""Exercise the whitelist migration with Git and mocked deployment services."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/deploy-production.sh'
WHITELIST = 'infra/nginx/whitelists/whitelist_vpn.conf'


@pytest.fixture
def deployment(tmp_path):
    work = tmp_path / 'work'
    work.mkdir()
    def git(*args):
        return subprocess.check_output(['git', '-C', str(work), *args], stderr=subprocess.DEVNULL).decode().strip()
    git('init', '-b', 'main')
    git('config', 'user.email', 'test@example.test')
    git('config', 'user.name', 'Deployment test')
    target = work / WHITELIST
    target.parent.mkdir(parents=True)
    target.write_text('allow 192.0.2.1;\ndeny all;\n')
    git('add', '.')
    git('commit', '-m', 'Before server-only configuration')
    old = git('rev-parse', 'HEAD')
    git('rm', WHITELIST)
    (work / '.gitignore').write_text(WHITELIST + '\n.env\n')
    git('add', '.gitignore')
    git('commit', '-m', 'Keep whitelist on server')
    revision = git('rev-parse', 'HEAD')
    git('checkout', '--detach', old)
    (work / '.env').write_text('')
    source = tmp_path / 'server-whitelist.conf'
    source.write_text('allow 192.0.2.2;\nallow 198.51.100.1;\ndeny all;\n')
    binary = tmp_path / 'bin'
    binary.mkdir()
    for name, contents in {
        'flock': '#!/bin/sh\nexit 0\n',
        'docker': '#!/bin/sh\nset -eu\ncmp "$PAGEPILOT_VPN_WHITELIST" "$PAGEPILOT_WORK_TREE/' + WHITELIST + '"\ncase "$*" in *"ps --status running --services"*) echo celery_beat;; esac\n',
    }.items():
        path = binary / name
        path.write_text(contents)
        path.chmod(0o755)
    env = {**os.environ, 'PATH': str(binary) + os.pathsep + os.environ['PATH'],
           'PAGEPILOT_REPOSITORY': str(work / '.git'), 'PAGEPILOT_WORK_TREE': str(work),
           'PAGEPILOT_VPN_WHITELIST': str(source)}
    def run():
        return subprocess.run(['sh', str(SCRIPT), revision], env=env, capture_output=True, text=True)
    return work, source, target, binary, git, revision, old, run


def test_deploy_preserves_exact_server_rules_when_git_removes_file(deployment):
    work, source, target, _, git, revision, _, run = deployment
    result = run()
    assert result.returncode == 0, result.stderr
    assert target.read_bytes() == source.read_bytes()
    assert not git('ls-files', WHITELIST)
    assert (work / '.git/deployed-revision').read_text().strip() == revision


def test_missing_server_copy_stops_before_checkout(deployment):
    work, source, target, _, git, _, old, run = deployment
    before = target.read_bytes()
    source.unlink()
    result = run()
    assert result.returncode != 0 and 'before checkout' in result.stderr
    assert git('rev-parse', 'HEAD') == old and target.read_bytes() == before
    assert not (work / '.git/deployed-revision').exists()


def test_existing_identical_whitelist_is_not_rewritten(deployment):
    _, source, target, binary, _, _, _, run = deployment
    assert run().returncode == 0
    target.chmod(0o444)
    before = target.stat().st_mtime_ns
    # A protected active file needs no write when its bytes already match.
    cp = binary / 'cp'
    cp.write_text('#!/bin/sh\nexit 77\n')
    cp.chmod(0o755)
    result = run()
    assert result.returncode == 0, result.stderr
    assert target.read_bytes() == source.read_bytes()
    assert target.stat().st_mtime_ns == before


def test_checkout_failure_restores_server_copy_without_marking_deployed(deployment):
    work, source, target, binary, _, _, _, run = deployment
    wrapper = binary / 'git'
    wrapper.write_text('#!/bin/sh\n"' + shutil.which('git') + '" "$@"\ncase "$*" in *"checkout -f main"*) exit 73;; esac\n')
    wrapper.chmod(0o755)
    result = run()
    assert result.returncode == 73
    assert target.read_bytes() == source.read_bytes()
    assert not (work / '.git/deployed-revision').exists()
