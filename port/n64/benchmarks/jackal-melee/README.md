# Jackal shield melee material regression

Ordinary frontal gunfire blocked in the investigated cases. Melee had a separate,
reproducible failure: its 25 rays selected a shield polygon, then discarded that
polygon's material before applying damage. Damage fell back to the Jackal's
unshielded indirect material. One observed strike removed 40 health while leaving
100 shield intact. Passing the selected hit region to damage preserves the
authored shield, body and backstab rules.

`results.json` records the source, asset and result hashes. Host ASan/UBSan checks
exercise the actual melee selector: five shield-face strikes, a depleted shield,
an exposed-body strike and a backstab, each at four actor yaws. The base bank runs
32 cases; the expanded bank runs 64 across Minor and Major Jackals. Existing
shield/body interception, damage flash, EMP, 15-second recharge and corpse
checks also run. The shared gameplay change is recorded against the original
GUNGNIR appearance certificate, with character payload/renderer gates retained.

The native fixture uses the same acceptance cases and production gameplay,
collision, damage and renderer. It performs one attack every 45 ticks. The
control compiles `game.c` from PR #21 and deliberately fails the shield-health
assertion on case zero; this is a regression-test failure, not a newly discovered
CPU crash. The repair must complete all 64 cases without assertions or CPU
exceptions. These controlled cases are separate from the active three-player
combat stress runs recorded in `../firefight-zoom`.

Use fresh output paths for each run. From the checkout root:

```sh
python3 tools/workspace.py run --output build/jackal-melee-host --peak-gib 0.4 -- \
  build/n64-python/bin/python port/n64/test_jackal_melee.py \
  --output build/jackal-melee-host
python3 tools/workspace.py run --output build/jackal-melee-native --peak-gib 1 -- \
  build/n64-python/bin/python port/n64/benchmarks/jackal-melee/build_fixture.py \
  --output build/jackal-melee-native
python3 tools/workspace.py run --output build/jackal-melee-capture --peak-gib 0.3 -- \
  build/n64-python/bin/python port/n64/benchmarks/jackal-melee/capture.py \
  --build build/jackal-melee-native/rom --output build/jackal-melee-capture \
  --settings /path/to/ares-settings.bml
```

Build a separate control with `--before
34a9f41a025df283b06c55bf16bd5bbef6b50c42`, then capture with
`--expect-failure`. The capture packages an identical executable and Blood Gulch
resources below Ares's 64 MiB ISViewer limit by omitting other maps. Each capture
owns and terminates only its own emulator process. Physical M64 acceptance at
Insane is still pending.

`refresh_maps.py` reproduced Blood Gulch byte for byte and verified every
existing map payload before proposing the new gameplay dependency digest. The
private asset update changes only that digest and its snapshot-manifest hash.
No geometry is changed. Proposed metadata stays in the declared output until
reviewed and promoted. All private art, ROMs and native logs remain local.
