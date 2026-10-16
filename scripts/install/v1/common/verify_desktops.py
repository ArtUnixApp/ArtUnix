#!/usr/bin/env python3
"""Resolve each advertised desktop against native repositories without installing it."""
import json
from pathlib import Path
import subprocess
from unittest.mock import patch
import environment_install
from package_manager import manager


def verify():
    kind = manager()
    desktops = ['xfce4', 'lxde-core', 'lxqt-core', 'kde-plasma-desktop',
                'mate-desktop-environment-core', 'i3-wm', 'openbox', 'icewm']
    if kind == 'apk':
        desktops.remove('lxde-core')
    native_run = subprocess.run
    results = {}
    for desktop in desktops:
        commands = []
        with patch('subprocess.run', side_effect=lambda command, **kwargs: commands.append(command)):
            environment_install.install([desktop])
        for command in commands:
            if 'update' in command:
                native_run(command, check=True)
                continue
            if kind == 'apt':
                command.insert(1, '--simulate')
            elif kind == 'apk':
                command.insert(2, '--simulate')
            elif kind == 'pacman':
                command.extend(['--print', '--print-format', '%n'])
            else:
                command.insert(1, '--assumeno')
                command.remove('-y')
            result = native_run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
            print(result.stdout, flush=True)
            # DNF intentionally aborts an otherwise valid transaction with --assumeno.
            valid_abort = kind == 'dnf' and result.returncode == 1 and 'Operation aborted' in result.stdout
            if result.returncode and not valid_abort:
                raise RuntimeError('Desktop dependency resolution failed: ' + desktop)
        results[desktop] = 'resolved'
    return results


if __name__ == '__main__':
    results = verify()
    Path('/tmp/artunix-desktop-resolution.json').write_text(json.dumps(results, indent=2) + '\n')
