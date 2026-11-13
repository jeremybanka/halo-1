"""Exercise the production HUD scope predicate with the real game/seat service."""
import argparse
from pathlib import Path
from firefight_test_support import FirefightHarness,ROOT
from test_render_matrix import function


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();h=FirefightHarness(a.output)
    (h.output/'hud_scope_under_test.inc').write_text('static bool scoped(const bg_player*p){'+function((ROOT/'port/n64/hud.c').read_text(),'scoped')+'}\n')
    for expanded in (False,True):
        binary=h.compile('test_vehicle_scope',expanded=expanded);h.finish();h.run(binary)


if __name__=='__main__':main()
