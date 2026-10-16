#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys


def setup(expected_id):
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    actual = release.get('ID', '').strip('"')
    if actual not in (('arch', 'archarm') if expected_id == 'arch' else (expected_id,)):
        raise RuntimeError('Unexpected distribution identity')
    import platform
    if platform.machine() not in ('aarch64', 'arm64'):
        raise RuntimeError('Expected ARM64 distribution')
    if expected_id == 'arch':
        # Every instance gets its own local master key; never publish a shared secret key.
        subprocess.run(['pacman-key', '--init'], check=True)
        subprocess.run(['pacman-key', '--populate', 'archlinuxarm'], check=True)
    resolv = Path('/etc/resolv.conf')
    resolv.unlink(missing_ok=True)
    resolv.write_text(''.join(f'nameserver {address}\n' for address in sys.argv[1:]))
    policy = Path('/usr/sbin/policy-rc.d')
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.write_text('#!/bin/sh\nexit 101\n')
    policy.chmod(0o755)
    Path('/tmp').mkdir(exist_ok=True)
    Path('/tmp').chmod(0o1777)
    Path('/root/.vnc').mkdir(parents=True, exist_ok=True)
