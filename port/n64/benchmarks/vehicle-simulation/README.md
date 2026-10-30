# Shared vehicle clearance and Wraith firing checks

Local appraisal on top of the Wraith/Shade distance LOD candidate. Geometry,
actor counts, physics rate and weapon tags are identical in both versions.
The baseline flag restores scalar clearance and cooldown obstruction checks.

From the isolated `build/n64-pve-squad/source` checkout:

```sh
build/n64-python/bin/python port/n64/benchmarks/vehicle-simulation/test.py
build/n64-python/bin/python port/n64/benchmarks/vehicle-simulation/test.py --target-math
build/n64-python/bin/python port/n64/benchmarks/vehicle-simulation/run.py build
build/n64-python/bin/python port/n64/benchmarks/vehicle-simulation/run.py capture
build/n64-python/bin/python port/n64/benchmarks/vehicle-simulation/collect.py
build/n64-python/bin/python port/n64/benchmarks/vehicle-simulation/viewer.py
```

SDK, Tiny3D, map override and private bank paths are explicit in the runner.
Optional case names select a subset. Native captures run serially and terminate
only their own Ares process. The runner removes only regenerable DFS, objects
and frontend-file copies after verifying the completed ROM against its manifest;
all compiler inputs, generated diagnostic sources, ROMs and logs remain.
Timing ROMs are losslessly gzip-compressed after hash verification and restored
only during capture to keep the nearly full disk usable. The playable ROM stays
uncompressed; the collector verifies decompressed ROM bytes against the manifest.

The host harness compares against the actual pre-change gameplay sources at
`031e79f57ba49ab32d507a1c97aee118cbf328d2`, not a second copy of the new algorithm.
It checks 650,000 scalar/packet rays across all thirteen maps, 20,000 ballistic
cases, 3,000 Wraith decision boundaries and 9,600 complete gameplay ticks.
It uses AddressSanitizer/UBSan with strict and target-style math separately.
The original scalar world ray API continues to serve queries needing a normal
or material and the optional original-BSP gameplay path.

Sixteen fresh live cases cover QA8 (four vehicles plus infantry) and QA9 (one
Ghost plus infantry), 1–4 players, before/after. Each has 45 observations; discard
five warm-ups for FPS, report engaged and all-player-alive scopes. Damage,
deaths, respawns and QA8's tick-600 restarts remain real. Faster execution can
sample different combat windows; small single-pair FPS differences are not
statistical evidence of a regression or gain.

`COLLISION`, `VA_AI` and `VA_PHYS` integrate completed 30-tick windows. Child
buckets overlap their parents. `aim_us`/`path_us` split Wraith analytic aiming
and world-segment validation; `path_calls` counts actual obstruction passes.
`packet_calls` counts shared five-lane queries, while `ray_calls` retains logical
lane counts. `arc_pause_us` includes the retained aim during cooldown and is
not entirely wasted work in the candidate. Human/projectile/physics costs
remain separate from vehicle AI.

The two `verify` builds execute 1,200 fixed ticks with scalar and frozen-trajectory
oracles, hashing state/events/RNG every tick. They are excluded from FPS conclusions.
All forty 30-tick checkpoints and nine final framebuffer pages must match.
Holding rendering until the final tick avoids frame-rate-dependent refreshes
of pickup visibility timers; no pickup or other gameplay code is changed.
Photos freeze the same four cameras at ticks 60 and 180, with nine full/omission
pages each. All before/after pixels must match, including the 16-bit framebuffer
alpha bit, as must camera/hull states and repeat frames.

All native measurements use Ares v148, NTSC 320×240, 8 MiB and audio enabled;
they are not new SummerCart64 measurements. The playable candidate retains the
maintained paced 30 FPS release preset. Public evidence contains numbers,
stripped logs, scripts and hashes; raw frames and source-derived images remain
in local/private artifact storage. This pass stops for appraisal without a push.
