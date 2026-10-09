# Exact vehicle pose reuse

`prepare_vehicle` compares kind, position, yaw/pitch, turret yaw/pitch and wheel
phase as nine raw 32-bit words. Distinct signed zeros remain distinct keys. A
miss runs the unchanged `compute_vehicle_pose`, including all rigid-part
transforms and conservative bounds.

Each vehicle records which of the two geometry slots contains that exact key.
The first hit in the other slot copies its base and active part matrices from
the previous slot. Later hits need no copy. The existing RSP fence still guards
every destination write; the source slot is read-only to both CPU and RSP.
Cache state occupies 480 bytes for 12 vehicle slots and allocates nothing at runtime.

Vehicle union and part bounds are shared CPU data with no writer outside the
miss path. Inactive vehicles can retain their entry; reactivation and reset
remain correct because every input to the computation is in the key. In
particular, resetting wheel phase changes the key when necessary. Immutable
rig/bounds tables need no version field.

Run `python3 port/n64/test_vehicle_pose_cache.py` to compare the actual cached
function against its miss path in independent output banks. The 75-second
portable replay produces 82.8% exact reuse at one render per 30 Hz tick, with just
15 inter-slot copies. Combat reuse is 92.2%; two renders per tick yield 91.4% reuse.
Varied resets, kind changes, reactivation and wheel/turret poses bring the test
to 109,485 exact fixed-coefficient and bounds comparisons under ASan/UBSan.
Host trig is substituted equally in both paths; these counts establish
equivalence and reuse, not a target performance improvement.

The target snapshot at tick 1148 also matches the pre-cache renderer exactly:
all 427,500 compared game pixels are unchanged. The raw capture, ROM hashes and
comparison are in `build/n64/performance-audit/vehicle-pose-cache/pixel-results.json`.
The quiet 75-second Ares replay still missed 14 display deadlines (13 during
vehicle scenes), versus 15 before caching. Reuse alone therefore does not
establish sustained nominal 30 FPS.

Per-second heap walks and PERF/PHASE logging now require `BG_PROFILE` and are
excluded from ordinary gameplay and quiet VI measurement. Rendering, sound,
simulation ticks and presentation deadlines are unchanged.
