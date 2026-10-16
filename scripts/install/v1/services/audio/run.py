#!/usr/bin/env python3
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

with socket.socket() as reservation:
    reservation.bind(('127.0.0.1', 0))
    port = reservation.getsockname()[1]
server = f'tcp:127.0.0.1:{port}'
os.environ['PULSE_SERVER'] = server
cookie = Path('/root/.config/pulse/cookie')
cookie.parent.mkdir(parents=True, exist_ok=True)
if not cookie.is_file():
    cookie.write_bytes(os.urandom(256))
cookie.chmod(0o600)
config = f'default-server = {server}\nautospawn = no\nenable-shm = no\n'
Path('/root/.config/pulse/client.conf').write_text(config)
Path('/etc/pulse/client.conf.d/artunix.conf').write_text(config)
daemon = subprocess.Popen(['pulseaudio', '-n', '--daemonize=no', '--exit-idle-time=-1', '--disable-shm=yes',
                           '--use-pid-file=no', '--realtime=no',
                           f'--load=module-native-protocol-tcp listen=127.0.0.1 port={port} auth-cookie=/root/.config/pulse/cookie auth-anonymous=no',
                           '--load=module-null-sink sink_name=artunix rate=48000 channels=2'])
recorder = None
try:
    for _ in range(100):
        if daemon.poll() is not None:
            raise RuntimeError('PulseAudio exited before startup')
        if subprocess.run(['pactl', 'info'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
            break
        time.sleep(.1)
    else:
        raise RuntimeError('PulseAudio startup timed out')
    subprocess.run(['pactl', 'set-default-sink', 'artunix'], check=True)
    recorder = subprocess.Popen(['parec', '--raw', '--format=s16le', '--rate=48000', '--channels=2',
                                 '--device=artunix.monitor', '--latency-msec=40'], stdout=subprocess.PIPE)
    with socket.create_connection(('127.0.0.1', int(sys.argv[1])), timeout=10) as output:
        output.settimeout(None)
        output.sendall((sys.argv[2]+'\n').encode('ascii'))
        print('ARTUNIX_AUDIO_READY', flush=True)
        while data := recorder.stdout.read(4096):
            output.sendall(data)
    raise RuntimeError('Audio capture ended')
finally:
    for process in (recorder, daemon):
        if process is not None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
