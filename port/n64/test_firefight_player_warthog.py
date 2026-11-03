"""Player transport and Firefight regressions against the pinned private bank."""
import argparse
from pathlib import Path
from firefight_test_support import FirefightHarness


def run(output):
    harness=FirefightHarness(output)
    for expanded in (False,True):
        tests=['test_firefight_player_warthog','test_firefight']
        if expanded:tests+=['test_firefight_fights','test_enemy_vehicles']
        for test in tests:harness.run(harness.compile(test,expanded))
    harness.finish()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,required=True)
    run(parser.parse_args().output_dir)
