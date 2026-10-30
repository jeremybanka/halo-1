# First Covenant squad — appraisal prototype

Historical checkpoint: the complete finite mode is now documented in
[FIREFIGHT_LIMITED.md](FIREFIGHT_LIMITED.md). The results below describe the earlier
five-enemy prototype, not the expanded roster.

This isolated prototype stages one minor Elite with a plasma rifle and four
minor Grunts with plasma pistols in Blood Gulch. It supports one to four local
players, real projectiles, player weapons, grenades, melee, deaths, dropped
weapons and player respawning. It is one encounter, not a completed Firefight
mode or campaign port. No wave director, campaign scripts or dropships are added.

## Source boundary

`extract_pve.py` reads the owned a30 cache. `bake_pve_blender.py` skins the original
low/superlow meshes and original animations in Blender. `pack_pve.py` packs them
and extracts the unmodified bodies of `grunt_decide_action`,
`elite_decide_action` and `actor_action_handle_panic_transition` from the original
AI source. Generated art, tag data and function bodies remain in the private
asset worktree.

The source selectors preserve the nearby-Elite suppression of mild Grunt panic,
the forced leader-loss panic transition, and the Elite's shield-dependent guard
state. Source tag values supply vitality, shield recovery, perception parameters,
weapon range, burst/pause cadence, aim error, damage modifiers and panic duration.
Movement speed comes from source animation root motion; Elite melee damage and
its hit time come from the source damage tag and animation keyframe. Source hand
markers attach the actual weapon models. Grunt armor uses the biped's orange
color permutation; Elite armor uses the minor variant's color change.

This is **not the complete original AI engine**. `pve_source.inc` supplies compact
platform services for the original selectors. Perception/action decisions run at
5 Hz, staggered across actors; movement and combat run on the existing 30 Hz
simulation clock. Navigation uses a baked 25 by 25 local grid validated with the
port's capsule solver. Pursuit uses last-seen positions. Retreat follows the
local graph; it is not the original tactical cover or squad-maneuver system.
Scripts, conversations, boarding, AI grenade throwing and several danger/evasion
handlers are explicitly disabled. Enemy bullet hit regions currently approximate
the authored capsule and head, rather than the animated source damage mesh.
There are no Covenant dialogue barks in this first encounter. Firing-position
coordination and friendly-line avoidance are also incomplete: in the longer
playable smoke test, the Elite could shoot through intervening Grunts and kill
them. Friendly damage remains enabled; this is an appraisal limitation.

NPC storage is independent of the four controller/camera slots. Animation and
attachment preparation are shared between viewports, with fenced vertex buffers,
original distance LODs and reuse of unchanged decoded poses. Dead actors remain
in the bounded pool; starting a new match restarts the squad.

## Blood Gulch ground correction

The visual sinking was a measurable mismatch between the reduced render ground
and the unchanged source collision floor. At the squad starts the render surface
was 0.043–0.098 world units above collision; a Grunt's authored collision height
is 0.55. Source animation foot heights were near zero.

`conform_bloodgulch_ground.py` creates an **isolated map-bank candidate** restoring
the original ground material triangles. Structures and collision remain intact.
All map sections 3–22 are checked byte-for-byte against the baseline. Ground
triangles rise from 623 to 2,425; total map triangles rise from 3,058 to 4,860;
packed vertices rise from 5,036 to 6,658 and chunks from 225 to 248. The canonical
multiplayer map bank is not replaced.

At 1,764 samples in the encounter's surrounding 20 by 20-unit region, render minus
collision height changes from a maximum +0.2593 to +0.001895 units. The corrected
minimum is -0.002393 units, consistent with 1/256-unit vertex packing. The wider
map still needs visual traversal appraisal; the numeric sample is not a claim
that every possible map position was tested.

## Reproduction and acceptance

Build with `port/n64/build.py --pve-squad --pve-players 1|2|3|4`, the installed
libdragon/Tiny3D paths, and a separate `--output-dir`. This build needs the
Expansion Pak. Pass `--map-bank-override` with the generated ground candidate to
include that correction. The normal build remains unaffected when `BG_PVE` is
absent. `--preset release` supplies paced presentation for the playable ROM.

`--pve-qa 2` repeats a fixed-seed 15-second encounter. Players stand at saved
positions; player one fires at the Elite after six seconds. This uses ordinary
weapons, damage and deaths, with no hidden invulnerability or forced kill.
`--pve-photo-tick` advances that fixture at 30 Hz and freezes its simulation and
presentation for a reproducible native photo. The seed, tick and unit positions,
angles, crouch state and vitality are logged at startup.

`port/n64/test_maps.py --pve` compiles the production simulation with ASan/UBSan,
exports the local navigation bank, checks clear staging positions and source
panic transitions, runs two minutes for each player count, and verifies that the
scripted pistol engagement kills the Elite. `--modes --target-math` separately
checks the existing multiplayer modes and spawn-weight source reference.

The local appraisal contains native Ares screenshots, the reduced/restored-ground
pixel comparison, raw timing logs, ROM hashes, build manifests and the playable
ROM. The performance fixtures use 320 by 240 NTSC, the Expansion Pak, profiling
overlays and uncapped presentation. They are emulator observations, not a new
hardware measurement. The empty-arena comparison shares staging but has no enemy
combat; the terrain comparison retains the same squad and collision.

## Appraisal measurements

The final matched Ares runs averaged 50.8 FPS with one player, 28.0 with two and
17.0 with four. The four-player empty arena averaged 35.2 FPS; the same squad on
the reduced ground averaged 19.0 FPS. Each result uses 30 one-second observations
after discarding five warm-up samples. These are uncapped diagnostic ROMs; the
playable release ROM uses the normal paced presentation.

In the four-player samples, the mean drawing/submission phase was 30.44 ms,
scene preparation 7.33 ms and simulation 9.12 ms. NPC decisions/perception/paths
accounted for 1.26 ms within simulation; NPC movement/combat for 1.80 ms within
simulation; NPC animation/attachments/visibility for 4.43 ms within preparation.
These are sampled CPU phases, not separate RSP/RDP utilization measurements.
The complete four-camera frame submitted about 29,470 vertex loads on average.

The final two-player photo was recaptured after the last melee fix and matched
the saved corrected-ground photo exactly (zero changed pixels). The playable
ROM was booted and observed running live combat; pause-menu control was not
manually exercised in the isolated emulator input profile. Host tests cover
squad reset and player-count changes.

Local review: `build/n64-pve-squad/comparison.html` in the original checkout,
with raw logs, build manifests and hashes in its adjacent `evidence/` directory.
The compact timing records and checkpoint identity are also checked in under
[`benchmarks/pve-squad/`](benchmarks/pve-squad/).

Stop here for visual/gameplay and performance appraisal before broadening the AI,
adding waves or adopting the terrain change into the normal multiplayer build.

## Firefight shell

The integrated build (`--firefight --preset release`) boots into the normal
front end. Firefight replaces the disabled Game Demos slot on the main menu.
It uses the four-port profile/ready screen, including P3/P4 and non-P1 hosts,
then map selection with Blood Gulch as the only enabled map. One, two, three and
four players are supported. Map acceptance goes directly to the pregame
countdown; there is no competitive game-type selection for Firefight.

The encounter remains one Elite and four Grunts. Restart recreates the squad and
restores player staging; quitting clears the NPC pool and frees its render
buffers. Returning to multiplayer restores the normal mode rules and full map
catalog. Cancelling quit resumes the current encounter. No wave director,
additional enemies, progression or new combat behavior is introduced here.

The entry announcement is the original **Halo 3: ODST** "Firefight" line, from
Yazite's [MCC raw-announcement recording](https://www.youtube.com/watch?v=0ZbG4kmbUEk).
The uploader identifies it as a direct MCC export; the retrieved audio passed
through YouTube Opus encoding, so this is not a bit-exact cache extraction.
Only the opening line is retained (0–1.04 seconds). It is converted to mono
11,025 Hz signed 8-bit PCM with a 20 ms tail fade and streamed from ROM through
the existing announcer channel. It plays after match setup, once per launch,
not on resume or restart. The private bank includes the isolated WAV, shipped
PCM and provenance/hashes in `assets/firefight/provenance.json`.

The integrated candidate requires an Expansion Pak. The existing build without
`--firefight` retains its multiplayer-only configuration. The supplied review
ROM uses the same restored-ground candidate as the squad appraisal. This does
not overwrite the canonical multiplayer map bank.

Additional validation:

- `test_firefight_frontend.c`: all 32 nonempty roster/host combinations,
  disabled-map rejection, backing out, countdown, quit/resume, and launch-time
  capability rechecks.
- `test_maps.py --pve`: two-minute simulations at **all four** player counts,
  restart staging, Firefight → CTF → Firefight lifecycle, and prior combat tests.
- `test_maps.py --modes --target-math --with-pve`: the full multiplayer suite
  with the NPC storage/code compiled in but inactive.
- `test_announcer_stream.c` with `BG_TEST_PCM_BYTES=11395`: 2,288,763 stereo
  frames byte-identical between streamed and resident playback of the shipped
  Firefight sample, including restart, final partial buffers and completion.
- `--firefight-qa 1|2|3|4`: native controller-edge routes through join, map
  restrictions, cancellation, launch, restart, quit/resume and multiplayer return.
  `--firefight-photo main|join|map` holds a menu within that route for photos.

The Firefight review package is `build/n64-firefight/` in the original checkout.
