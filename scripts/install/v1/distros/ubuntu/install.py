#!/usr/bin/env python3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))
from distro_install import install

install('https://github.com/termux/proot-distro/releases/download/v4.18.0/ubuntu-noble-aarch64-pd-v4.18.0.tar.xz', '91acaa786b8e2fbba56a9fd0f8a1188cee482b5c7baeed707b29ddaa9a294daa', 'ubuntu-noble-aarch64')
