import importlib.util
from pathlib import Path
import unittest
import sys
import tempfile
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[1] / 'v1/common/package_recovery.py'
sys.path.insert(0, str(SOURCE.parent))
spec = importlib.util.spec_from_file_location('package_recovery', SOURCE)
recovery = importlib.util.module_from_spec(spec)
spec.loader.exec_module(recovery)


class RecoveryTests(unittest.TestCase):
    def setUp(self):
        distro = patch('package_manager.distribution', return_value='debian')
        distro.start()
        self.addCleanup(distro.stop)
    def test_real_subprocess_failure_is_streamed_and_original_recipe_resumes(self):
        with tempfile.TemporaryDirectory() as directory:
            marker = Path(directory) / 'attempt'
            script = Path(directory) / 'recipe.py'
            script.write_text(
                'from pathlib import Path\nimport sys\n'
                'marker=Path(sys.argv[1])\n'
                'if not marker.exists():\n'
                ' marker.write_text("first")\n'
                ' print("dpkg was interrupted", flush=True)\n'
                ' sys.exit(1)\n'
                'marker.write_text("resumed")\nprint("pmstatus:1:100:configured", flush=True)\n')
            with patch.object(recovery, 'check') as check, patch.object(recovery, 'recover') as repair:
                recovery.execute([sys.executable, str(script), str(marker)])
            repair.assert_called_once()
            self.assertIn('dpkg was interrupted', repair.call_args.args[0])
            self.assertEqual(marker.read_text(), 'resumed')
            check.assert_called_once()

    def test_interrupted_install_repairs_and_retries_original_recipe_once(self):
        commands = []
        original = ['python3', 'desktop/install.py']

        def run(command, required=True):
            commands.append(command)
            if command == original and commands.count(original) == 1:
                raise recovery.PackageFailure('dpkg was interrupted')
            return 0, ''

        with patch.object(recovery, 'run', side_effect=run):
            recovery.execute(original)
        self.assertEqual(commands.count(original), 2)
        self.assertIn(['dpkg', '--configure', '-a'], commands)
        repair = next(command for command in commands if '--fix-broken' in command)
        self.assertIn('--no-remove', repair)
        self.assertEqual(commands[-1][-1], 'check')

    def test_corrupt_archive_is_cleaned_before_repair(self):
        with patch.object(recovery, 'run', return_value=(0, '')) as run:
            recovery.recover('Hash Sum mismatch: corrupt archive')
        self.assertEqual(run.call_args_list[0].args[0][-1], 'clean')

    def test_second_failure_stops_without_infinite_retry(self):
        with patch.object(recovery, 'run', side_effect=recovery.PackageFailure('bad package')) as run, \
                patch.object(recovery, 'recover') as repair:
            with self.assertRaises(recovery.PackageFailure):
                recovery.execute(['recipe'])
        self.assertEqual(run.call_count, 2)
        repair.assert_called_once()

    def test_disk_full_and_locks_do_not_trigger_repair(self):
        for reason in ('No space left on device', 'Could not get lock /var/lib/dpkg/lock'):
            with self.subTest(reason=reason), patch.object(recovery, 'run') as run:
                with self.assertRaisesRegex(recovery.PackageFailure, 'Free device storage or wait'):
                    recovery.recover(reason)
                run.assert_not_called()

    def test_database_corruption_preserves_database(self):
        with patch.object(recovery, 'run') as run:
            with self.assertRaisesRegex(recovery.PackageFailure, 'manual recovery'):
                recovery.recover('dpkg: error: parsing file /var/lib/dpkg/status')
            run.assert_not_called()

    def test_dpkg_audit_output_blocks_completion_even_with_zero_exit(self):
        with patch.object(recovery, 'run', return_value=(0, 'package is only half configured')):
            with self.assertRaisesRegex(recovery.PackageFailure, 'still require configuration'):
                recovery.check()

    def test_healthy_resume_does_not_reinstall_or_refresh(self):
        with patch.object(recovery, 'run', return_value=(0, '')) as run:
            recovery.main(['--resume'])
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args_list[-1].args[0][-1], 'check')

    def test_failed_repair_does_not_rerun_recipe_or_claim_success(self):
        with patch.object(recovery, 'run', side_effect=recovery.PackageFailure('interrupted')) as run, \
                patch.object(recovery, 'recover', side_effect=recovery.PackageFailure('offline')):
            with self.assertRaisesRegex(recovery.PackageFailure, 'offline'):
                recovery.execute(['recipe'])
        self.assertEqual(run.call_count, 1)


if __name__ == '__main__':
    unittest.main()
