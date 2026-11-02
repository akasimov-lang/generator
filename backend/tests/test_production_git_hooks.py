import os
from pathlib import Path
import subprocess
import tempfile
import unittest

HOOK = Path(__file__).resolve().parents[2] / 'scripts' / 'git-hooks' / 'pre-receive'


class ProductionGuardTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = self.root / 'repo'
        self.repo.mkdir()
        self.git('init', '-q')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.invalid')
        (self.repo / 'app.py').write_text('original\n')
        (self.repo / '.gitignore').write_text('.env\nbackups/\n')
        self.git('add', '.')
        self.git('commit', '-qm', 'baseline')
        self.old = self.git('rev-parse', 'HEAD').strip()
        (self.repo / 'app.py').write_text('next\n')
        self.git('commit', '-qam', 'next')
        self.new = self.git('rev-parse', 'HEAD').strip()
        self.git('checkout', '-q', self.old)

    def git(self, *args):
        return subprocess.check_output(['git', *args], cwd=self.repo, text=True)

    def guard(self, old=None, new=None):
        return subprocess.run(['sh', str(HOOK)], cwd=self.repo / '.git',
            input=f'{old or self.old} {new or self.new} refs/heads/main\n',
            text=True, capture_output=True,
            env={**os.environ, 'PAGEPILOT_WORK_TREE': str(self.repo)})

    def test_clean_source_allows_fast_forward_with_ignored_runtime_files(self):
        (self.repo / '.env').write_text('private runtime data')
        (self.repo / 'backups').mkdir()
        (self.repo / 'backups' / 'data').write_text('backup')
        result = self.guard()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.git('rev-parse', 'HEAD').strip(), self.old)

    def test_modified_source_blocks_deploy_without_changing_file(self):
        (self.repo / 'app.py').write_text('server-only change\n')
        result = self.guard()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('app.py', result.stderr)
        self.assertEqual((self.repo / 'app.py').read_text(), 'server-only change\n')

    def test_untracked_source_blocks_deploy(self):
        (self.repo / 'new_module.py').write_text('new module\n')
        result = self.guard()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('new_module.py', result.stderr)

    def test_non_fast_forward_is_rejected(self):
        result = self.guard(old=self.new, new=self.old)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('fast-forward', result.stderr)


if __name__ == '__main__':
    unittest.main()
