"""Compile every runtime entry-point configuration against the installed SDK.

No ROM assets are regenerated and no emulator is launched. Linking/packing the
maintained release, quiet, telemetry and reload modes remains validate.py's job.
"""

import argparse
from pathlib import Path
import subprocess
import contextlib
import io
from build import ROOT, parse_args, compile_options

VARIANTS = {
    "scope-qa": ["--pve-squad", "--scope-qa", "--output-dir", "build/scope-fix/config"],
    "m64-polish": ["--pve-squad", "--m64-polish-qa", "--output-dir", "build/m64-polish/config"],
    "release": ["--preset", "release"],
    "solver-profile": ["--benchmark", "--benchmark-page", "7"],
    "animation-profile": ["--benchmark", "--benchmark-page", "8"],
    "pipeline-profile": ["--benchmark", "--benchmark-page", "9", "--gpu-diagnostic"],
    "pipeline-empty": [
        "--benchmark",
        "--benchmark-page",
        "9",
        "--gpu-diagnostic",
        "--gpu-empty-scissor",
    ],
    "pipeline-minimal": [
        "--benchmark",
        "--benchmark-page",
        "9",
        "--gpu-diagnostic",
        "--gpu-empty-scissor",
        "--gpu-minimal-attributes",
    ],
    "body-flat": ["--preset", "release", "--no-vehicle-body-candidates"],
    "profile": ["--profile"],
    "collision": ["--profile", "--pve-squad", "--collision-profile"],
    "collision-baseline": ["--profile", "--pve-squad", "--collision-profile", "--collision-baseline"],
    "pve-preparation": ["--profile", "--pve-squad", "--pve-prep-profile"],
    "pve-preparation-baseline": ["--profile", "--pve-squad", "--pve-prep-profile", "--pve-prep-baseline"],
    "pve-preparation-photo-baseline": ["--pve-squad", "--pve-model-qa", "--pve-prep-baseline"],
    "benchmark": ["--benchmark", "--paced30"],
    "quiet": ["--vi-benchmark", "--preset", "release"],
    "buffers4": ["--vi-benchmark", "--paced30", "--paced30-buffers", "4"],
    "buffers5": ["--vi-benchmark", "--paced30", "--paced30-buffers", "5"],
    "snapshot": ["--snapshot-tick", "1148"],
    "frontend": ["--frontend-qa", "4"],
    "menu": ["--menu-qa"],
    "model": ["--model-qa"],
    "spartan-motion": ["--spartan-motion-qa"],
    "spartan-reload": ["--spartan-reload-qa"],
    "covenant-models": ["--pve-squad", "--pve-model-qa"],
    "covenant-candidate": ["--pve-squad", "--pve-model-qa", "--pve-model-bank",
                           "build/covenant-models/bank", "--output-dir", "build/covenant-models/config"],
    "covenant-crunch": ["--pve-squad", "--pve-model-bank", "build/covenant-crunch/bank", "--pve-crunch", "--output-dir", "build/covenant-crunch/config"],
    "covenant-crunch-baseline": ["--pve-squad", "--pve-model-bank", "build/covenant-crunch/bank", "--pve-crunch", "--pve-crunch-baseline", "--output-dir", "build/covenant-crunch/config"],
    "covenant-crunch-photo": ["--pve-squad", "--pve-model-qa", "--pve-model-bank", "build/covenant-crunch/bank", "--pve-crunch", "--output-dir", "build/covenant-crunch/config"],
    "weapon": ["--weapon-qa"],
    "hud": ["--hud-qa"],
    "geometry": ["--geometry-qa"],
    "environment": ["--environment-qa"],
    "ground": ["--ground-qa"],
    "aim": ["--aim-qa", "0"],
    "plasma": ["--plasma-qa", "3"],
    "interactions": ["--interaction-qa", "3"],
    "shields": ["--shield-qa", "2"],
    "movement": ["--movement-qa", "0"],
    "combat": ["--combat-qa", "7"],
    "reload": ["--reload-qa", "--validate"],
    "effects": ["--effects-qa"],
    "destruction": ["--destruction-qa"],
    "showcase": ["--showcase", "banshee"],
    "bsp": ["--blam-bsp"],
    "telemetry": ["--demo", "--telemetry"],
}


def main():
    assert parse_args(["--preset", "release"]).rspq_buffer_kib == 32
    assert parse_args(["--preset", "release", "--validate"]).rspq_buffer_kib == 8
    assert (
        parse_args(["--preset", "release", "--validate", "--rspq-buffer-kib", "32"]).rspq_buffer_kib
        == 32
    )
    for flags in (
        ["--preset", "release", "--gpu-empty-scissor"],
        ["--preset", "release", "--gpu-minimal-attributes"],
        ["--benchmark", "--gpu-diagnostic", "--gpu-minimal-attributes"],
        ["--vi-benchmark", "--gpu-empty-scissor"],
        ["--pve-model-qa"],
        ["--pve-crunch-baseline"],
        ["--pve-crunch", "--pve-squad"],
        ["--pve-crunch", "--pve-squad", "--pve-model-bank", "build/covenant-models/bank", "--output-dir", "build/covenant-crunch/config"],
        ["--scope-qa"],
        ["--scope-qa", "--pve-squad", "--profile", "--output-dir", "build/scope-fix/config"],
        ["--m64-polish-qa"],
        ["--m64-polish-qa", "--firefight", "--output-dir", "build/m64-polish/config"],
        ["--m64-polish-qa", "--pve-squad", "--profile", "--output-dir", "build/m64-polish/config"],
        ["--pve-draw-audit"],
        ["--vehicle-cost-audit"],
        ["--vehicle-query-baseline"],
        ["--vehicle-query-verify"],
        ["--pve-draw-audit", "--pve-squad", "--profile", "--pve-photo-tick", "60"],
        ["--firefight", "--pve-model-bank", "build/covenant-models/bank"],
        ["--pve-model-bank", "build/covenant-models/bank", "--output-dir", "build/covenant-models/config"],
    ):
        try:
            with contextlib.redirect_stderr(io.StringIO()):
                parse_args(flags)
        except SystemExit as error:
            assert error.code == 2
        else:
            raise AssertionError("Unsafe diagnostic combination accepted: " + str(flags))
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=ROOT / "build/n64-validation/configurations"
    )
    parser.add_argument(
        "--prepared", type=Path, default=ROOT / "build/n64-validation/target/release"
    )
    parser.add_argument("--sdk", type=Path, help="Installed SDK override for an isolated checkout")
    parser.add_argument("--tiny3d", type=Path, help="Tiny3D override for an isolated checkout")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for name, flags in VARIANTS.items():
        options = parse_args(flags)
        sdk, tiny = (args.sdk or options.sdk).resolve(), (args.tiny3d or options.tiny3d).resolve()
        for unit in ("main.c", "scene.c", "presentation.c", "runtime_qa.c"):
            source = ROOT / "port/n64" / unit
            subprocess.run(
                [
                    str(sdk / "bin/mips64-elf-gcc"),
                    "-c",
                    str(source),
                    "-o",
                    str(args.output_dir / (name + "-" + source.stem + ".o")),
                    *map(str, compile_options(options, sdk, tiny, args.prepared, source)),
                ],
                cwd=ROOT,
                check=True,
            )
        print("PASS runtime configuration: " + name, flush=True)
    print(f"PASS: {len(VARIANTS)} configurations / {len(VARIANTS)*4} target translation units")


if __name__ == "__main__":
    main()
