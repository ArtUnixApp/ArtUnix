#!/usr/bin/env python3
from pathlib import Path
import uuid

identity = Path('/etc/machine-id')
value = identity.read_text().strip() if identity.is_file() else ''
if len(value) != 32 or any(c not in '0123456789abcdef' for c in value):
    identity.unlink(missing_ok=True)
    identity.write_text(uuid.uuid4().hex+'\n')

config = Path('/etc/pulse/client.conf.d/artunix.conf')
config.parent.mkdir(parents=True, exist_ok=True)
config.write_text('default-server = unix:/tmp/artunix-pulse.sock\nautospawn = no\nenable-shm = no\n')
user = Path('/root/.config/pulse/client.conf')
user.parent.mkdir(parents=True, exist_ok=True)
user.write_text(config.read_text())
profile = Path('/etc/profile.d/artunix-audio.sh')
profile.parent.mkdir(parents=True, exist_ok=True)
profile.unlink(missing_ok=True)
Path('/etc/asound.conf').write_text('pcm.!default { type pulse }\nctl.!default { type pulse }\n')
