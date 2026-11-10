"""Bake selected-map infantry navigation and exercise real Firefight scenarios."""
import argparse
from pathlib import Path
import struct
import subprocess
from firefight_test_support import FirefightHarness


def run(output):
    h=FirefightHarness(output)
    baker=h.compile('bake_firefight_nav',embedded=False)
    for map_id in (0,3):h.run(baker,[map_id,h.nav],f'bake-{map_id}.log')
    for expanded in (False,True):
        binary=h.compile('test_firefight_maps',expanded);h.run(binary)
        if not expanded:
            valid=(h.nav/'firefight-nav-0.bin').read_bytes()
            corruptions={'truncated':valid[:-1],'wrong-map':valid[:4]+struct.pack('>H',3)+valid[6:],
                'oversized':valid[:6]+struct.pack('>H',8193)+valid[8:],'bad-neighbor':valid[:26]+struct.pack('>H',8192)+valid[28:]}
            for name,raw in corruptions.items():
                directory=h.output/name;directory.mkdir();(directory/'firefight-nav-0.bin').write_bytes(raw)
                h.run(binary,['reject',0],name+'.log',{'BG_FIREFIGHT_NAV_DIRECTORY':str(directory)})
        from firefight_test_support import ROOT
        menu=h.output/('frontend-roster' if expanded else 'frontend-base')
        command=['clang','-std=c17','-O1','-g','-fsanitize=address,undefined','-DBG_FIREFIGHT',*(['-DBG_PVE_ROSTER'] if expanded else []),
            '-I'+str(ROOT/'port/n64'),*[str(ROOT/'port/n64'/n) for n in ('test_firefight_frontend.c','frontend.c','menu.c','controls.c')],'-lm','-o',str(menu)]
        subprocess.run(command,check=True);h.run(menu);h.records.append({'test':menu.name,'command':command})
    h.finish()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    run(parser.parse_args().output_dir)
