#!/usr/bin/env python3
"""Run Wayland-only Plasma inside the instance's existing X11 display."""
import os
import re
from pathlib import Path
import subprocess
import time
import uuid


def run():
    # This short instance-owned bind avoids AF_UNIX's 108-byte host path limit
    # after PRoot prefixes guest paths with the much longer rootfs location.
    runtime = Path('/run/artunix/wl')
    runtime.mkdir(parents=True, exist_ok=True)
    if runtime.is_symlink() or runtime.stat().st_uid != os.getuid():
        raise RuntimeError('Invalid Wayland runtime directory')
    runtime.chmod(0o700)
    env = dict(os.environ, XDG_RUNTIME_DIR=str(runtime))
    env.pop('WAYLAND_DISPLAY', None)
    socket_name = 'wl-' + uuid.uuid4().hex[:16]
    screen = subprocess.check_output(['xrandr', '--current'], env=env, text=True)
    size = re.search(r'current\s+(\d+)\s+x\s+(\d+)', screen)
    if size is None:
        raise RuntimeError('Cannot determine X11 display dimensions')
    # Weston supplies a windowed Wayland backend without DRM, VT, logind or input devices.
    parent = subprocess.Popen(['weston', '--backend=x11-backend.so', '--renderer=pixman',
                               '--shell=desktop-shell.so', '--socket=' + socket_name,
                               '--idle-time=0', '--width=' + size[1], '--height=' + size[2]], env=env)
    plasma = None
    try:
        deadline = time.monotonic() + 20
        while not (runtime / socket_name).is_socket():
            if parent.poll() is not None or time.monotonic() >= deadline:
                raise RuntimeError('Nested Wayland display failed to start')
            time.sleep(.1)
        env.update(WAYLAND_DISPLAY=socket_name, XDG_SESSION_TYPE='wayland',
                   XDG_CURRENT_DESKTOP='KDE', QT_QPA_PLATFORM='wayland',
                   QT_QUICK_BACKEND='software', KWIN_COMPOSE='Q', PLASMA_USE_SYSTEMD_BOOT='0')
        # The private accelerated Mesa bundle is X11-only. Nested Wayland uses
        # the distro's Wayland-capable Mesa and a software compositor instead.
        env.update(LD_LIBRARY_PATH='/usr/lib', LIBGL_DRIVERS_PATH='/usr/lib/dri',
                   GALLIUM_DRIVER='llvmpipe', LIBGL_ALWAYS_SOFTWARE='1')
        env.pop('MESA_LOADER_DRIVER_OVERRIDE', None)
        env.pop('VK_ICD_FILENAMES', None)
        plasma = subprocess.Popen(['startplasma-wayland'], env=env)
        while plasma.poll() is None:
            if parent.poll() is not None:
                raise RuntimeError('Nested Wayland display exited')
            time.sleep(.2)
        if plasma.returncode:
            raise RuntimeError(f'Plasma exited ({plasma.returncode})')
    finally:
        for child in (plasma, parent):
            if child is not None and child.poll() is None:
                child.terminate()
                try:
                    child.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    child.kill()
                    child.wait()


if __name__ == '__main__':
    run()
