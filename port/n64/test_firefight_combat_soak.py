"""Qualify the active-combat soak controller using the real map/game and sanitizers."""
import argparse
import importlib.util
from pathlib import Path
from firefight_test_support import FirefightHarness


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();h=FirefightHarness(a.output)
    binary=h.compile('test_firefight_combat_soak',expanded=True);h.finish()
    source=Path(__file__).with_name('benchmarks')/'firefight-zoom/capture_combat.py'
    spec=importlib.util.spec_from_file_location('capture_combat',source)
    capture=importlib.util.module_from_spec(spec);spec.loader.exec_module(capture)
    for fight in (0,1):
        text=h.run(binary,args=[fight,18000],log=f'combat-{fight}.log')
        failures=capture.coverage(capture.rows(text))
        assert not failures,failures
        print('PASS sustained activity and simultaneous-load gates:',fight,flush=True)


if __name__=='__main__':main()
