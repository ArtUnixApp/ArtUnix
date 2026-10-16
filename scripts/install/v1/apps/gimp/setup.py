#!/usr/bin/env python3
from pathlib import Path

if not Path('/usr/bin/gimp').is_file():
    raise RuntimeError('GIMP executable is missing')
Path('/root/.config/GIMP').mkdir(parents=True, exist_ok=True)
