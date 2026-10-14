import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

COMMON = Path(__file__).resolve().parents[1] / 'v1/common'


def load(name):
    spec = importlib.util.spec_from_file_location(name, COMMON / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ScriptTests(unittest.TestCase):
    def test_bad_download_checksum_never_extracts_or_marks_rootfs(self):
        module = load('distro_install')
        with tempfile.TemporaryDirectory() as folder:
            root, cache = Path(folder) / 'root', Path(folder) / 'cache'
            response = io.BytesIO(b'corrupt rootfs')
            response.url = 'https://example.test/rootfs'
            with patch.object(sys, 'argv', ['install.py', str(root), str(cache)]), \
                    patch.object(module.urllib.request, 'urlopen', return_value=response), \
                    patch.object(module.subprocess, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'checksum mismatch'):
                    module.install(response.url, '0' * 64, 'rootfs')
                self.assertFalse((root / '.artunix-rootfs').exists())
                self.assertFalse(list(cache.glob('*.partial')))
                self.assertFalse(any(call.args[0][0] == 'tar' for call in run.call_args_list))

    def test_retry_rejects_changed_rootfs_recipe(self):
        module = load('distro_install')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'root'
            root.mkdir()
            (root / '.artunix-rootfs').write_text('old recipe digest')
            with patch.object(sys, 'argv', ['install.py', str(root), str(Path(folder) / 'cache')]), \
                    patch.object(module.subprocess, 'run') as run:
                with self.assertRaisesRegex(RuntimeError, 'does not match'):
                    module.install('https://example.test/rootfs', '0' * 64, 'rootfs')
                run.assert_not_called()

    def test_package_failure_propagates(self):
        module = load('environment_install')
        with patch.object(module.subprocess, 'run', side_effect=subprocess.CalledProcessError(100, 'apt-get')):
            with self.assertRaises(subprocess.CalledProcessError):
                module.install(['xfce4'])

    def test_vnc_setup_writes_selected_session_and_uses_password_stdin(self):
        module = load('environment_setup')
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'tigervnc'
            password = Path(folder) / 'password'
            password.write_text('secret12')
            original_path = Path
            def resolve(value):
                return config if value == '/root/.config/tigervnc' else original_path(value)
            with patch.object(sys, 'argv', ['setup.py', str(password)]), \
                    patch.object(module, 'Path', side_effect=resolve), \
                    patch.object(module.os, 'umask'), patch.object(module.subprocess, 'run') as run:
                module.setup(['startlxqt'])
                self.assertIn('exec dbus-launch --exit-with-session startlxqt', (config / 'xstartup').read_text())
                self.assertEqual(run.call_args.kwargs['input'], b'secret12\n')
                self.assertNotIn('secret12', str(run.call_args.args))


if __name__ == '__main__':
    unittest.main()
