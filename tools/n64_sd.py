#!/usr/bin/env python3
"""Build the current N64 release and copy a timestamped ROM to an SD card."""

import argparse
from datetime import datetime
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def require_card(volume):
    if not volume.is_mount():
        raise RuntimeError(f"SD card is not mounted at {volume}; attach it and retry.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--volume", type=Path, default=Path("/Volumes/DISK_IMG"))
    args = parser.parse_args()
    volume = args.volume.resolve()
    require_card(volume)

    build_root = ROOT / "build"
    build_root.mkdir(exist_ok=True)
    # A fresh output directory prevents an old ROM from being copied and keeps
    # this build separate from ongoing experiments in other build directories.
    with tempfile.TemporaryDirectory(prefix="n64-sd-", dir=build_root) as output:
        print(f"Building N64 release for {volume}/homebrew/ ...", flush=True)
        subprocess.run(
            [sys.executable, str(ROOT / "port/n64/build.py"),
             "--preset", "release", "--output-dir", output],
            cwd=ROOT,
            check=True,
        )
        roms = list(Path(output).glob("*.z64"))
        if len(roms) != 1 or roms[0].stat().st_size == 0:
            raise RuntimeError("Build did not produce exactly one nonempty .z64 ROM.")

        require_card(volume)
        homebrew = volume / "homebrew"
        homebrew.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        destination = homebrew / f"halo_{timestamp}.z64"
        # Exclusive creation preserves existing builds, even on a name collision.
        with destination.open("xb") as target:
            try:
                with roms[0].open("rb") as source:
                    shutil.copyfileobj(source, target)
                target.flush()
                os.fsync(target.fileno())
            except BaseException:
                destination.unlink(missing_ok=True)
                raise
        print(f"Copied {destination} ({destination.stat().st_size:,} bytes)", flush=True)
        print("Eject the SD card before removing it.")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, RuntimeError, subprocess.CalledProcessError) as exc:
        sys.exit(f"n64-sd: {exc}")
