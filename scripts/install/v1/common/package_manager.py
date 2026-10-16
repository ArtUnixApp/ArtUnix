#!/usr/bin/env python3
"""Native package commands; signatures remain enabled for every distribution."""
from pathlib import Path
import subprocess


def distribution():
    fields = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
    return fields['ID'].strip('"')


def manager():
    distro = distribution()
    if distro in ('debian', 'ubuntu', 'kali'):
        return 'apt'
    if distro in ('arch', 'archarm'):
        return 'pacman'
    if distro == 'fedora':
        return 'dnf'
    if distro == 'alpine':
        return 'apk'
    raise ValueError('Unsupported distribution: ' + distro)


def install(packages, refresh=True):
    kind = manager()
    if kind == 'apt':
        if refresh:
            subprocess.run(['apt-get', 'update'], check=True)
        command = ['apt-get', '-y', '--no-install-recommends', 'install']
    elif kind == 'pacman':
        # Never refresh Arch metadata without a full upgrade (partial upgrades break ABI).
        command = ['pacman', '-Syu' if refresh else '-S', '--needed', '--noconfirm']
    elif kind == 'dnf':
        command = ['dnf', '-y', '--setopt=install_weak_deps=False', 'install']
    else:
        command = ['apk', 'add', '--no-cache']
    subprocess.run(command + list(packages), check=True)


def account_packages():
    return {'apt': ['sudo', 'passwd', 'bash'], 'pacman': ['sudo', 'shadow', 'bash'],
            'dnf': ['sudo', 'shadow-utils', 'bash'], 'apk': ['sudo', 'shadow', 'bash']}[manager()]


def service_packages(service):
    kind = manager()
    if service == 'ssh':
        return ['openssh' if kind == 'pacman' else 'openssh-server']
    return {'apt': ['pulseaudio', 'pulseaudio-utils', 'libasound2-plugins'],
            'pacman': ['pulseaudio', 'alsa-plugins'],
            'dnf': ['pulseaudio', 'pulseaudio-utils', 'alsa-plugins-pulseaudio'],
            'apk': ['pulseaudio', 'pulseaudio-utils', 'alsa-plugins-pulse']}[kind]
