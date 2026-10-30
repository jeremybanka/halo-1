"""Paired quiet VI runs; terminate only the Ares processes started here."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'build/player-aim'
HERE = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--settings', type=Path, required=True)
    parser.add_argument('--repeat', type=int, default=2)
    args = parser.parse_args()
    results = []
    for repeat in range(args.repeat):
        for variant in ('baseline', 'candidate'):
            manifest = json.loads(next((OUT / variant).glob('*.build.json')).read_text())
            rom = Path(manifest['rom']['path'])
            path = OUT / f'{variant}-{repeat + 1}-native.log'
            with path.open('w') as log:
                proc = subprocess.Popen(['/Applications/ares.app/Contents/MacOS/ares',
                                         '--settings-file', str(args.settings.resolve()),
                                         '--no-file-prompt', str(rom)], stdout=log, stderr=subprocess.STDOUT)
                start = time.monotonic()
                try:
                    while proc.poll() is None and time.monotonic() - start < 360:
                        time.sleep(.5)
                        text = path.read_text(errors='replace')
                        if 'BENCH vi_fresh group=VEHICLES' in text or 'assertion failed' in text.lower():
                            break
                finally:
                    proc.terminate()
                    try:
                        proc.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        proc.kill(); proc.wait()
            text = path.read_text(errors='replace')
            assert 'BENCH vi_fresh group=VEHICLES' in text, text[-2000:]
            assert 'assertion failed' not in text.lower()
            groups = {}
            for line in re.findall(r'BENCH vi_fresh group=.*', text):
                values = dict(re.findall(r'(\w+)=(\w+)', line))
                group = values.pop('group')
                if group in groups:
                    continue
                values = {k: int(v) for k, v in values.items()}
                values['fps'] = values['frames'] * 1e6 / values['elapsed_us']
                groups[group] = values
            heap = re.findall(r'live_heap_free_bytes=(\d+)', text)
            item = dict(variant=variant, repeat=repeat + 1, groups=groups,
                        heap_free=int(heap[-1]) if heap else None,
                        rom_sha256=hashlib.sha256(rom.read_bytes()).hexdigest(),
                        log_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
            results.append(item)
            (HERE / 'performance.json').write_text(json.dumps(results, indent=2) + '\n')
            print(variant, repeat + 1, 'FPS', groups['ALL']['fps'], 'p95', groups['ALL']['p95_us'],
                  'heap', item['heap_free'], flush=True)


if __name__ == '__main__':
    main()
