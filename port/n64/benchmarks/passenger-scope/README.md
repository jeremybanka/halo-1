# Passenger scope overlay

The world camera already magnified shotgun zoom, but `hud.c` rejected scope
masks, markings and magnification labels whenever `vehicle >= 0`. Use the
production personal-weapon seat service instead: a stable Warthog passenger can
scope; drivers, gunners, dead players and seat transitions cannot.

The pre-fix host check fails at the passenger overlay assertion. The repaired
check passes 648 states in each of the base and expanded banks with ASan/UBSan.
It uses the actual HUD predicate and the real game/seat service.

Matched native Ares v148 NTSC/8 MiB captures cover 15 pages and 31 camera poses.
Pages 0–9 (the original on-foot scope cases) are pixel-identical. Pages 10–12
restore passenger pistol 2× and sniper 2×/10× overlays. Pages 13–14 restore the
wide P3 and narrow P2 passenger overlays in three-player Warthog crews; the
other players' viewports are pixel-identical. No assertion or CPU exception was
recorded. Frozen photos check rendering rather than frame rate.

`results.json` records native pixel hashes and changed-pixel counts. ROMs,
images and full logs remain locally pinned under
`build/shotgun-scope-20261113-*`; no source-derived images or ROMs are committed.
The logging cartridge keeps the same executable and Blood Gulch inputs while
omitting other map filesystem payloads to fit Ares's ISViewer address limit.

Run the host regression in a fresh guarded output:

```sh
python3 tools/workspace.py run --output build/passenger-scope-host-NEW --peak-gib 0.4 -- \
  build/n64-python/bin/python port/n64/test_vehicle_scope.py \
  --output build/passenger-scope-host-NEW
```

Build `port/n64/build.py --pve-squad --scope-qa` with the verified expanded enemy
bank and its normal crunch/roster/shield/vehicle flags in a fresh output. Capture
its 15 pages with known NTSC/8 MiB/Homebrew Ares settings:

```sh
python3 tools/workspace.py run --output build/passenger-scope-native-NEW --peak-gib 0.3 -- \
  build/n64-python/bin/python port/n64/benchmarks/passenger-scope/capture.py \
  --build build/passenger-scope-build-NEW --settings path/to/ares.bml \
  --output build/passenger-scope-native-NEW
```
