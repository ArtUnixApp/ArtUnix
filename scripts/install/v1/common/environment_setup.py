#!/usr/bin/env python3
import os
from pathlib import Path
import shlex
import subprocess
import sys


def setup(session):
    password_file = Path(sys.argv[1])
    password = password_file.read_text().strip()
    os.umask(0o077)
    config = Path('/root/.config/tigervnc')
    config.mkdir(parents=True, exist_ok=True)
    with (config / 'passwd').open('wb') as output:
        subprocess.run(['tigervncpasswd', '-f'], input=(password+'\n').encode(), stdout=output, check=True)
    startup = config / 'xstartup'
    startup.write_text('#!/bin/sh\nunset SESSION_MANAGER DBUS_SESSION_BUS_ADDRESS\n'
                       'exec dbus-launch --exit-with-session '+shlex.join(session)+'\n')
    startup.chmod(0o700)
