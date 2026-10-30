#!/usr/bin/env python3
"""Supplementary native residency check; excluded from performance results."""
import argparse
from pathlib import Path
import subprocess
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('capture', type=Path)
    parser.add_argument('--settings', type=Path, required=True)
    parser.add_argument('--timeout', type=float, default=1200)
    args = parser.parse_args()
    output = args.capture.resolve()
    settings = output / 'maps-ares.bml'
    text = args.settings.read_text()
    start = text.index('Audio\n')
    end = text.index('Input\n', start)
    text = text[:start] + text[start:end].replace('  Blocking: true', '  Blocking: false') + text[end:]
    settings.write_text(text)
    roms = list((output / 'maps-cycle').glob('*.z64'))
    assert len(roms) == 1, 'Expected one isolated maps-cycle ROM'
    path = output / 'maps-cycle-native.log'
    complete = False
    with path.open('w') as log:
        proc = subprocess.Popen([
            '/Applications/ares.app/Contents/MacOS/ares', '--settings-file',
            str(settings), '--no-file-prompt', str(roms[0])],
            stdout=log, stderr=subprocess.STDOUT)
        start = time.monotonic()
        try:
            while proc.poll() is None and time.monotonic() - start < args.timeout:
                time.sleep(.5)
                text = path.read_text(errors='replace')
                if any(x in text.lower() for x in ('assertion failed', 'assertf', 'rdpq error', 'rdpq warning')):
                    break
                if 'FRONTEND_QA step=223/223 map=12 done=1' in text:
                    complete = True
                    break
        finally:
            if proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()
    assert complete, 'Map residency cycle did not complete cleanly'
    print('PASS all-map native residency cycle')


if __name__ == '__main__':
    main()
