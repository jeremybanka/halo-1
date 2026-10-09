# Power-ups and vehicle edge cases

Active camouflage uses the requested demake presentation: fully hidden world
body and held weapon at rest, a one-second reveal after an actual shot, three
seconds without shooting before fading out over one second. Repeated shots
renew the quiet timer. Mounted primary/secondary fire and personal weapons in
passenger seats use the same rule. Empty triggers, reloading and switching do
not renew it. Receiving damage also reveals the player, following the original
damage depower behavior. Acquisition and the final second before expiry fade;
the original map's 45-second duration is retained. Refreshing an active pickup
does not erase a firing reveal. Death clears camo and shield charging state.

The fully hidden phase submits no body or held-weapon triangles. Partial
visibility uses RDP noise alpha rejection in the existing opaque/depth pass:
no duplicate shell, framebuffer refraction, transparency sorting or new mesh
bank. Shield hit color combines with the same opacity. The local first-person
weapon and HUD remain readable; opponents cannot see that viewmodel. Projectiles,
impacts and shield-break effects remain visible clues.

Source references and deliberate changes:

- `game_engine_weapon_fired` and `unit_update` use weapon-specific camouflage
  reduction/regrowth. The explicit one/three/one timing above replaces those
  constants at the user's request; this is not claimed to be the Xbox shader.
- `unit_cause_damage` reduces camouflage on damage. This adapter shares the
  shot reveal timer rather than reproducing every damage tag's reduction value.
- `find_aim_assist_targets_recursive` rejects fully cloaked units, not every
  active power-up. Assistance now follows visible state. A homing needle loses
  its target when that target becomes fully hidden; physical hits still work.
- `motion_sensor.c:should_draw_object` permits moving cloaked players in a
  multiplayer game. Camo does not suppress radar. Firing/throwing can show a
  crouched player, and seated players use hull velocity instead of stale foot
  velocity. Stationary occupied hulls no longer force a motion blip.

## Vehicle corrections

Boarding checks a nearby seat's approach against terrain and neighboring hulls.
Distance rejection happens before those queries. Voluntary exits prefer the
original exit marker, then try six nearby alternatives with terrain capsule,
vehicle hull and player clearance. The exit animation starts only when a clear
candidate exists and rechecks on completion. An obstruction that arrives during
the animation leaves the player in the seat; forced death/rollover ejection
still releases reservations even if no candidate is available.

Splatter contact now sweeps the original collision hull against the player's
capsule (up to eight substeps), replacing the 0.8-unit origin sphere. It uses
relative speed and all three velocity axes, including lateral/falling motion.
Existing low-speed threshold, approximate damage scale and 0.3-second grace
against one's own dismounted vehicle remain. This is not the complete Xbox
object/object impulse and collision-damage solver.

Attached plasma grenades now store a hull-local contact, transformed each tick,
so banking/rolling vehicles keep their grenades attached. Third-person camera
obstruction uses a center ray and four near-plane shoulder rays, includes
neighboring hulls, and can retract closer than the old minimum distance. The five
terrain probes share one conservative BVH candidate query and retain the original
polygon tests; 1,200 packet rays agree with independent queries.

Existing original hull rays govern exposed seats and cover. Destructible hulls
and burned wrecks remain the requested demake extension; several Xbox multiplayer
hulls are invulnerable. Biped hit regions still use approximate pills, and the
collision hull is in bind pose rather than following moving hatches/turrets.
Mounted weapon damage/material profiles and full contact impulses remain open.

## Verification

`test_powerups.c` exercises real pickups and weapon input, shot/quiet/fade timing,
dry triggers, expiry, damage/death/respawn, radar, aim assistance, Needler target
loss and mounted firing. Existing shield tests cover non-stacking overshields,
charge protection, EMP, decay and recharge interruption.

`test_vehicle_edges.c` checks all ten seats from four directions: 34 exposed
rays and six hull-blocked rays, terrain-blocked probes excluded. It also checks
blast cover, blocked/interrupted exits, neighboring-hull camera obstruction,
capsule contacts outside the old kill sphere, an actual fast-hull damage event,
and rotating plasma attachment. Existing interaction tests retain every seat,
contention, entry destruction, all flips and sustained rollover release.

Ares evidence and current build identities are saved under
`build/n64/powerup-vehicle-audit/`. The camo recording stages infantry and a
Warthog gunner, collects actual world power-ups, then fires through production
input. It is N64 test-fixture footage, not retail Xbox footage or a timing run.

The four-player release lifecycle uses three display buffers and 32 KiB queue
buffers. It exercises all eight weapons before completing a 15-kill match and
returning through the menus. RDP validation is a separate 16 KiB-queue build:
the validator plus 32 KiB queues exhausts 4 MiB during the all-player pistol
transition. Its captured assertion identifies `firstperson_buffer_resize`;
the subsequent black display is the assertion inspector failing to allocate
its own framebuffer. The diagnostic queue reduction changes queue capacity,
not the rendering commands. Do not use validation builds for timing acceptance.

## Performance acceptance

The new camera probes share their terrain BVH search and polygon projections;
source-hull capsule contacts traverse the existing hull BVHs. Seat spheres
reject unreachable vehicles before marker transforms. The comparison tests
retain exhaustive reference paths. No mesh/detail reduction or extra rendering
pass is introduced by this work.

The final quiet Ares replay measures **25.7 FPS overall / 27.6 combat / 23.9
vehicles**, with 125 KiB live free heap (4 MiB, three display buffers, 32 KiB
queues). It displays 1,932 distinct poses over 75.050 seconds after warmup.
P95 is 66.8 ms; the maximum is 267.4 ms overall and 100.2 ms in vehicles.
The release lifecycle and 16 KiB-queue diagnostic lifecycle both pass 37/37;
the latter reports zero RDP errors and warnings. Final camo footage also reports
zero RDP errors and warnings.

The vehicle-heavy replay remains below the development target. Keep the
vehicle performance acceptance item open; the final evidence records both the
overall and vehicle-section figures rather than treating the overall average
as a passing vehicle result. Full retail/controller parity and the final 30 FPS
pass are also still open.

## October 9 source-audit follow-up

[FIDELITY_EDGES.md](FIDELITY_EDGES.md) supersedes the earlier open items about
animated hit regions, moving supports, mounted damage/materials, contact impulses
and the landing-camera audit. Retail comparison remains deferred. Consult the
current release manifest for performance; earlier numbers describe older ROMs.
