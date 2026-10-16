#!/usr/bin/env python3
import os
from pathlib import Path
import shlex
import subprocess
import sys
import shutil
from package_manager import distribution


def setup(session):
    password_file = Path(sys.argv[1])
    password = password_file.read_text().strip()
    os.umask(0o077)
    config = Path('/root/.config/tigervnc')
    config.mkdir(parents=True, exist_ok=True)
    with (config / 'passwd').open('wb') as output:
        subprocess.run([shutil.which('tigervncpasswd') or 'vncpasswd', '-f'], input=(password+'\n').encode(), stdout=output, check=True)
    desktop = Path('/root/.config/artunix')
    desktop.mkdir(parents=True, exist_ok=True)
    if session == ['startplasma-x11'] and distribution() in ('alpine', 'arch', 'archarm'):
        shutil.copyfile(Path(__file__).with_name('plasma_wayland.py'), desktop / 'plasma-wayland.py')
        session = ['python3', '/root/.config/artunix/plasma-wayland.py']
        # The configured user gets a copy of this directory during account setup.
        command = 'python3 "$HOME/.config/artunix/plasma-wayland.py"'
    else:
        command = shlex.join(session)
    startup = desktop / 'xstartup'
    startup.write_text('#!/bin/sh\nunset SESSION_MANAGER DBUS_SESSION_BUS_ADDRESS\n'
                       'exec dbus-launch --exit-with-session '+command+'\n')
    startup.chmod(0o700)
