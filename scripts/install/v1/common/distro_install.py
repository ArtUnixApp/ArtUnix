#!/usr/bin/env python3
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import re
import urllib.request
import tarfile
import shutil
from pathlib import PurePosixPath

REPOSITORY = 'ArtUnixApp/ArtUnix'


class RootfsTar(tarfile.TarFile):
    def makelink(self, member, target):
        if member.islnk():
            # Android app sandboxes can reject linkat even when both files are owned
            # by the app. Preserve the bytes and permissions without creating a link.
            with self.extractfile(self.getmember(member.linkname)) as source, open(target, 'wb') as output:
                shutil.copyfileobj(source, output)
        else:
            super().makelink(member, target)


def extract_rootfs(archive, root, top):
    base = root.resolve()

    def member_filter(member, destination):
        parts = PurePosixPath(member.name).parts
        if not parts or parts[0] != top or '..' in parts or member.name.startswith('/'):
            raise ValueError('Invalid rootfs archive path')
        name = '/'.join(parts[1:])
        if not name:
            return None
        if len(parts) > 2 and parts[1] in ('dev', 'proc', 'sys', 'run', 'tmp'):
            return None
        if not (member.isfile() or member.isdir() or member.issym() or member.islnk()):
            return None
        parent = (root / name).parent.resolve()
        if not parent.is_relative_to(base):
            raise ValueError('Rootfs archive parent escapes installation')
        target = root / name
        # Repeated archive entries must not write through an earlier symlink.
        if target.is_symlink():
            target.unlink()
        if member.islnk():
            links = PurePosixPath(member.linkname).parts
            if not links or links[0] != top or '..' in links:
                raise ValueError('Invalid rootfs hard-link target')
        # Absolute Linux symlink targets are intentional and interpreted by PRoot.
        # Archive member parents are checked above to prevent following one outside.
        return member.replace(name=name, deep=False)

    with RootfsTar.open(archive, 'r:xz') as source:
        source.extractall(root, filter=member_filter)


def read_json(url):
    request = urllib.request.Request(url, headers={'User-Agent': 'ArtUnix-Rootfs-v1', 'Accept': 'application/vnd.github+json'})
    with urllib.request.urlopen(request, timeout=30) as response:
        if not response.url.startswith('https://'):
            raise ValueError('Release metadata must use HTTPS')
        body = response.read(1024 * 1024 + 1)
        if len(body) > 1024 * 1024:
            raise ValueError('Release metadata exceeds limit')
        return json.loads(body)


def release_asset(release, name):
    matches = [asset for asset in release.get('assets', []) if asset['name'] == name]
    if len(matches) != 1:
        raise RuntimeError(f'Release must contain exactly one {name} asset')
    url = matches[0]['browser_download_url']
    if not url.startswith(f'https://github.com/{REPOSITORY}/releases/download/'):
        raise ValueError('Unexpected release asset URL')
    return url


def latest_rootfs(distro):
    release = read_json(f'https://api.github.com/repos/{REPOSITORY}/releases/latest')
    if release.get('draft') or release.get('prerelease'):
        raise ValueError('Expected a published stable release')
    manifest = read_json(release_asset(release, 'rootfs-manifest.json'))
    if manifest.get('schemaVersion') != 1 or manifest.get('architecture') != 'arm64':
        raise ValueError('Unsupported rootfs manifest')
    recipe = manifest['distros'][distro]
    if not re.fullmatch(r'[a-f0-9]{64}', recipe['sha256']):
        raise ValueError('Invalid rootfs checksum')
    if not re.fullmatch(r'artunix-[a-z0-9.-]+-arm64', recipe['top']):
        raise ValueError('Invalid rootfs archive prefix')
    if not re.fullmatch(r'artunix-[a-z0-9.-]+-arm64\.tar\.xz', recipe['asset']):
        raise ValueError('Invalid rootfs asset name')
    if recipe['asset'] != recipe['top']+'.tar.xz' or not recipe['top'].startswith(f'artunix-{distro}-'):
        raise ValueError('Rootfs asset does not match distribution')
    return dict(distro=distro, release=release['tag_name'], url=release_asset(release, recipe['asset']),
                sha256=recipe['sha256'], top=recipe['top'])


def install_latest(distro):
    root = Path(sys.argv[1])
    source_file = root / '.artunix-rootfs-source.json'
    # Once extraction completed, resume its exact rootfs instead of upgrading it in place.
    if (root / '.artunix-rootfs').exists() and source_file.exists():
        source = json.loads(source_file.read_text())
        if source.get('distro') != distro:
            raise ValueError('Installed distribution does not match request')
    elif (root / '.artunix-rootfs').exists():
        raise RuntimeError('This rootfs predates release manifests. Create a new instance to use release rootfs assets.')
    else:
        source = latest_rootfs(distro)
        root.mkdir(parents=True, exist_ok=True)
        source_file.write_text(json.dumps(source, indent=2))
    print(f"Rootfs release: {source['release']} ({source['sha256']})", flush=True)
    install(source['url'], source['sha256'], source['top'])


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
    extract_rootfs(archive, root, top)
    marker.write_text(sha256)
    prepare(root)


def prepare(root):
    # Networking and service suppression are needed before bootstrapping guest Python.
    resolv = root / 'etc/resolv.conf'
    resolv.unlink(missing_ok=True)
    resolv.write_text(''.join(f'nameserver {address}\n' for address in sys.argv[3:]))
    hosts = root / 'etc/hosts'
    hosts.unlink(missing_ok=True)
    hosts.write_text('127.0.0.1 localhost localhost.localdomain\n::1 localhost localhost.localdomain\n')
    policy = root / 'usr/sbin/policy-rc.d'
    policy.parent.mkdir(parents=True, exist_ok=True)
    policy.unlink(missing_ok=True)
    policy.write_text('#!/bin/sh\nexit 101\n')
    policy.chmod(0o755)
