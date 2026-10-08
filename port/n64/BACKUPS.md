# Halo64 backups and private assets

The public source branch is `jeremybanka/n64-blood-gulch` in
`https://github.com/jeremybanka/halo-1`. It contains the runtime, extraction,
reduction and repair scripts, recipes, and documentation. The customized asset
payloads are pinned by the `halo64-assets` Git submodule:

`https://github.com/jeremybanka/halo64-assets` — **private**.

The submodule stores the current reduced JSON meshes, corresponding Blender
scenes, texture/reference inputs, packed animation and audio banks, generated C,
provenance reports, and six menu-art adaptations. Raw/decompressed `.map` caches
and extraction logs are excluded. Privacy does not imply ownership of the
original Halo data or attributed ModRetro photographs. Keep the bank private.
No asset bytes are included in the public submodule entry: it contains only the
private repository URL and pinned commit hash.

## Use the bank

```sh
git submodule update --init halo64-assets
python3 port/n64/setup_assets.py --verify
```

GitHub access to the private repository is required. The setup command links:

- `build/n64/assets` → `halo64-assets/assets`
- `build/n64/generated` → `halo64-assets/generated`
- `build/n64/frontend-files` → `halo64-assets/frontend-files`

Menu-art links under `port/n64/menu_art/` also point into the private bank.
`build.py` connects the bank automatically when initialized. Existing real
asset directories are never discarded; explicit adoption archives matching
banks before linking. Extraction and packing continue to use the established
paths and consequently update the private checkout.

To archive matching old banks before adopting a submodule, use:

```sh
python3 port/n64/setup_assets.py \
  --archive-existing build/n64/_asset-snapshots/initial --verify
```

Local source-cache links are restored from that archive when it is present.
On a different machine, supply/extract the owned source disc to regenerate
those caches. They are unnecessary for accessing the saved meshes, but original
cache hashes remain part of extraction/build provenance checks.

## Commit asset changes

Review and commit the private bank first, push it, then commit and push the
updated submodule pointer in the source repository. This order ensures that the
public pin always identifies an available private snapshot:

```sh
git -C halo64-assets status
git -C halo64-assets add assets generated frontend-files menu_art
python3 port/n64/snapshot_assets.py
git -C halo64-assets add bank-manifest.json
git -C halo64-assets commit -m 'Describe the reviewed asset change'
git -C halo64-assets push
git add halo64-assets
git commit -m 'Pin updated Halo64 asset bank'
git push
```

`snapshot_assets.py` records the tracked private payload files' sizes and
SHA-256 checksums; `setup_assets.py --verify` checks that snapshot. Re-run the
manifest after any bank changes. The manifest records the source commit before
the corresponding public pointer commit, avoiding a circular commit dependency.

## This Mac's iCloud archive

The output/audit tree lives in:

`~/Library/Mobile Documents/com~apple~CloudDocs/Halo64/n64`

The workspace's `build/n64` is a symlink to it. Existing gallery URLs, scripts,
ROM names and recording paths continue to work. The private asset banks are
local Git checkouts, reached through three links inside that output tree;
iCloud holds their preserved pre-submodule snapshots too. Other machines
should create their own asset links with `setup_assets.py` rather than use this
Mac's absolute symlink targets.

`Halo64/source/` contains a checksum-verified copy of the supplied Xbox ISO.
`Halo64/backups/` holds a complete pre-publication source Git bundle and a
migration manifest with file hashes. The atomic same-volume migration preserved
all file inodes, sizes and symlink targets. Original local asset directories
were retained under `n64/_asset-snapshots/initial/` before linking the new bank.
Historical comparisons, videos, experiment data and ROMs remain there for
continued contributions. Native tools write through the symlink as before.
macOS handles upload to iCloud; moving files into that directory does not itself
confirm that every byte has finished uploading. Avoid evicting the archive while
actively building or recording from it.

## Publication cleanup

Before the first N64 branch push, its unpublished history was rewritten to
remove all six menu PNGs. Their bytes are preserved in the private bank and the
complete original source Git bundle. The public checkout now contains relative
links to them. Earlier source hashes in audit and release manifests describe the
original verified builds and were deliberately retained.
