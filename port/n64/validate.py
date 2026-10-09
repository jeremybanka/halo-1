#!/usr/bin/env python3
"""Run the maintained behavior-preserving N64 validation baseline.

Asset banks must already be connected. This never regenerates or reduces them.
Target builds are opt-in; Ares pixels and VI timing remain separate evidence.
"""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from blam.test_vehicle import validate as host_suites

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = (
    "test_scene_equivalence.py",
    "test_render_matrix.py",
    "test_render_prepare.py",
    "test_render_flush.py",
    "test_vehicle_culling.py",
    "test_vehicle_pose_cache.py",
    "test_deferred_animation.py",
    "test_vi_benchmark.py",
    "test_weapon_workspace.py",
    "test_model_index_aliases.py",
    "test_effect_bounds.py",
    "test_audio_schedule.py",
    "test_paced_acquire.py",
    "test_input_menu.py",
)
ASSETS = (
    "test_interaction_assets.py",
    "test_pack_bounds.py",
    "test_scope_geometry.py",
    "test_scorpion_barrel.py",
    "test_menu_assets.py",
)
HEADERS = (
    "render_bounds",
    "render_lod",
    "render_animation",
    "firstperson_service",
    "firstperson_ammo",
    "hud_layout",
    "benchmark",
    "cadence",
    "cadence_tail",
    "render_pacing",
    "pacing_fifo",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--group",
        action="append",
        choices=("host", "headers", "contracts", "assets", "equivalence", "target"),
        help="Repeat for selected groups; default host/contracts/assets",
    )
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build/n64-validation")
    parser.add_argument(
        "--reference", default="b3fba521", help="Git checkpoint for optional per-tick equivalence"
    )
    args = parser.parse_args()
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=True)
    groups = args.group or ["host", "contracts", "assets"]
    results = []

    def check(name, operation):
        started = time.monotonic()
        try:
            operation()
            result = {"name": name, "status": "pass"}
        except (subprocess.CalledProcessError, AssertionError) as error:
            result = {"name": name, "status": "fail", "error": str(error)}
        result["seconds"] = round(time.monotonic() - started, 3)
        results.append(result)
        print(result["status"].upper() + ": " + name, flush=True)

    def command(arguments):
        subprocess.run(
            list(map(str, arguments)),
            cwd=ROOT,
            check=True,
            env={**os.environ, "HALO64_VALIDATION_OUTPUT": str(out / "contracts")},
        )

    if "host" in groups:
        check("game/vehicle sanitizer suites", lambda: host_suites(out / "host"))
    if "host" in groups or "headers" in groups:
        (out / "host").mkdir(parents=True, exist_ok=True)
        for name in HEADERS:

            def header(name=name):
                binary = out / "host" / name
                extra = {
                    "firstperson_service": ["build/n64/generated/interaction_assets.c"],
                    "firstperson_ammo": ["build/n64/generated/firstperson_ammo_data.c"],
                    "render_pacing": ["port/n64/blam/runtime.c"],
                }.get(name, [])
                command(
                    [
                        "clang",
                        "-std=c17",
                        "-O1",
                        "-g",
                        "-Wall",
                        "-Wextra",
                        "-Werror",
                        "-fsanitize=address,undefined",
                        "-Iport/n64",
                        "port/n64/test_" + name + ".c",
                        *extra,
                        "-lm",
                        "-o",
                        binary,
                    ]
                )
                command([binary])

            check(name, header)

        def fast_bounds():
            binary = out / "host/bounds-target-math"
            command(
                [
                    "clang",
                    "-std=c17",
                    "-O2",
                    "-ffast-math",
                    "-ftrapping-math",
                    "-fno-associative-math",
                    "-fno-finite-math-only",
                    "-fsanitize=undefined",
                    "-Iport/n64",
                    "port/n64/test_render_bounds.c",
                    "-lm",
                    "-o",
                    binary,
                ]
            )
            command([binary])

        check("bounds with production math flags", fast_bounds)
    for group, scripts in [("contracts", CONTRACTS), ("assets", ASSETS)]:
        if group in groups:
            for script in scripts:
                check(
                    script,
                    lambda script=script: command([sys.executable, ROOT / "port/n64" / script]),
                )
    if "equivalence" in groups:
        check(
            "checkpoint per-tick equivalence",
            lambda: command(
                [
                    sys.executable,
                    "port/n64/test_runtime_equivalence.py",
                    "--reference",
                    args.reference,
                    "--output-dir",
                    out / "equivalence",
                ]
            ),
        )
    if "target" in groups:
        for name, flags in [
            ("release", []),
            ("quiet", ["--vi-benchmark"]),
            ("telemetry", ["--demo", "--telemetry"]),
            ("reload", ["--reload-qa", "--validate"]),
        ]:
            check(
                "target " + name,
                lambda name=name, flags=flags: command(
                    [
                        sys.executable,
                        "port/n64/build.py",
                        "--preset",
                        "release",
                        "--output-dir",
                        out / "target" / name,
                        *flags,
                    ]
                ),
            )
        check(
            "runtime configuration matrix",
            lambda: command(
                [
                    sys.executable,
                    "port/n64/test_runtime_configs.py",
                    "--prepared",
                    out / "target/release",
                    "--output-dir",
                    out / "configurations",
                ]
            ),
        )
    (out / "results.json").write_text(
        json.dumps({"groups": groups, "results": results}, indent=2) + "\n"
    )
    failed = [result["name"] for result in results if result["status"] == "fail"]
    print(
        f"{len(results)-len(failed)}/{len(results)} validation groups passed; report: {out}/results.json"
    )
    if failed:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
