#!/usr/bin/env python3
"""Bounded package repair for setup; never delete locks or force package removal."""
import os
import re
from pathlib import Path
import subprocess
import sys

APT = ['apt-get', '-o', 'APT::Status-Fd=1', '-o', 'Dpkg::Progress-Fancy=0',
       '-o', 'Acquire::Retries=2', '-o', 'DPkg::Lock::Timeout=30']
ENV = dict(os.environ, DEBIAN_FRONTEND='noninteractive', LC_ALL='C')


class PackageFailure(RuntimeError):
    pass


def run(command, required=True):
    # Stream progress to the app, retaining only a bounded diagnostic tail.
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             text=True, errors='replace', env=ENV)
    tail = ''
    try:
        for line in child.stdout:
            print(line, end='', flush=True)
            tail = (tail + line)[-65536:]
        status = child.wait()
    finally:
        child.stdout.close()
        if child.poll() is None:
            child.terminate()
            child.wait()
    if required and status:
        raise PackageFailure(f'Command failed ({status}): {command[0]}\n{tail}')
    return status, tail


def check():
    from package_manager import manager
    kind = manager()
    if kind != 'apt':
        if kind == 'pacman':
            run(['pacman', '-Dk'])
        elif kind == 'dnf':
            run(['dnf', 'check'])
        else:
            _, plan = run(['apk', 'add', '--simulate', '--no-network'])
            if re.search(r'\b(Installing|Upgrading|Downgrading|Reinstalling|Purging)\b', plan):
                raise PackageFailure('APK reports an incomplete dependency transaction:\n' + plan)
        return
    _, audit = run(['dpkg', '--audit'])
    if audit.strip():
        raise PackageFailure('Packages still require configuration:\n' + audit)
    run(APT + ['check'])


def recover(reason):
    from package_manager import manager
    if manager() != 'apt':
        # Never delete locks, relax signatures, or perform an unbounded database repair.
        raise PackageFailure('Native package operation failed. Existing files were preserved; resolve the reported error and Retry.\n' + reason)
    lower = reason.lower()
    if any(text in lower for text in ('no space left', 'read-only file system',
                                      'could not get lock', 'unable to acquire',
                                      'is another process using it')):
        raise PackageFailure('Free device storage or wait for the package manager, then Retry.\n' + reason)
    if any(text in lower for text in ('parsing file', 'status database', 'status file could not')):
        raise PackageFailure('Package database needs manual recovery; existing files were preserved.\n' + reason)
    print('ArtUnix: repairing interrupted package setup', flush=True)
    if any(text in lower for text in ('hash sum mismatch', 'unexpected end of file',
                                      'unexpected end of stream', 'not a debian format',
                                      'decompression', 'lzma error', 'corrupt', 'unexpected size')):
        # Discard downloaded archives only, so APT fetches and authenticates them again.
        run(APT + ['clean'])
    if any(text in lower for text in ('merge list', 'problem parsing', 'lists could not be parsed')):
        # Rebuild disposable repository indexes, preserving locks and package state.
        for folder in (Path('/var/lib/apt/lists'), Path('/var/lib/apt/lists/partial')):
            for entry in folder.iterdir() if folder.is_dir() else ():
                if entry.name != 'lock' and (entry.is_file() or entry.is_symlink()):
                    entry.unlink()
    # Dependencies may prevent the first configure from succeeding; fix them next.
    run(['dpkg', '--configure', '-a'], required=False)
    run(APT + ['-o', 'APT::Update::Error-Mode=any', 'update'])
    run(APT + ['-y', '--no-remove', '--fix-broken', 'install'])
    run(['dpkg', '--configure', '-a'])
    check()


def execute(command):
    try:
        run(command)
        check()
    except PackageFailure as failure:
        recover(str(failure))
        # A repaired dependency tree alone does not prove the requested recipe ran.
        run(command)
        check()


def main(args):
    if args == ['--check']:
        check()
    elif args == ['--resume']:
        try:
            check()
        except PackageFailure as failure:
            recover(str(failure))
    elif args and args[0] == '--run' and len(args) > 1:
        execute(args[1:])
    else:
        raise ValueError('Expected --check, --resume, or --run command ...')


if __name__ == '__main__':
    try:
        main(sys.argv[1:])
    except PackageFailure as failure:
        print('ArtUnix setup paused: ' + str(failure), file=sys.stderr, flush=True)
        sys.exit(1)
