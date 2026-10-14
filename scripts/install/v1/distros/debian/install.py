#!/usr/bin/env python3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))
from distro_install import install

install('https://github.com/termux/proot-distro/releases/download/v4.26.0/debian-trixie-aarch64-pd-v4.26.0.tar.xz', 'cda75346f2c9e09e8a802665745b5a7e2bd6d8584dbf1c86c8c57ef54c4e2d3c', 'debian-trixie-aarch64')
