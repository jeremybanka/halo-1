"""Archive exact native pixels, four-view comparisons and capture provenance."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
from PIL import Image, ImageChops, ImageDraw

ROOT = Path(__file__).resolve().parents[4]
POSES = ['Level', 'Yaw left', 'Yaw right', 'Pitch down', 'Pitch up / hull tilt']
def label(i):
    return ('External' if i<25 else 'Gunner')+' / '+POSES[(i//2)%5]+' / '+('Flash' if i%2 else 'Rest')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    spec = importlib.util.spec_from_file_location('decode_photo', ROOT / 'port/n64/benchmarks/firefight-limited/decode_photo.py')
    decoder = importlib.util.module_from_spec(spec); spec.loader.exec_module(decoder)
    captures, provenance = {}, {}
    for name, directory in [('before', 'photos-baseline'), ('after', 'photos')]:
        folder = args.capture / directory
        log = folder / 'native.log'
        chunks = re.findall(r'FF_PHOTO_BEGIN.*?FF_PHOTO_END', log.read_text(errors='replace'), re.S)
        assert len(chunks) == 51
        captures[name] = []
        for i, chunk in enumerate(chunks[:50]):
            temporary = args.capture / 'decode-frame.log'; temporary.write_text(chunk)
            path = args.output / f'{name}-{i:02}.png'
            decoder.decode(temporary, path)
            captures[name].append(Image.open(path).convert('RGB'))
        manifest_path = max(folder.glob('*.build.json'), key=lambda p:p.stat().st_mtime)
        manifest = json.loads(manifest_path.read_text())
        provenance[name] = dict(build=manifest, log_sha256=hashlib.sha256(log.read_bytes()).hexdigest())
    rows, checks = [], []
    for i, (a, b) in enumerate(zip(captures['before'], captures['after'])):
        difference = ImageChops.difference(a, b)
        changed = sum(any(pixel) for pixel in difference.getdata())
        checks.append(dict(frame=i, state=label(i), changed_pixels=changed))
        assert changed > 0 if i%2 else changed == 0, (i, changed)
        difference.point(lambda x: min(255, x*4)).save(args.output / f'diff-{i:02}.png')
        rows.append(f'<tr><th>{label(i)}</th>' + ''.join(
            f'<td><img src="{name}-{i:02}.png" width="320" height="240"></td>' for name in ('before', 'after', 'diff')) + '</tr>')
    samples = [1,3,5,7,9,25,27,29]
    sheet = Image.new('RGB', (960, len(samples)*262), '#151b22'); draw = ImageDraw.Draw(sheet)
    for row,i in enumerate(samples):
        for col,name in enumerate(('before','after')):
            draw.text((col*320+5,row*262+4),name+' / '+label(i),fill='white')
            sheet.paste(captures[name][i],(col*320,row*262+22))
        draw.text((645,row*262+4),'Difference x4',fill='white')
        sheet.paste(Image.open(args.output/f'diff-{i:02}.png'),(640,row*262+22))
    sheet.save(args.output/'contact-sheet.png')
    for name in ('before','after'):
        captures[name][0].save(args.output/(name+'.gif'),save_all=True,
            append_images=captures[name][1:10],duration=100,loop=0)
    (args.output / 'comparison.html').write_text('''<!doctype html><meta charset="utf-8"><title>Warthog muzzle flash</title>
<style>body{background:#151b22;color:#eee;font:16px system-ui;margin:24px}table{border-collapse:collapse}td,th{padding:8px;border-bottom:1px solid #444}img{image-rendering:pixelated}th{max-width:160px}</style>
<h1>Warthog muzzle flash — native four-view capture</h1><p>Same frozen states and asset bank; baseline uses the renderer before mounted flashes. Each 320×240 PNG contains four viewports: four external angles in the first half, then the production gunner camera. Difference is amplified ×4. These photo ROMs are not used for timing.</p>
<table><thead><tr><th>State / pitch</th><th>Before</th><th>After</th><th>Difference ×4</th></tr></thead><tbody>''' + ''.join(rows) + '</tbody></table>')
    (args.output / 'pixel-checks.json').write_text(json.dumps(checks, indent=2)+'\n')
    (args.output / 'provenance.json').write_text(json.dumps(provenance, indent=2)+'\n')
    print(args.output / 'comparison.html')


if __name__ == '__main__': main()
