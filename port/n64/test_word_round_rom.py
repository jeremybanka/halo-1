"""Build a standalone VR4300 rounding test ROM; inspect its PASS screen in Ares.

No game assets are needed. The target executes both conversions on normal,
subnormal, signed-zero and boundary inputs; packing alone does not run the test.
"""

import argparse
import os
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--sdk",
        type=Path,
        default=os.environ.get("N64_INST", ROOT.parent / "n64-2048/.build/libdragon"),
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build/n64-validation/word-round")
    args = parser.parse_args()
    sdk, out = args.sdk.resolve(), args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)

    def run(command):
        subprocess.run(
            list(map(str, command)), cwd=ROOT, check=True, env={**os.environ, "N64_INST": str(sdk)}
        )

    elf = out / "word-round.elf"
    run(
        [
            sdk / "bin/mips64-elf-gcc",
            "-march=vr4300",
            "-mtune=vr4300",
            "-mabi=o64",
            "-O2",
            "-g",
            "-std=gnu17",
            "-DN64",
            "-fno-fast-math",
            "-ffp-contract=off",
            "-ffunction-sections",
            "-fdata-sections",
            "-I" + str(sdk / "mips64-elf/include"),
            "-Iport/n64",
            "port/n64/test_word_round_n64.c",
            "-L" + str(sdk / "mips64-elf/lib"),
            "-Wl,-Tn64.ld",
            "-Wl,--gc-sections",
            "-Wl,--wrap,__do_global_ctors",
            "-ldragon",
            "-lm",
            "-lc",
            "-ldragonsys",
            "-o",
            elf,
        ]
    )
    sym, stripped, rom = (elf.with_suffix(ext) for ext in (".sym", ".stripped", ".z64"))
    run([sdk / "bin/n64sym", elf, sym])
    shutil.copy2(elf, stripped)
    run([sdk / "bin/mips64-elf-strip", "-s", stripped])
    run([sdk / "bin/n64elfcompress", "-o", out, "-c", "1", stripped])
    run(
        [
            sdk / "bin/n64tool",
            "--title",
            "HALO64 WORD TEST",
            "--toc",
            "--output",
            rom,
            "--align",
            "256",
            stripped,
            "--align",
            "8",
            sym,
        ]
    )
    run([sdk / "bin/ed64romconfig", "--savetype", "none", "--regionfree", rom])
    print("Built", rom, "— run it to verify 617,834 inputs / zero failures.")


if __name__ == "__main__":
    main()
