# Firefight Covenant roster appraisal

Read [the report](../../FIREFIGHT_ROSTER.md) for results, source boundaries and
measurement scope. All commands run at the isolated checkout root with its
Python 3.11 environment. Private source caches and Blender are needed to regenerate
animations; the archived bank suffices to rebuild the ROM.

```sh
build/n64-python/bin/python port/n64/extract_pve_roster.py \
  --maps build/assets/halo-retail/maps \
  --base halo64-assets/assets/covenant-symmetry/source \
  --output build/firefight-roster/source
```

In Blender, load `port/n64/bake_pve_blender.py` and call
`bake(source/'squad-source.json', source/'rebaked.json.gz', model_names=['grunt','elite'])`.
This skins the accepted corrected meshes with source alternate clips, without
editing the active Blender scene. Then:

```sh
build/n64-python/bin/python port/n64/pack_pve_roster.py \
  build/firefight-roster/source --output build/firefight-roster/bank
build/n64-python/bin/python port/n64/benchmarks/firefight-roster/audit.py
build/n64-python/bin/python port/n64/test_maps.py --firefight --roster \
  --output-dir build/firefight-roster/host
build/n64-python/bin/python port/n64/test_maps.py --collision --roster --target-math \
  --output-dir build/firefight-roster/collision-host
build/n64-python/bin/python port/n64/test_maps.py --pve --roster \
  --output-dir build/firefight-roster/pve-host
build/n64-python/bin/python port/n64/test_maps.py --firefight \
  --output-dir build/firefight-roster/default-host
```

`run.py build VERSION` builds each player count for `candidate`, `roster` or
`ordinary`; `photos` builds the 46-page native photo ROM and `play` the menu-based
30 FPS release candidate. It pins the SDK, tiny3d and corrected Blood Gulch bank
used by prior appraisal runs. `capture_all.py` runs photos and all three candidate
matrices serially. Each capture owns and stops only its own Ares subprocess.
Ares needs desktop/native process access; a sandbox-only launch can exit without
producing measurements. Settings are saved as `build/firefight-roster/ares.bml`.

The saved `baseline` ROMs/logs were built **before** this pass's runtime edits,
from parent 60f285452d5863a4175b590539138acba791e78e and private parent bccde59f93e785de43dddae8a401a85bdaba406a.
Rebuilding `baseline` on the changed tree is not a reproduction of those original
captures. Use those parents and the saved manifests. The final candidate manifests
record dirty-tree input hashes, so the parent commit alone is not their identity.
`input-checks.json` verifies that production inputs still match all fourteen final
native builds. Only expanded host assertions in `test_pve_roster.inc` postdate
those builds; that test include is not compiled into the ROM.

QA 4 preserves the old crowded composition; QA 7 has the new variants at the same
caps, staging, input route and 600-tick reset. QA 3 is ordinary opening play.
All three use audio, collision profiling, NPC preparation profiling and uncapped
rendering. CPU phase samples are not independent GPU durations.

```sh
build/n64-python/bin/python port/n64/benchmarks/firefight-roster/collect.py
build/n64-python/bin/python port/n64/benchmarks/firefight-roster/compare.py \
  /Users/jem/dojo/halo-1/build/n64-firefight-roster
```

`collect.py` preserves per-case ROM/manifest/log hashes. `compare.py` verifies all
46 native readbacks, records the four cameras and generates near/selected-LOD
diffs. Audio previews are the packed PCM payload, not emulator audio recordings.
The private archive contains the capture log and resulting images; public logs
contain timing/counters, not frame pixels or source art. `asset-checks.json`,
`pixel-checks.json`, host logs and `results.json` retain the evidence.
