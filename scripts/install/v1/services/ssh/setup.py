#!/usr/bin/env python3
from pathlib import Path
import os
import subprocess
import sys

os.umask(0o077)
directory = Path('/root/.ssh')
directory.mkdir(parents=True, exist_ok=True)
directory.chmod(0o700)
key = Path(sys.argv[1]).read_text().strip()
if not key.startswith('ssh-ed25519 '):
    raise ValueError('An Ed25519 public key is required')
authorized = directory / 'authorized_keys'
authorized.write_text(key+'\n')
authorized.chmod(0o600)
Path('/run/sshd').mkdir(parents=True, exist_ok=True)
subprocess.run(['ssh-keygen', '-A'], check=True)
