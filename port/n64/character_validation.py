"""Keep character asset acceptance separate from changes to shared game code.

The original certificate remains immutable evidence for its recorded runtime.
These shared files do not generate character payloads; new builds record their
changes explicitly. Character authoring, decoding, rendering and all private
asset bytes retain the original exact-hash gate.
"""
import hashlib
from pathlib import Path

SHARED_RUNTIME={'port/n64/build.py','port/n64/map.c','port/n64/game.c','port/n64/hud.c','port/n64/frontend_draw.c'}


def verify_gungnir(root,certificate):
    root=Path(root);changes={}
    for group in ('files','inputs'):
        for name,expected in certificate[group].items():
            path=root/name
            if not path.is_file():raise ValueError('Missing GUNGNIR validation input: '+name)
            actual=hashlib.sha256(path.read_bytes()).hexdigest()
            if actual==expected:continue
            if group=='inputs' and name in SHARED_RUNTIME:
                changes[name]={'certificate_sha256':expected,'current_sha256':actual}
            else:raise ValueError('Stale GUNGNIR assets: '+name)
    return changes
