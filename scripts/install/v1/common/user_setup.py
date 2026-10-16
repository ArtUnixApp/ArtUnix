#!/usr/bin/env python3
"""Create the configured Linux account without exposing passwords in arguments or logs."""
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
from package_manager import install, account_packages


def secure_sudoers(sudoers):
    # Rootfs/package-provided snippets (including Ubuntu's README) must meet
    # sudo's mode checks too. Preserve their contents and keep validation strict.
    sudoers.chmod(0o755)
    main = sudoers.parent / 'sudoers'
    for config in [main, *sudoers.iterdir()]:
        if config.is_file() and not config.is_symlink():
            config.chmod(0o440)


def permissions(username):
    install(account_packages())
    subprocess.run(['groupadd', '--force', 'sudo'], check=True)
    subprocess.run(['usermod', '--append', '--groups', 'sudo', username], check=True)
    sudoers = Path('/etc/sudoers.d')
    sudoers.mkdir(parents=True, exist_ok=True)
    rule = sudoers / ('artunix-' + username)
    rule.write_text(username + ' ALL=(ALL:ALL) ALL\n')
    secure_sudoers(sudoers)
    subprocess.run(['visudo', '--check', '--file', str(rule)], check=True)
    subprocess.run(['visudo', '--check'], check=True)


def setup(credentials):
    data = json.loads(Path(credentials).read_text())
    username, password = data['username'], data['password']
    if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', username) or username in ('root', 'daemon', 'nobody'):
        raise ValueError('Invalid Linux username')
    if not 6 <= len(password) <= 128 or any(ord(c) < 32 or ord(c) == 127 for c in password):
        raise ValueError('Invalid Linux password')
    try:
        account = pwd.getpwnam(username)
    except KeyError:
        install(account_packages())
        subprocess.run(['useradd', '--create-home', '--shell', '/bin/bash', username], check=True)
        account = pwd.getpwnam(username)
    if account.pw_uid < 1000 or account.pw_dir != '/home/' + username:
        raise ValueError('Username belongs to an existing system account')
    permissions(username)
    # The secret is passed through stdin, never through command arguments.
    subprocess.run(['chpasswd', '--crypt-method', 'SHA512'], input=(username + ':' + password + '\n').encode(),
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=True)
    home = Path(account.pw_dir)
    home.mkdir(parents=True, exist_ok=True)
    for relative in ('.config/artunix', '.config/tigervnc', '.config/pulse', '.config/GIMP'):
        source = Path('/root') / relative
        if source.is_dir():
            shutil.copytree(source, home / relative, dirs_exist_ok=True)
    for path in [home, *home.rglob('*')]:
        if not path.is_symlink():
            os.chown(path, account.pw_uid, account.pw_gid)
    home.chmod(0o700)


if __name__ == '__main__':
    if sys.argv[1] == '--permissions':
        username = sys.argv[2]
        account = pwd.getpwnam(username)
        if not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', username) or account.pw_uid < 1000 or account.pw_dir != '/home/' + username:
            raise ValueError('Invalid Linux account')
        permissions(username)
    else:
        setup(sys.argv[1])
