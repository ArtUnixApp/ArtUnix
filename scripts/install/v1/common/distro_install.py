#!/usr/bin/env python3
import hashlib
import os
from pathlib import Path
import subprocess
import sys
import urllib.request


def install(url, sha256, top):
    root, cache = map(Path, sys.argv[1:3])
    root.mkdir(parents=True, exist_ok=True)
    cache.mkdir(parents=True, exist_ok=True)
    marker = root / '.artunix-rootfs'
    if marker.exists():
        if marker.read_text() != sha256:
            raise RuntimeError('Installed rootfs does not match repository recipe')
        prepare(root)
        return
    subprocess.run(['apt', 'update'], check=True)
    subprocess.run(['apt', '-y', 'install', 'xz-utils'], check=True)
    archive = cache / f'{sha256}.tar.xz'

    def digest(path):
        with path.open('rb') as stream:
            return hashlib.file_digest(stream, 'sha256').hexdigest()

    if not archive.exists() or digest(archive) != sha256:
        partial = archive.with_suffix('.xz.partial')
        try:
            if not url.startswith('https://'):
                raise ValueError('Rootfs URL must use HTTPS')
            with urllib.request.urlopen(url, timeout=30) as response, partial.open('wb') as output:
                if not response.url.startswith('https://'):
                    raise ValueError('Rootfs redirect must use HTTPS')
                total = 0
                while data := response.read(65536):
                    total += len(data)
                    if total > 512 * 1024 * 1024:
                        raise ValueError('Rootfs download exceeds limit')
                    output.write(data)
                print(f'Downloaded {total} bytes', flush=True)
            if digest(partial) != sha256:
                raise RuntimeError('Downloaded rootfs checksum mismatch')
            os.replace(partial, archive)
        finally:
            partial.unlink(missing_ok=True)
    subprocess.run(['tar', '--extract', '--xz', '--file', str(archive), '--directory', str(root),
                    '--strip-components=1', '--no-same-owner', '--no-same-permissions',
                    f'--exclude={top}/dev/*'], check=True)
    marker.write_text(sha256)
    prepare(root)


def prepare(root):
    # Networking and service suppression are needed before bootstrapping guest Python.
    resolv = root / 'etc/resolv.conf'
    resolv.unlink(missing_ok=True)
    resolv.write_text(''.join(f'nameserver {address}\n' for address in sys.argv[3:]))
    policy = root / 'usr/sbin/policy-rc.d'
    policy.write_text('#!/bin/sh\nexit 101\n')
    policy.chmod(0o755)
