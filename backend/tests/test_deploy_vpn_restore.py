"""Exercise only runtime whitelist restoration, never deploy or invoke real sudo."""
import os
from pathlib import Path
import subprocess
import pytest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts' / 'deploy-production.sh'
RESTORE = 'restore_vpn() {' + SCRIPT.read_text().split('restore_vpn() {', 1)[1].split('\n}', 1)[0] + '\n}'


def run_restore(tmp_path, original, writable=True):
    source = tmp_path / 'server.conf'; source.write_text('allow test-only;\n')
    target = tmp_path / 'runtime.conf'; target.write_text(original)
    target.chmod(0o644 if writable else 0o444)
    fake_sudo = tmp_path / 'sudo'
    fake_sudo.write_text('#!/bin/sh\n[ "$1" = -n ] || exit 10\nshift\necho sudo >> "$RESTORE_LOG"\nchmod u+w "$4"\nexec "$@"\n')
    fake_sudo.chmod(0o755)
    log = tmp_path / 'calls'
    subprocess.run(['sh', '-c', 'vpn_source=$1; vpn_target=$2;\n' + RESTORE + '\nrestore_vpn',
                    'test', str(source), str(target)], check=True,
                   env={**os.environ, 'PATH': str(tmp_path) + ':' + os.environ['PATH'], 'RESTORE_LOG': str(log)})
    assert target.read_bytes() == source.read_bytes()
    return log


@pytest.mark.skipif(os.geteuid() == 0, reason="Root bypasses file write permissions")
def test_read_only_runtime_file_uses_narrow_sudo_copy(tmp_path):
    log = run_restore(tmp_path, 'old test-only;\n', writable=False)
    assert log.read_text() == 'sudo\n'


def test_identical_runtime_rules_do_not_need_privileges(tmp_path):
    assert not run_restore(tmp_path, 'allow test-only;\n', writable=False).exists()


def test_writable_runtime_file_uses_normal_copy(tmp_path):
    assert not run_restore(tmp_path, 'old test-only;\n').exists()
