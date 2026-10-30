# Selectable Blood Gulch fights

The Firefight flow is now players → map → fight → countdown. **Onslaught** is
selected by default. **Gauntlet** is available in builds containing the CE roster.
The countdown shows the selected name; backing out, returning from results and
restarting a live match preserve the selection. Multiplayer's type selector is
unchanged. Both fights require the Expansion Pak and use Blood Gulch.

## Onslaught

This names the existing encounter without changing its schedule, cap, formation
variants, arrival pacing, vehicles, resources, score or victory rules. The 15-wave
totals remain 276 / 337 / 395 / 456 enemies for 1 / 2 / 3 / 4 humans, before the
bonus. Simultaneous caps remain 6 / 8 / 10 / 12.

## Gauntlet

Gauntlet keeps the existing solo formation schedule for every party size:
**276 enemies**, consisting of 165 Grunts, 90 Elites (including vehicle pilots),
17 Jackals and four Hunters across the survival portion. It uses 3 / 4 / 5 squads
per ordinary wave in rounds 1 / 2 / 3, with one extra squad in wave four and each
boss wave. Every party size gets the same six-second minimum reinforcement gap.
The cap is six solo or eight with 2–4 humans. Pending arrivals count against it;
the two-Hunter limit and complete-squad admission checks remain.

Player count changes source loadouts at spawn, not actor quantities or invented
health/damage multipliers:

| Players | Promotion rules |
| --- | --- |
| 1 | Existing solo schedule and loadouts. |
| 2 | Minor Elites, Grunts and Jackals become their corresponding Majors; stronger existing specialists remain. |
| 3 | Major rifle/Needler Elites become Spec Ops; Major Needler Grunts become Spec Ops; minor cloaked rifle Elites become cloaked Majors. Plasma-pistol Grunts and shield-bearing Jackals remain in the mix. |
| 4 | Eligible lead rifle Elites become gold Zealots. Squads without a fuel rod promote one eligible plasma-pistol Grunt to a fuel-rod Grunt, retaining other plasma pistols and Needlers. |

Original sword, fuel-rod and cloaked roles are retained. At most one fuel rod is
assigned per formation. Species and squad sizes stay identical across party
sizes, and every tier retains all four enemy species. Existing source variants
supply vitality, shield behavior, weapons, firing cadence, grenade rules, poses
and dialogue; rank alone does not give a custom stat boost. Pilot rank changes
the occupant; mounted weapons still use their vehicle-specific source profiles.

The same 3 rounds × 5 waves, Ghost/Banshee/Shade/Wraith sequence, shared reserves,
round recoveries, Catch/Cloud adaptations, drops, scoring and 60-second Grunt
bonus apply. Bonus Grunts are not promoted. New shots, hit geometry and animations
use the existing assets. No new art or audio bank is needed.

This is initial challenge tuning. Automated kills establish lifecycle correctness,
not that human completion is fair or that a four-player party receives exactly
four times the opposition strength. This pass makes no new FPS claim.

## Validation and reproduction

`benchmarks/firefight-fights/test.py` runs ASan/UBSan host checks against the
resident vehicle/roster banks. It compares every Onslaught packet to the frozen
pre-selection function at `031e79f5`, verifies its original counts and variants,
and exercises all four Gauntlet tiers through 15 waves and the bonus. It checks
source rank/weapon/vitality application on both arrival routes, conservative
capsule bounds, diversity, quantity, fuel limits, restart, defeat and PvP return.
The existing full Firefight, roster, enemy-vehicle and frontend regressions also
run. Both roster-enabled and base menu builds cover every controller/host roster,
both fight choices, unavailable-choice guards, back/results, countdown and quit.

`refresh_maps.py` reproduces Blood Gulch byte-for-byte before updating its
`game.c` provenance hash; only the restart dispatch changed in that source file.
The first host regression attempt lacked `.modes64` links in its isolated fixture;
those metadata links are now present, and the full CTF-return check passes.

Run with the local Python environment and a writable compiler temporary directory:

```
TMPDIR=/private/tmp/halo-vehicle-simulation build/n64-python/bin/python port/n64/benchmarks/firefight-fights/test.py
TMPDIR=/private/tmp/halo-vehicle-simulation build/n64-python/bin/python port/n64/benchmarks/firefight-fights/refresh_maps.py
TMPDIR=/private/tmp/halo-vehicle-simulation build/n64-python/bin/python port/n64/benchmarks/firefight-fights/run.py build
build/n64-python/bin/python port/n64/benchmarks/firefight-fights/run.py capture
```

The scripted native shell checks both selection/countdown pages, launches
four-player Gauntlet, restarts it, cancels/quits and returns to multiplayer.
Its readback is diagnostic-only; the playable build has ordinary controller input.
Native results and source/ROM provenance are recorded beside the runner after
capture. Private raw framebuffer logs and the playable ROM stay under `build/`.
