"""Run real melee selection, collision and material damage under sanitizers."""
import argparse
from pathlib import Path
from firefight_test_support import FirefightHarness

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();h=FirefightHarness(a.output)
    for expanded in (False,True):
        binary=h.compile('test_jackal_melee',expanded=expanded);h.finish();print(h.run(binary),flush=True)

if __name__=='__main__':main()
