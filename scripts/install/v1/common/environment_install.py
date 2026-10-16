#!/usr/bin/env python3
import subprocess
from package_manager import manager, install as native_install


def install(packages):
    kind = manager()
    if kind != 'apt':
        profiles = {
            'pacman': {'xfce4': ['xfce4', 'xfce4-terminal'], 'i3-wm': ['i3-wm', 'i3status', 'xterm'],
                       'openbox': ['openbox', 'xterm'], 'icewm': ['icewm', 'xterm'],
                       'lxde-core': ['lxde', 'lxterminal'], 'lxqt-core': ['lxqt', 'qterminal', 'openbox'],
                       'mate-desktop-environment-core': ['mate', 'mate-terminal'],
                       'kde-plasma-desktop': ['plasma-desktop', 'plasma-workspace', 'konsole', 'kwin', 'weston', 'xorg-xwayland', 'xorg-xrandr']},
            'dnf': {'xfce4': ['xfce4-session', 'xfce4-panel', 'xfce4-settings', 'xfwm4', 'xfdesktop', 'Thunar', 'xfce4-terminal'],
                    'i3-wm': ['i3', 'i3status', 'xterm'], 'openbox': ['openbox', 'xterm'], 'icewm': ['icewm', 'xterm'],
                    'lxde-core': ['lxde-common', 'lxsession', 'lxpanel', 'pcmanfm', 'openbox', 'lxterminal'],
                    'lxqt-core': ['lxqt-session', 'lxqt-panel', 'lxqt-config', 'pcmanfm-qt', 'qterminal', 'openbox'],
                    'mate-desktop-environment-core': ['mate-session-manager', 'mate-panel', 'mate-settings-daemon', 'marco', 'caja', 'mate-terminal'],
                    'kde-plasma-desktop': ['plasma-desktop', 'plasma-workspace-x11', 'konsole', 'kwin-x11']},
            'apk': {'xfce4': ['xfce4', 'xfce4-terminal'], 'i3-wm': ['i3wm', 'i3status', 'xterm'],
                    'openbox': ['openbox', 'xterm'], 'icewm': ['icewm', 'xterm'],
                    'lxqt-core': ['lxqt-desktop', 'qterminal', 'openbox'],
                    'mate-desktop-environment-core': ['mate-desktop-environment', 'mate-terminal'],
                    'kde-plasma-desktop': ['plasma-desktop', 'plasma-workspace', 'konsole', 'kwin', 'weston',
                                           'weston-backend-x11', 'weston-shell-desktop', 'xwayland', 'xrandr']}}
        desktop = profiles.get(kind, {}).get(packages[0])
        if desktop is None:
            raise ValueError('Desktop is unavailable for this distribution')
        dependencies = {
            'pacman': ['dbus', 'x11vnc', 'tigervnc', 'xorg-fonts-misc', 'xkeyboard-config', 'vulkan-icd-loader',
                       'libdrm', 'libx11', 'libxcb', 'libxshmfence', 'libxxf86vm'],
            'dnf': ['dbus-x11', 'x11vnc', 'tigervnc', 'xorg-x11-fonts-misc', 'xkeyboard-config', 'vulkan-loader',
                    'libdrm', 'libX11', 'libxcb', 'libxshmfence', 'libXxf86vm'],
            'apk': ['dbus-x11', 'x11vnc', 'tigervnc', 'font-misc-misc', 'xkeyboard-config', 'vulkan-loader',
                    'libdrm', 'libx11', 'libxcb', 'libxshmfence', 'libxxf86vm']}
        native_install(dependencies[kind] + desktop)
        return
    subprocess.run(['apt-get', '-o', 'APT::Status-Fd=1', 'update'], check=True)
    subprocess.run(['apt-get', '-o', 'APT::Status-Fd=1', '-o', 'Dpkg::Progress-Fancy=0', '-y',
                    '--no-install-recommends', 'install', 'dbus-x11', 'x11vnc',
                    'tigervnc-tools', 'xfonts-base', 'xkb-data', 'libvulkan1', 'libdrm2',
                    'libx11-xcb1', 'libxcb-glx0', 'libxcb-dri3-0', 'libxcb-present0', 'libxcb-sync1',
                    'libxcb-xfixes0', 'libxshmfence1', 'libxxf86vm1', *packages], check=True)
