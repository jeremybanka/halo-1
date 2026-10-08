# Xbox shield feedback on N64

The owned Xbox Blood Gulch cache and reconstructed source drive this port.
`extract_shields.py` exports a provenance report, reduced depletion/spark sprites,
and the low/depleted HUD warning samples. Extracted assets remain under ignored
`build/n64`, never in Git.

## Original behavior

- `characters\\cyborg_mp\\cyborg_mp` exports recent shield damage to A_in and
  maps it through the `very_early` (fourth-root) function to B_out.
  `characters\\cyborg\\shaders\\shield hit` uses B_out for intensity.
- `source/objects/damage.c` sets current shield damage to 1 after a shield hit
  and decays it by 1/60 per 30 Hz tick. Depletion clears the modifier and emits
  `characters\\cyborg\\cyborg shield depletion`: gold (255,213,85) clouds
  lasting 0.25–0.3 seconds and sparks lasting 2–2.25 seconds.
- Full shields, damaged shields after the flash fades, normal recharge, and
  resting overshields have no persistent full-body shader glow. The cyborg
  collision tag has no recharging effect. CE does not use the later games'
  constant white overshield aura. Shield vitality is clamped to 1 for exported
  object shader functions (`source/objects/objects.c`).
- The collision tag specifies six seconds of stun and four seconds to recharge.
  Repeated health damage while empty restarts the delay. Recharge does not heal.
- `object_double_charge_shield` starts an overshield fill (100 HUD points/sec)
  capped at 300, protects the player during charging, and rejects a new pickup
  above 100. The extra layers decay at 100/45 points/sec in multiplayer. Hits
  during protected charging can still flash. Respawn clears all transient state.
- `source/interface/hud_unit.c` draws extra HUD layers red, then green. It
  triggers charge while charging, low below 25 but above zero, depleted at zero,
  and silences these states on death. Low and charge may overlap.
- `source/interface/hud_sounds.c` maintains looping sounds by state. The owned
  tags provide 0.5-second low/depleted fades and a 0.1-second recharge fade-out.
  The shield depletion effect has no separate world sound part: the impact
  sound and depleted HUD loop provide the break/down feedback.

## Deliberate N64 simplifications

The hit modifier mixes the source orange perpendicular tint into the existing
opaque Spartan draw, with a small shimmer. It follows the source fourth-root
intensity envelope. There is no second skinned shell, extra body triangle, or
shader texture lookup. Xbox's scrolling volume noise and blue grazing-angle
color are not reproduced. Team color and mesh shading remain underneath.

A break emits two reduced source clouds and four sparks instead of the original
6–8 clouds and 10–20 sparks. They originate at the break position, independently
of later player movement. Camera-facing clouds sit at the near surface of the
shield envelope so the torso cannot hide their centers. They retain depth
occlusion against the world. All share the existing 32-quad per-view effects
budget and leave four quads available for the first-person weapon effects.

Original shield_hit and shield_charge PCM are reused. Low/depleted loops are
mono signed 8-bit at 5512 Hz (32,637 sample bytes together); the two 16×16 RGBA
sprites add 2048 bytes. These alarm tones accept a lower sample rate to fit 4 MiB.
Three protected mixer channels aggregate identical couch HUD states, avoiding
four copies of the same alarm and gunfire stealing them. Split-screen column
panning is averaged across the affected players. The tag fades are retained.
Charge stops when interrupted, fully charged, dead, or at match completion.
Inactive shield states skip fade math. The mixer reuses each scaled stereo
sample until its source cursor advances, which saves work for the 5512/11025 Hz
clips without changing PCM output or playback phase. The 17-channel equivalence
test covers 2,472,207 stereo frames, including rate changes, looping and clipping.
The regular impact sound is now shield-hit driven; unshielded health damage
cannot produce a false shield impact sound.

## Build and verification

```
build/n64-python/bin/python port/n64/extract_shields.py
build/n64-python/bin/python port/n64/blam/test_vehicle.py
build/n64-python/bin/python port/n64/build.py --shield-qa 0 --validate
build/n64-python/bin/python port/n64/build.py --shield-qa 1 --validate
build/n64-python/bin/python port/n64/build.py --shield-qa 2 --validate
build/n64-python/bin/python port/n64/build.py --vi-benchmark --paced30 --paced30-buffers 5
build/n64-python/bin/python port/n64/build.py --paced30 --paced30-buffers 5
```

The fixtures use real projectile collision/damage, a real overshield pickup,
and production ticks. Only player placement and inspection cameras are staged.
Page 0 shows full / hit / break / overshield hit; page 1 shows full / recharge /
low recharge / resting overshield from a second angle; page 2 shows a quietly
damaged shield, unshielded health damage, and a resting overshield after sparks
expire. Their HUD bars report the inspected actor's actual state. Frozen QA is
not a performance measurement. Release timing uses the separate quiet replay.

Host sanitizer tests cover shield transitions, recharge interruption, overshield
protection/non-stacking/decay, death/respawn, warning state overlap, PCM loop
phase, tagged fades, and pan. Ares captures and measured results are in
`build/n64/shield-audit/comparison.html` and its manifest.
