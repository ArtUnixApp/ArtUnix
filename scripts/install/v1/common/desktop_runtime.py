#!/usr/bin/env python3
"""Migrate desktop launchers without changing the configured desktop environment."""
import re
import subprocess
import sys
from pathlib import Path
import shutil


def cleanup():
    # The registry is private to this instance and HOME. Never pkill across guests.
    if not shutil.which('tigervncserver'):
        return
    result = subprocess.run(['tigervncserver', '-kill', ':*', '-clean'],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    print(result.stdout, end='', flush=True)
    listing = subprocess.run(['tigervncserver', '-list', '-cleanstale'],
                             stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, check=True)
    print(listing.stdout, end='', flush=True)
    if re.search(r'^\s*:?\d+\s+\d+\s+\d+', listing.stdout, re.MULTILINE):
        raise RuntimeError('An old VNC server is still running; refusing to start another')


def prepare():
    cleanup()
    config = Path.home() / '.config/artunix'
    config.mkdir(parents=True, exist_ok=True)
    startup = config / 'xstartup'
    if not startup.exists():
        for old in (Path.home() / '.config/tigervnc/xstartup', Path.home() / '.vnc/xstartup'):
            if old.is_file():
                shutil.copyfile(old, startup)
                break
    if not startup.is_file():
        raise RuntimeError('Desktop startup script is missing')
    startup.chmod(0o700)


def dependencies(network=False, kde=False):
    from package_manager import manager, install
    kind = manager()
    if kind != 'apt':
        # Installed with the desktop; avoid modifying rolling guests at every launch.
        required = ['dbus-launch'] + (['x11vnc'] if network else [])
        if any(not shutil.which(command) for command in required):
            install((['dbus', 'x11vnc'] if kind == 'pacman' else ['dbus-x11', 'x11vnc']))
        return
    packages = ['xkb-data', 'libvulkan1', 'libdrm2', 'libx11-xcb1', 'libxcb-glx0',
                'libxcb-dri3-0', 'libxcb-present0', 'libxcb-sync1', 'libxcb-xfixes0',
                'libxshmfence1', 'libxxf86vm1']
    if network:
        packages.append('x11vnc')
    if kde:
        packages.append('kwin-x11')
    missing = []
    for package in packages:
        result = subprocess.run(['dpkg-query', '-W', '-f=${Status}', package], capture_output=True, text=True)
        if result.returncode or result.stdout != 'install ok installed':
            missing.append(package)
    if missing:
        subprocess.run(['apt-get', 'update'], check=True)
        subprocess.run(['apt-get', '-y', '--no-install-recommends', 'install', *missing], check=True)


if __name__ == '__main__':
    if sys.argv[1] == 'dependencies':
        dependencies('--network' in sys.argv[2:], '--kde' in sys.argv[2:])
    elif sys.argv[1] == 'prepare':
        prepare()
    elif sys.argv[1] == 'cleanup':
        cleanup()
    else:
        raise ValueError('Unknown desktop runtime action')
