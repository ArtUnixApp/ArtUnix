#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys


def setup(expected_id):
    release = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    if release.get('ID', '').strip('"') != expected_id:
        raise RuntimeError('Unexpected distribution identity')
    if subprocess.check_output(['dpkg', '--print-architecture'], text=True).strip() != 'arm64':
        raise RuntimeError('Expected ARM64 distribution')
    resolv = Path('/etc/resolv.conf')
    resolv.unlink(missing_ok=True)
    resolv.write_text(''.join(f'nameserver {address}\n' for address in sys.argv[1:]))
    policy = Path('/usr/sbin/policy-rc.d')
    policy.write_text('#!/bin/sh\nexit 101\n')
    policy.chmod(0o755)
    Path('/tmp').mkdir(exist_ok=True)
    Path('/tmp').chmod(0o1777)
    Path('/root/.vnc').mkdir(parents=True, exist_ok=True)
