#!/usr/bin/env python3
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "common"))
from package_manager import install, service_packages

install(service_packages('ssh'))
