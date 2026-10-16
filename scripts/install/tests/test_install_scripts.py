import importlib.util
import io
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch, Mock

COMMON = Path(__file__).resolve().parents[1] / 'v1/common'
sys.path.insert(0, str(COMMON))


def load(name):
    spec = importlib.util.spec_from_file_location(name, COMMON / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ScriptTests(unittest.TestCase):
    def setUp(self):
        self.distro = patch('package_manager.distribution', return_value='debian')
        self.distro.start()
        self.addCleanup(self.distro.stop)
    def test_user_creation_sets_password_via_stdin_and_copies_vnc(self):
        # pwd is supplied by Linux in the guest; this test also runs on Windows.
        import types
        with patch.dict(sys.modules, {'pwd': types.SimpleNamespace(getpwnam=Mock())}):
            module = load('user_setup')
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            credentials = base / 'credentials.json'
            credentials.write_text('{"username":"alice","password":"p:a ssword"}')
            source = base / 'root/.config/tigervnc'
            source.mkdir(parents=True); (source / 'passwd').write_bytes(b'encrypted-vnc')
            (source / 'xstartup').write_text('exec startxfce4')
            account = types.SimpleNamespace(pw_uid=1000, pw_gid=1000, pw_dir='/home/alice')
            def resolve(value):
                if str(value) == '/etc/sudoers.d':
                    return base / 'etc/sudoers.d'
                if str(value) == '/root':
                    return base / 'root'
                if str(value) == '/home/alice':
                    return base / 'home/alice'
                return Path(value)
            with patch.object(module.pwd, 'getpwnam', side_effect=[KeyError(), account]), \
                    patch.object(module, 'Path', side_effect=resolve), \
                    patch.object(module.os, 'chown', create=True), patch.object(module.subprocess, 'run') as run:
                module.setup(credentials)
                self.assertIn(['useradd','--create-home','--shell','/bin/bash','alice'],
                              [call.args[0] for call in run.call_args_list])
                commands = [call.args[0] for call in run.call_args_list]
                self.assertIn(['apt-get', '-y', '--no-install-recommends', 'install', 'sudo', 'passwd', 'bash'], commands)
                self.assertIn(['usermod', '--append', '--groups', 'sudo', 'alice'], commands)
                self.assertIn(['visudo', '--check'], commands)
                self.assertEqual((base / 'etc/sudoers.d/artunix-alice').read_text(), 'alice ALL=(ALL:ALL) ALL\n')
                password_call = next(call for call in run.call_args_list if call.args[0][0]=='chpasswd')
                self.assertEqual(password_call.kwargs['input'], b'alice:p:a ssword\n')
                self.assertNotIn('p:a ssword', str(password_call.args))
                self.assertEqual((base / 'home/alice/.config/tigervnc/passwd').read_bytes(), b'encrypted-vnc')
                self.assertNotIn('p:a ssword', (base / 'home/alice/.config/tigervnc/xstartup').read_text())

    def test_sudoers_modes_include_ubuntu_readme_and_preserve_contents(self):
        import types
        with patch.dict(sys.modules, {'pwd': types.SimpleNamespace(getpwnam=Mock())}):
            module = load('user_setup')
        with tempfile.TemporaryDirectory() as folder:
            base = Path(folder)
            snippets = base / 'sudoers.d'
            snippets.mkdir()
            contents = {'sudoers': '@includedir /etc/sudoers.d\n',
                        'sudoers.d/README': '# Ubuntu sudo configuration\n',
                        'sudoers.d/artunix-alice': 'alice ALL=(ALL:ALL) ALL\n'}
            for name, text in contents.items():
                (base / name).write_text(text)
            (snippets / 'directory').mkdir()
            with patch.object(Path, 'chmod', autospec=True) as chmod:
                module.secure_sudoers(snippets)
            modes = {call.args[0]: call.args[1] for call in chmod.call_args_list}
            self.assertEqual(modes[snippets], 0o755)
            for name, text in contents.items():
                self.assertEqual(modes[base / name], 0o440)
                self.assertEqual((base / name).read_text(), text)
            self.assertNotIn(snippets / 'directory', modes)
            with patch.object(Path, 'chmod', autospec=True) as chmod:
                module.secure_sudoers(snippets)
            self.assertEqual(modes, {call.args[0]: call.args[1] for call in chmod.call_args_list})

    def test_user_setup_rejects_system_accounts(self):
        import types
        with patch.dict(sys.modules, {'pwd': types.SimpleNamespace(getpwnam=Mock())}):
            module = load('user_setup')
        with tempfile.TemporaryDirectory() as folder:
            credentials = Path(folder) / 'credentials.json'
            credentials.write_text('{"username":"syslog","password":"secret123"}')
            account = types.SimpleNamespace(pw_uid=101,pw_gid=101,pw_dir='/var/log')
            with patch.object(module.pwd,'getpwnam',return_value=account), \
                    patch.object(module.subprocess,'run') as run:
                with self.assertRaisesRegex(ValueError,'system account'):
                    module.setup(credentials)
                run.assert_not_called()

    def test_extracts_hardlinks_as_files_without_os_link(self):
        import tarfile
        import os
        module=load('distro_install')
        with tempfile.TemporaryDirectory() as directory:
            archive=Path(directory)/'root.tar.xz'
            root=Path(directory)/'root'
            root.mkdir()
            with tarfile.open(archive,'w:xz') as tar:
                original=tarfile.TarInfo('rootfs/usr/bin/tool')
                original.size=4; original.mode=0o755
                tar.addfile(original,io.BytesIO(b'tool'))
                duplicate=tarfile.TarInfo('rootfs/usr/bin/tool-copy')
                duplicate.type=tarfile.LNKTYPE; duplicate.linkname=original.name; duplicate.mode=0o755
                tar.addfile(duplicate)
            with patch.object(os,'link',side_effect=PermissionError('Android linkat denied')):
                module.extract_rootfs(archive,root,'rootfs')
            self.assertEqual((root/'usr/bin/tool-copy').read_bytes(),b'tool')

    def test_rejects_traversal_archive_entries(self):
        import tarfile
        module=load('distro_install')
        with tempfile.TemporaryDirectory() as directory:
            archive=Path(directory)/'root.tar.xz'
            root=Path(directory)/'root'; root.mkdir()
            with tarfile.open(archive,'w:xz') as tar:
                item=tarfile.TarInfo('rootfs/../outside'); item.size=4
                tar.addfile(item,io.BytesIO(b'evil'))
            with self.assertRaisesRegex(ValueError,'archive path'):
                module.extract_rootfs(archive,root,'rootfs')
            self.assertFalse((Path(directory)/'outside').exists())
    def release_fixture(self, module, distro='debian', suite='trixie'):
        top = f'artunix-{distro}-{suite}-arm64'
        names = ['rootfs-manifest.json', top+'.tar.xz']
        release = {'tag_name': 'rootfs-2026-10', 'draft': False, 'prerelease': False,
                   'assets': [{'name': name, 'browser_download_url':
                               f'https://github.com/{module.REPOSITORY}/releases/download/rootfs-2026-10/{name}'} for name in names]}
        manifest = {'schemaVersion': 1, 'architecture': 'arm64', 'distros': {
            distro: {'asset': top+'.tar.xz', 'sha256': 'a'*64, 'top': top}}}
        return release, manifest

    def test_pending_distro_release_names_include_dotted_alpine_version(self):
        module = load('distro_install')
        for distro, suite in [('kali', 'rolling'), ('arch', 'rolling'), ('fedora', '44'), ('alpine', '3.23')]:
            with self.subTest(distro=distro):
                release, manifest = self.release_fixture(module, distro, suite)
                with patch.object(module, 'read_json', side_effect=[release, manifest]):
                    source = module.latest_rootfs(distro)
                self.assertEqual(source['top'], f'artunix-{distro}-{suite}-arm64')

    def test_dotted_version_support_still_rejects_path_prefixes(self):
        module = load('distro_install')
        for top in ('../artunix-alpine-3.23-arm64', 'artunix-alpine-../../outside-arm64', 'artunix-fedora-44-arm64'):
            release, manifest = self.release_fixture(module, 'alpine', '3.23')
            manifest['distros']['alpine'].update(top=top, asset=top+'.tar.xz')
            with self.subTest(top=top), patch.object(module, 'read_json', side_effect=[release, manifest]):
                with self.assertRaises(ValueError):
                    module.latest_rootfs('alpine')

    def test_latest_release_uses_matching_asset_and_manifest_checksum(self):
        module = load('distro_install')
        release, manifest = self.release_fixture(module)
        with patch.object(module, 'read_json', side_effect=[release, manifest]) as read:
            source = module.latest_rootfs('debian')
        self.assertEqual(read.call_args_list[0].args[0],
                         'https://api.github.com/repos/ArtUnixApp/ArtUnix/releases/latest')
        self.assertEqual(source['sha256'], 'a'*64)
        self.assertIn('/rootfs-2026-10/artunix-debian-trixie-arm64.tar.xz', source['url'])

    def test_latest_release_missing_archive_fails(self):
        module = load('distro_install')
        release, manifest = self.release_fixture(module)
        release['assets'].pop()
        with patch.object(module, 'read_json', side_effect=[release, manifest]):
            with self.assertRaisesRegex(RuntimeError, 'exactly one'):
                module.latest_rootfs('debian')

    def test_latest_release_invalid_checksum_fails(self):
        module = load('distro_install')
        release, manifest = self.release_fixture(module)
        manifest['distros']['debian']['sha256'] = '../bad'
        with patch.object(module, 'read_json', side_effect=[release, manifest]):
            with self.assertRaisesRegex(ValueError, 'checksum'):
                module.latest_rootfs('debian')

    def test_extracted_rootfs_retry_keeps_release_without_querying_latest(self):
        import json
        module = load('distro_install')
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder) / 'root'
            root.mkdir()
            (root / '.artunix-rootfs').write_text('a'*64)
            source = dict(distro='debian', release='old-release', url='https://example.test/rootfs', sha256='a'*64, top='rootfs')
            (root / '.artunix-rootfs-source.json').write_text(json.dumps(source))
            with patch.object(sys, 'argv', ['install.py', str(root), str(Path(folder) / 'cache')]), \
                    patch.object(module, 'latest_rootfs') as latest, patch.object(module, 'install') as install:
                module.install_latest('debian')
                latest.assert_not_called()
                install.assert_called_once_with(source['url'], source['sha256'], source['top'])

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

    def test_x11_setup_writes_selected_session_and_keeps_external_password_private(self):
        module = load('environment_setup')
        with tempfile.TemporaryDirectory() as folder:
            config = Path(folder) / 'tigervnc'
            password = Path(folder) / 'password'
            password.write_text('secret12')
            original_path = Path
            def resolve(value):
                if value == '/root/.config/tigervnc':
                    return config
                if value == '/root/.config/artunix':
                    return Path(folder) / 'artunix'
                return original_path(value)
            with patch.object(sys, 'argv', ['setup.py', str(password)]), \
                    patch.object(module, 'Path', side_effect=resolve), \
                    patch.object(module.os, 'umask'), patch.object(module.subprocess, 'run') as run:
                module.setup(['startlxqt'])
                self.assertIn('exec dbus-launch --exit-with-session startlxqt', (Path(folder) / 'artunix/xstartup').read_text())
                self.assertFalse((config / 'xstartup').exists())
                self.assertEqual(run.call_args.kwargs['input'], b'secret12\n')
                self.assertNotIn('secret12', str(run.call_args.args))

    def test_kde_dependency_check_restores_missing_x11_window_manager(self):
        module = load('desktop_runtime')
        def status(command, **kwargs):
            return Mock(returncode=1, stdout='') if command[-1]=='kwin-x11' else Mock(returncode=0, stdout='install ok installed')
        with patch.object(module.subprocess, 'run', side_effect=status) as run:
            module.dependencies(kde=True)
        commands=[call.args[0] for call in run.call_args_list]
        self.assertIn(['apt-get', '-y', '--no-install-recommends', 'install', 'kwin-x11'], commands)
        with patch.object(module.subprocess, 'run', side_effect=status) as run:
            module.dependencies()
        self.assertFalse(any(call.args[0][0]=='apt-get' for call in run.call_args_list))
        with patch.object(module.subprocess, 'run', return_value=Mock(returncode=0,stdout='install ok installed')) as run:
            module.dependencies(kde=True)
        self.assertFalse(any(call.args[0][0]=='apt-get' for call in run.call_args_list))

    def test_x11_migration_preserves_selected_desktop_and_existing_launcher(self):
        module = load('desktop_runtime')
        with tempfile.TemporaryDirectory() as folder:
            home = Path(folder)
            old = home / '.config/tigervnc/xstartup'
            old.parent.mkdir(parents=True)
            old.write_text('#!/bin/sh\nexec dbus-launch startplasma-x11\n')
            with patch.object(module.Path, 'home', return_value=home), patch.object(module, 'cleanup'):
                module.prepare()
                target = home / '.config/artunix/xstartup'
                self.assertEqual(target.read_text(), old.read_text())
                target.write_text('#!/bin/sh\nexec custom-session\n')
                module.prepare()
                self.assertIn('custom-session', target.read_text())


if __name__ == '__main__':
    unittest.main()
