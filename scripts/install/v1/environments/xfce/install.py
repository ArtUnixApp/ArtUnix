#!/usr/bin/env python3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))
from environment_install import install

install(['xfce4', 'xfce4-terminal'])
