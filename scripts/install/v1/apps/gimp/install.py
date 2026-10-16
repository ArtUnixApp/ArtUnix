#!/usr/bin/env python3
import subprocess

subprocess.run(['apt-get', '-o', 'APT::Status-Fd=1', '-o', 'Dpkg::Progress-Fancy=0', '-y',
                '--no-install-recommends', 'install', 'gimp'], check=True)
