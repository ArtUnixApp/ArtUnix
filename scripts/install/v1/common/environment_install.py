#!/usr/bin/env python3
import subprocess


def install(packages):
    subprocess.run(['apt-get', '-o', 'APT::Status-Fd=1', 'update'], check=True)
    subprocess.run(['apt-get', '-o', 'APT::Status-Fd=1', '-o', 'Dpkg::Progress-Fancy=0', '-y',
                    '--no-install-recommends', 'install', 'dbus-x11', 'tigervnc-standalone-server',
                    'tigervnc-tools', 'xfonts-base', *packages], check=True)
