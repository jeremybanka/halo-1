"""Host sanitizer coverage for service-state clocks plus the rocket alpha mask."""
from pathlib import Path
import json,re,subprocess,tempfile
ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='halo-fp-service-') as tmp:
    tmp=Path(tmp);(tmp/'t3d').mkdir()
    (tmp/'t3d/t3d.h').write_text('typedef struct { char data[32]; } T3DVertPacked;\n')
    subprocess.run(['clang','-std=c17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
        '-I'+str(tmp),'-I'+str(ROOT/'port/n64'),str(ROOT/'port/n64/test_firstperson_service.c'),
        str(ROOT/'build/n64/generated/interaction_assets.c'),'-o',str(tmp/'test')],check=True)
    subprocess.run([str(tmp/'test')],check=True)
s=(ROOT/'build/n64/generated/firstperson_data.c').read_text()
texture=re.search(r'bg_fp_rocket_texture\[2048\][^=]*=\{([^}]+)',s).group(1)
alpha=[int(x,16)&1 for x in texture.split(',')]
assert len(alpha)==2048 and 0<sum(alpha[:-64])<1984 and all(alpha[-64:])
w=json.loads((ROOT/'build/n64/assets/firstperson-reduced.json').read_text())['weapons']['rocket']
assert w['decal_separation']['triangles']==12
assert w['decal_separation']['distance']==1.5/256
print('PASS: rocket lettering retains transparent cutouts and an opaque body texel row; decal separation is recorded')
