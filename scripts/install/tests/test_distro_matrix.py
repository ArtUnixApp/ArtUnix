import importlib.util
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

COMMON = Path(__file__).resolve().parents[1] / 'v1/common'
sys.path.insert(0, str(COMMON))
import package_manager
import environment_install
import package_recovery


class DistroMatrixTests(unittest.TestCase):
    def test_every_desktop_resolves_to_native_package_command(self):
        desktops = ['xfce4', 'lxde-core', 'lxqt-core', 'kde-plasma-desktop',
                    'mate-desktop-environment-core', 'i3-wm', 'openbox', 'icewm']
        for distro, command in [('debian', 'apt-get'), ('ubuntu', 'apt-get'), ('kali', 'apt-get'),
                                ('archarm', 'pacman'), ('fedora', 'dnf'), ('alpine', 'apk')]:
            for desktop in desktops:
                if distro == 'alpine' and desktop == 'lxde-core':
                    continue
                with self.subTest(distro=distro, desktop=desktop), \
                        patch.object(package_manager, 'distribution', return_value=distro), \
                        patch('subprocess.run') as run:
                    environment_install.install([desktop])
                    argv = run.call_args.args[0]
                    self.assertEqual(argv[0], command)
                    self.assertNotIn('--allow-untrusted', argv)
                    self.assertNotIn('--nogpgcheck', argv)
                    if command == 'pacman':
                        self.assertIn('-Syu', argv)
                    if desktop == 'kde-plasma-desktop' and command == 'dnf':
                        self.assertIn('kwin-x11', argv)
                        self.assertTrue(any('x11' in value and 'plasma' in value for value in argv))
                    if desktop == 'kde-plasma-desktop' and command in ('pacman', 'apk'):
                        self.assertIn('weston', argv)
                        self.assertIn('kwin', argv)

    def test_alpine_lxde_is_rejected_before_package_changes(self):
        with patch.object(package_manager, 'distribution', return_value='alpine'), patch('subprocess.run') as run:
            with self.assertRaisesRegex(ValueError, 'unavailable'):
                environment_install.install(['lxde-core'])
            run.assert_not_called()

    def test_non_apt_health_checks_never_call_dpkg(self):
        for distro, command in [('arch', ['pacman', '-Dk']), ('fedora', ['dnf', 'check']), ('alpine', ['apk', 'add', '--simulate', '--no-network'])]:
            with self.subTest(distro=distro), patch.object(package_manager, 'distribution', return_value=distro), \
                    patch.object(package_recovery, 'run', return_value=(0, '')) as run:
                package_recovery.check()
                run.assert_called_once_with(command)
                with self.assertRaises(package_recovery.PackageFailure):
                    package_recovery.recover('broken transaction')
                run.assert_called_once_with(command)

    def test_non_apt_account_tools_and_services(self):
        for distro in ('arch', 'fedora', 'alpine'):
            with self.subTest(distro=distro), patch.object(package_manager, 'distribution', return_value=distro):
                self.assertIn('sudo', package_manager.account_packages())
                self.assertIn('bash', package_manager.account_packages())
                self.assertTrue(package_manager.service_packages('ssh'))
                self.assertIn('pulseaudio', package_manager.service_packages('audio'))

    def test_apk_health_check_rejects_unfinished_dependency_plan(self):
        with patch.object(package_manager, 'distribution', return_value='alpine'), \
                patch.object(package_recovery, 'run', return_value=(0, '(1/1) Installing missing-dependency (1.0)')):
            with self.assertRaisesRegex(package_recovery.PackageFailure, 'incomplete dependency'):
                package_recovery.check()

    def test_unknown_distribution_stops_before_installing(self):
        with patch.object(package_manager, 'distribution', return_value='unknown'), patch('subprocess.run') as run:
            with self.assertRaises(ValueError):
                package_manager.install(['bash'])
            run.assert_not_called()
