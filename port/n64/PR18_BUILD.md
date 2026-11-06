# Build the complete PR #18 release from GitHub

The handoff revision preserves PR #18's gameplay code at
`13a909946e0ce866ade88b30de5d907b076fefce` and all derived payloads from private
asset revision `1e1888fcc120376c488334d992de1a530331998c`. It adds the missing
compressed source caches, a restore helper and the exact expanded-roster recipe.
The three maps are required both by provenance checks and by the vehicle exporter.
Do not skip those checks.

## Checkout and toolchain

Use the immutable public commit from the handoff message in a clean checkout of
`https://github.com/jeremybanka/halo-1.git`. Preserve local changes and existing
outputs; follow any local worktree/storage policy. Initialize its exact private
submodule pin, not the private repository's default branch:

```sh
git submodule sync -- halo64-assets
git submodule update --init halo64-assets
git rev-parse HEAD
git ls-tree HEAD halo64-assets
git -C halo64-assets rev-parse HEAD
```

GitHub access to `https://github.com/jeremybanka/halo64-assets.git` is required.
The last two commands must identify the same asset commit. No AirDrop or iCloud
files are required. The private package adds about 345 MiB of compressed input
chunks; expanded inputs need about 544 MiB, including the assembled enemy bank.

Use Python **3.11** with `port/n64/requirements.txt`. The reference toolchain is:

- libdragon `494f1f586d3d6d5fc65b516a8ce29ccf42f85e15`
- Tiny3D `ec557373e986b5e041cc102a7ff787eb07921937`
- `mips64-elf-gcc` 16.2.0

Set `N64_INST` to the installed libdragon SDK and `TINY3D_DIR` to the built Tiny3D
checkout. The build also needs the libdragon source tree for its RSP queue
configuration. If that tree is not the SDK's sibling `libdragon-src`, pass
`--libdragon-source /your/libdragon-source` to `build.py`.

## Restore the pinned input package

Activate the Python 3.11 environment. Choose a new directory each time:

```sh
python3 port/n64/setup_assets.py --verify
python3 port/n64/restore_pr18_inputs.py --output-dir build/pr18-inputs-001
```

If the checkout has a workspace policy, replace the restore command with its
guarded equivalent; use the main checkout's CLI with `--root` if necessary:

```sh
python3 tools/workspace.py run --output build/pr18-inputs-001 --peak-gib 1 -- \
  python3 port/n64/restore_pr18_inputs.py --output-dir build/pr18-inputs-001
```

The helper verifies all private payloads, compressed and uncompressed chunk
hashes, whole-map hashes and all 32 assembled enemy-bank files. It creates
ignored links from the private bank to the restored caches. Existing matching
maps are preserved; conflicting maps or an existing output directory are refused.
Keep the restored input directory while its links are in use.

The enemy bank combines versioned `assets/enemy-vehicles/bank` files with
`assets/vehicle-lods/bank/vehicle_distance_data.c`. These are exactly the inputs
used by the original release's local `build/map-inputs/enemy-bank` directory.

## Build the expanded release

`--preset release` alone builds the smaller default roster. To reproduce the
full multiplayer and four-encounter Firefight configuration, run:

```sh
python3 port/n64/build.py --preset release \
  --pve-model-bank build/pr18-inputs-001/enemy-bank \
  --pve-crunch --pve-roster --pve-jackal-shields \
  --enemy-vehicle-bank build/pr18-inputs-001/enemy-bank \
  --vehicle-distance-lods --output-dir build/pr18-release-001
```

Both output directories must be fresh. Supply SDK/source flags as above when
your installations are not selected by the environment/default paths.

The original release artifact is
`halo-64-pve-model-candidate-paced30-rspq32k.z64`, 72,581,120 bytes, SHA-256:

```text
8e6ffd2dcb5010c5436b86ee4487b90164a4ac67e852ea67e224ed4f5766d180
```

Record the new ROM size and SHA-256 together with its `.build.json` manifest,
public/private refs and toolchain. Treat a different hash as a result to explain,
not proof of byte-identical reproduction. The intended hardware is SummerCart64
with an 8 MiB Expansion Pak. Existing SD-card contents do not need formatting.
