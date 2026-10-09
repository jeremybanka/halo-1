# Blood Gulch fidelity closure pass

This pass addresses the remaining source-audit items from the power-up/vehicle
review. Retail Xbox comparison was explicitly deferred by the user on October
9, 2026. The extracted disc tags and reconstructed source are evidence about
this implementation; they are not a retail gameplay recording.

## Mounted weapons and damage

The Warthog gun, Ghost bolts, Scorpion cannon and secondary machine gun,
Banshee bolts and fuel rod now use their original trigger and damage profiles.
Extraction retains firing-rate ramps, error cones, chamber flags/times,
projectile speed/range/gravity, shield/body modifiers, hull materials,
vehicle passthrough penalty and rider damage fraction. Projectile velocities
from the map are per tick and are converted to the adapter's units per second.
The Ghost magazine's chamber time is not applied: its every-round chamber flag
is clear. Cannon and fuel rod retain their four-second chamber interval.

Direct hull hits transfer damage to riders before hull resistance, following
`damage.c:children_take_damage`; the first three vehicles use 0.18 and Banshee
uses zero. Fractional hull vitality avoids rounding small impacts into excessive
damage. Material comes from the struck original collision surface. The existing
area-damage cover path remains separate from direct-hit transfer.

Deliberate limits: destructible multiplayer Warthog/Ghost/Scorpion hulls remain
the requested demake extension (the original multiplayer hull body material is
invulnerable). A zero/unlimited projectile range is bounded to at least 100 world
units. Muzzle placement remains the existing mounted-camera adapter.

## Animated hit geometry and contacts

Original cyborg collision surfaces replace the three head/body/leg spheres.
The 150 vertices and 236 triangles retain their authored hit regions and follow
the same sampled animation timeline as the visible body, including crouch,
landing, weapon ready, seat entry, riding and exit. Frames live in a 792,528-byte
ROM bank; two frame endpoints and four current collision poses are resident.
Per-bone bounds reject rays before triangle tests. Aim assistance still uses
its existing approximate target pill; physical bullet hits use the animated
surfaces.

Vehicle collision surfaces retain materials and are refitted for turret, barrel
and hatch transforms before applying the live rigid-body basis. One cache per articulated model reuses poses, sized to each mesh so all three
use approximately the memory of the former two maximum-sized caches. Only changed
rigid parts and their BVH ancestors are refitted. Joint transforms are calculated
per part, not per vertex. Conservative broad-phase radii bound each part around its own pivot;
no triangles are discarded. Wheel spin is not applied to hit surfaces.

Standing players resolve against hull surfaces, keep a local support anchor,
move with a translating/rotating vehicle and detach when jumping. Player/player
capsules separate symmetrically and remove closing velocity. The source biped
collision shove, upward bias, live-player halving and collision damage replace
the previous speed-only damage approximation. Original vehicle/vehicle
mass-point force/torque transfer was already present and remains regression
checked. Exit grace and bounded hull sweep substeps remain adapter choices.

Ground recovery follows the source's adjacent-surface search, half-radius
plane gate and 1.6-unit/sec outward-speed limit. It requires shared triangle
edges and valid clearance; it cannot snap an airborne jump or bridge a gap.
This remains the N64 capsule/substep adapter, not a claim that the entire original
swept-feature solver and its contact ordering have been ported unchanged.

## Frag, Needler and landing audit

The owned map defines 75 native body and 75 shield vitality. A centered frag
has a maximum of 120 damage; the extracted shield/body rules leave 40 normalized
health. A seven-needle supercombine applies the 60-damage EMP effect plus six
10-damage sibling detonations, leaving 20 normalized health in the isolated
fixture. Effect-graph traversal found no missing extra damage part or default
multiplayer multiplier. These unexpected retail breakpoints remain **uncertified**;
no compensating damage increase was invented. Extra attached needles now expire
immediately, while the six combined siblings multiply their remaining fuse by
the source random fraction instead of restarting a full fuse.

The frag showcase stages a firefight before its grenade finishes both opponents.
It now tracks the narrower animated body targets for 24 AR rounds, rather than
18, and still requires two deaths in the same tick from one live grenade.
All six showcases start at full vitality and use production input/damage.

The earlier “first-person landing camera effect” item was an audit question.
`biped_get_sight_position` uses standing/crouched camera height, without a landing
bob. `biped_update_landing` selects body poses and footstep events. The owned
`globals\\falling` damage tag has zero camera impulse and zero shake, and the
dirt/grass landing material entries have sound but no visual effect. No extra
camera bob was added. Existing landing poses, recovery, audio and falling damage
remain; exact retail presentation/controller acceptance is still outstanding.

## Performance and verification

The initial quiet four-player run regressed to 22.2 overall / 26.3 combat /
18.5 vehicle FPS. This is below the agreed development target. Profiling found
substantial repeated static-world searches in the original vehicle solver.
A bounded candidate-index cache preserves exact bounds filtering and original
BVH order, with uncached fallback on overflow. It caches neither contacts nor
forces. Native tests compare 48,000 ordered queries with the uncached tree.
The final quiet run measures **24.4 overall / 26.3 combat / 22.7 vehicle FPS**,
with 52 KiB live free heap, P95 66.8 ms and maximum 200.5 ms. This improves the
initial regression but does not meet the development target. Timing acceptance
uses the quiet ROM, not instrumented/native speed.

The expanded all-weapons lifecycle also exposed a first-person allocation
failure during the four-player AR-to-pistol transition. An Ares RDRAM export
showed the first resized mesh pointer was null at 3.1 seconds. The 24 KiB menu
glyph workspace now allocates with the front end and releases on match entry,
instead of occupying gameplay RAM. A second export identified heap fragmentation:
about 40 KiB remained free, but the last pistol allocation could not find an
11,648-byte block. First-person workspaces now lazily reserve the maximum authored
mesh size per visible player/slot and reuse that capacity until returning to the
menu. No glyph limit, weapon geometry or artwork was reduced.

Focused sanitizer checks cover mounted cadence, material/rider transfer,
standing/carrying/jumping on a tank, player separation, animated hit regions,
neighbor support recovery, articulated ray/capsule queries and all six gameplay
showcases. The full suite also covers existing combat, camo, pickups, terrain,
vehicles, audio and menu-independent match rules. Final Ares lifecycle, RDP and
performance evidence is recorded with exact ROM hashes in the release manifest
and `build/n64/fidelity-audit/`.

Release and diagnostic Ares lifecycles complete all 37 steps: all eight weapons,
a 15-kill match, results, menu return and control settings. The diagnostic run
reports zero RDP errors and warnings. It uses 8 KiB queues because the 16 KiB
validator configuration exhausts its 4 MiB budget; the playable release retains
32 KiB queues. The release staged match retained 34 KiB free and returned to
346 KiB at the main menu. Quiet replay memory and FPS are separate measurements.
