#!/usr/bin/env python3
"""Restore the hash-locked PR #18 build inputs from the private asset checkout.

Run through tools/workspace.py run when the checkout has a workspace policy.
This restores inputs only; the original build's provenance checks still run.
"""

import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys

SOURCE_REF = "13a909946e0ce866ade88b30de5d907b076fefce"
BASE_ASSET_REF = "1e1888fcc120376c488334d992de1a530331998c"
PACKAGE = Path("assets/build-inputs/pr18")
MAP_NAMES = {"bloodgulch-decompressed.map", "a30-decompressed.map", "b40-decompressed.map", "ui.map", "bloodgulch.map"}
MAX_CHUNK = 32 * 1024 * 1024


def sha256(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def checked_path(parent, name):
    relative = Path(name)
    if relative.is_absolute() or not relative.parts or ".." in relative.parts:
        raise ValueError("Unsafe package path: " + name)
    path = parent / relative
    if not path.resolve().is_relative_to(parent.resolve()) or path.is_symlink():
        raise ValueError("Package payload must be a local regular file: " + name)
    return path


def cache_destination(bank, name):
    if name.endswith("-decompressed.map"):
        return bank / "assets" / name
    return bank.parent / "build/assets/halo-retail/maps" / name


def verify(path, record):
    if not path.is_file() or path.stat().st_size != record["bytes"] or sha256(path) != record["sha256"]:
        raise ValueError("Missing or changed input: " + str(path))


def restore(bank, output):
    package = bank / PACKAGE
    manifest = json.loads((package / "manifest.json").read_text())
    if (manifest["schema"], manifest["source_ref"], manifest["base_asset_ref"]) != (1, SOURCE_REF, BASE_ASSET_REF):
        raise ValueError("Not the PR #18 input package")
    maps = manifest["maps"]
    if set(maps) != MAP_NAMES:
        raise ValueError("PR #18 requires exactly five source caches")
    # Check every compressed payload and bank member before writing anything.
    for name, record in maps.items():
        if sum(part["raw_bytes"] for part in record["parts"]) != record["bytes"]:
            raise ValueError("Incomplete map: " + name)
        for part in record["parts"]:
            if not 0 < part["raw_bytes"] <= MAX_CHUNK:
                raise ValueError("Invalid chunk size")
            verify(checked_path(package, part["path"]), part)
    for name, record in manifest["enemy_bank"].items():
        if Path(name).name != name:
            raise ValueError("Invalid bank filename")
        verify(checked_path(bank, record["path"]), record)
    # Existing correct map links/files can be reused. Never replace another file.
    for name, record in maps.items():
        destination = cache_destination(bank, name)
        if os.path.lexists(destination):
            verify(destination, record)
    if output.exists():
        raise FileExistsError("Use a fresh output directory: " + str(output))
    (output / "assets").mkdir(parents=True)
    (output / "enemy-bank").mkdir()
    for name, record in maps.items():
        temporary = output / "assets" / (name + ".partial")
        with temporary.open("xb") as stream:
            for part in record["parts"]:
                with gzip.open(checked_path(package, part["path"]), "rb") as compressed:
                    data = compressed.read(part["raw_bytes"] + 1)
                if len(data) != part["raw_bytes"] or hashlib.sha256(data).hexdigest() != part["raw_sha256"]:
                    raise ValueError("Corrupt map chunk: " + part["path"])
                stream.write(data)
        verify(temporary, record)
        temporary.rename(output / "assets" / name)
    for name, record in manifest["enemy_bank"].items():
        destination = output / "enemy-bank" / name
        shutil.copyfile(checked_path(bank, record["path"]), destination)
        verify(destination, record)
    # Publish links only after the entire restore is verified.
    for name in maps:
        destination = cache_destination(bank, name)
        if not os.path.lexists(destination):
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.symlink_to((output / "assets" / name).resolve())
    (output / "restore.json").write_text(json.dumps({
        "source_ref": SOURCE_REF,
        "base_asset_ref": BASE_ASSET_REF,
        "package_sha256": sha256(package / "manifest.json"),
        "maps": {name: {k: record[k] for k in ("bytes", "sha256")} for name, record in maps.items()},
        "enemy_bank_files": len(manifest["enemy_bank"]),
        "reference_rom": manifest["reference_rom"],
    }, indent=2) + "\n")
    return manifest


def main():
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    output = args.output_dir.absolute()
    if not output.resolve().is_relative_to((root / "build").resolve()):
        parser.error("Output must be inside this checkout's build directory")
    common = Path(subprocess.check_output(["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"], text=True).strip())
    if ((root / "workspace-policy.json").exists() or (common.parent / "workspace-policy.json").exists()) and not os.environ.get("HALO_WORKSPACE_PARENT_RUN"):
        parser.error("Run this restore through tools/workspace.py run --output <same path> --peak-gib 1 -- <command>")
    bank = root / "halo64-assets"
    # Verify the full pinned bank, including the compressed input package.
    from setup_assets import verify_bank, connect_assets
    print("Verified", verify_bank(), "private asset files", flush=True)
    manifest = restore(bank, output)
    connect_assets()
    command = [sys.executable, "port/n64/build.py", "--preset", "release",
               "--pve-model-bank", str(output / "enemy-bank"), "--pve-crunch",
               "--pve-roster", "--pve-jackal-shields",
               "--enemy-vehicle-bank", str(output / "enemy-bank"),
               "--vehicle-distance-lods", "--output-dir", str(output / "rom")]
    print("Restored the PR #18 maps and expanded enemy bank.")
    print("Build with your N64_INST and TINY3D_DIR environment, and supply --libdragon-source if needed:")
    print(shlex.join(command))
    print("Reference ROM:", json.dumps(manifest["reference_rom"], sort_keys=True))


if __name__ == "__main__":
    main()
