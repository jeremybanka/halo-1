# Reach Firefight design for the CE N64 port

Research date: 28 October 2026. Scope: one to four human players, including
Reach's solo and cooperative matchmaking variants. This records the pre-implementation design proposal. The completed first
implementation and its measured boundaries are in [FIREFIGHT_LIMITED.md](FIREFIGHT_LIMITED.md).

The best starting point is a finite cooperative survival match, drawing on
Reach's Firefight Limited. Its important ingredients are distinct encounters,
shared stakes, recovery opportunities and rewarding combat. Enemy population
is a tuning parameter, and must fit the N64's measured rendering budget.
Score Attack supplies a useful second model for repeatable solo challenges and
regression fixtures. Arcade presets can follow once the same underlying
director works well.

## Which Reach experience

Reach's variants changed during its lifetime. A launch custom game, an October
2010 matchmaking game and a June 2011 playlist need not have identical settings.
The following are dated reference points, not a claim that one preset covers all
Reach Firefight.

| Reference | Players relevant here | Structure and purpose |
| --- | --- | --- |
| Custom Firefight | 1–4 | The manual describes a default one-set match; customizable survival. |
| Classic | 1–4 | Endless survival, with Black Eye replacing Cloud in round three. |
| Standard matchmaking, October 2010 update | Cooperative, up to 4 | Expanded to one set or 30 minutes; friendly fire disabled. |
| Firefight Limited, early 2011 | Cooperative, up to 4 | Finite survival; 10 shared reserve lives; defeat when no one can return. |
| Firefight Arcade, February/June 2011 | Cooperative, up to 4 | Weapon-focused power fantasies with boosted traits and fast respawns; June specified a 20-minute limit. |
| Score Attack matchmaking | 1 | Repeatable score competition; one round, with the time limit raised to 15 minutes in October 2010. |
| Firefight Doubles, June 2011 | 2 | Offered 2X Score Attack, Arcadefight and FF Limited. |

Sources: [Reach manual, printed pages 16–19](https://www.videogamemanual.com/xbox360/Halo-%20Reach.pdf),
[October update](https://halo.bungie.org/bwu/index.html?item=299),
[January Limited announcement](https://halo.bungie.org/bwu/?item=309),
[February playlist split](https://halo.bungie.org/bwu/index.html?item=312),
and [June update](https://nikon.bungie.org/bwu/index.html?item=327).
The manual describes Score Attack for one or two players, whereas the dedicated
[matchmaking playlist was solo](https://www.halopedia.org/Firefight_%28Halo%3A_Reach%29#Score_Attack).
Use the dated playlist records for matchmaking limits; the manual alone does not
resolve that discrepancy. For our port, three players must receive explicit
balancing and testing alongside one, two and four.

## Encounter structure and pacing

The overall structure is five waves per round, three rounds per set, then an
optional timed bonus. Round completion offers recovery; set completion offers
a longer break. The manual describes the bonus as a score opportunity with
respawning disabled and possible extra-life rewards. See the
[manual](https://www.videogamemanual.com/xbox360/Halo-%20Reach.pdf).

```text
Initial → Main → Main → Main → Boss → Recover / resupply
                    repeat for three rounds
                    → Timed bonus → Result or next set
```

David Cobb's reverse-engineering documentation gives the finer mechanics:
normal waves contain six internal squads. Ordinary waves can advance with
three enemies remaining; a boss wave requires a full clear, and its final five
enemies receive markers. Dropship departure also gates progression. Boss-wave
completion restores living players' shields, revives dead players and adds one
reserve life per Spartan. Bonus waves replenish enemies until their timer or
team elimination ends them.
[ReachVariantTool encounter flow](https://davidjcobb.github.io/ReachVariantEditor/concepts/firefight.html).

This creates several useful pacing effects, in our interpretation:

- A wave is a recognizable encounter, not necessarily a perfectly isolated
  batch. Small overlaps sustain momentum.
- Boss completion creates closure. Markers prevent the climax becoming a long
  search for a hidden survivor.
- Recovery lets the team regroup, redistribute equipment and prepare for a new
  threat. Continuous spawning would remove this contrast.
- The bonus changes the objective from cautious survival to taking scoring
  opportunities under time pressure.

There is no universal fixed duration for every wave: player effectiveness,
enemy roles, travel and arrival conditions influence it. Exact intermission and
bonus timer defaults should be read from the selected variant before copying
them. In June 2011 Bungie specified dropships for Arcade's first and boss waves;
this is a useful precedent for reserving elaborate arrivals for important
boundaries. [June update](https://nikon.bungie.org/bwu/index.html?item=327).

## How encounters vary

Reach separates initial, main and boss template lists, with ordered or randomized
selection. Its editor's squad-count field describes template entries, not the
number of living actors. Round settings also control skulls and allow mixed
enemy formations.
[ReachVariantTool round settings](https://davidjcobb.github.io/ReachVariantEditor/editor/main_window_ff/round.html).

A community experiment on **Heroic Courtyard** found these examples:

| Template | Observed composition | Total |
| --- | --- | --- |
| Elite Patrol | Six teams, each with one Elite and three Grunts | 24 |
| Hunters | Six individual Hunters | 6 |
| Elite Strike Team | Four Generals, one Ranger team and one Grunt team | 12 |
| Hunter Kill Team | Two Hunters and four Elite Patrol teams | 18 |

These are observations for that test context, not universal counts for every
map, difficulty and playlist.
[TestTube's wave and squad experiment](https://steamcommunity.com/sharedfiles/filedetails/?id=1967747082).

The design implication is substantial: escalation can mean fewer enemies with
a different tactical demand. It need not mean steadily increasing actor counts.
For CE, the useful roles are:

| Role | Combat decision to create | Port implication |
| --- | --- | --- |
| Grunts with an Elite leader | Break leadership, exploit panic, manage surrounding fire | Already partly represented; preserve the source behavior. |
| Shielded Elites | Strip shields, capitalize before recovery, respond to melee pressure | More ranks alone do not create enough variety; positioning and weapon use matter. |
| Shield-bearing Jackals | Change angle, expose a weak point, or spend a grenade | A valuable next enemy because it changes the player's action. |
| Hunters | Coordinate distraction and flanking; punish careless positioning | A later boss candidate once movement, melee and damage regions are reliable. |

The last table is adaptation analysis, not a claim of documented Bungie intent.
Reach-specific Brutes, Skirmishers, jetpacks and Target Locators are not required
to establish this CE combat loop.

## Lives, equipment and difficulty

Bungie explicitly separated Limited's survival experience from Arcade's more
permissive play. Limited used 10 shared lives. February's Rocketfight and
Sniperfight included 150% damage/melee, doubled overshields and five-second
respawns; Fistfight instead used 200% damage/melee and 120% movement. Those
changes alter encounter tempo as much as enemy settings do.
[February update](https://halo.bungie.org/bwu/index.html?item=312).

Reach's scenario settings distinguish ammunition crates for ordinary UNSC
weapons, round-start power-weapon deliveries, dropships and map-specific hazards
such as vehicles. These are separate controls, not one generic resupply switch.
[ReachVariantTool scenario settings](https://davidjcobb.github.io/ReachVariantEditor/editor/main_window_ff/scenario.html).
The manual also describes replenished health packs and UNSC weapons after
rounds. [Manual](https://www.videogamemanual.com/xbox360/Halo-%20Reach.pdf).

For the October matchmaking baseline, the round progression was Tough Luck;
then Tough Luck plus Catch; then those two plus Cloud.
[Bungie's October update](https://halo.bungie.org/bwu/index.html?item=299).
The associated changes are increased evasion, more grenade use and loss of
motion-tracker information. Other configurable skulls constrain ammunition,
raise ranks, alter resistances or increase health. Round skull masks are
configurable; an ODST-style permanent skull ladder across successive sets
should not be assumed for Reach.
[Round and skull settings](https://davidjcobb.github.io/ReachVariantEditor/editor/main_window_ff/round.html).

Our interpretation: resource access and information determine whether players
hold cover, scavenge, push or retreat. Repeatedly increasing enemy health would
preserve much less of this design than improving real enemy behavior and varying
the available equipment.

## Scoring and replay value

Reach rewards kills and techniques such as headshots and grenade sticks, shows
the current score and multiplier, and supports comparison with other players.
[Manual](https://www.videogamemanual.com/xbox360/Halo-%20Reach.pdf).
Player accounts also describe the importance of sustained killing/weapon
sprees and multi-kills for high scores.
[Contemporary Firefight scoring discussion](https://gamefaqs.gamespot.com/xbox360/960512-halo-reach/answers/226859-can-some-one-tell-me-some-efficient-firefight-tactics).
That supports rewarding efficient, skilled survival, but does not establish
every multiplier or timing constant.

Community-documented Reach base values give the approximate scale:

| Enemy | Base value before modifiers |
| --- | ---: |
| Grunt Minor / Major / Ultra | 10 / 15 / 25 |
| Jackal Minor / Major / Sniper | 20 / 30 / 45 |
| Elite Minor / Major / Ultra / General | 50 / 100 / 125 / 150 |
| Hunter | 150 |

Source: [Reach enemy statistics](https://steamcommunity.com/sharedfiles/filedetails/?id=3571809884).
These are useful reference values, not yet a verified scoring table extracted
from a pinned Reach Firefight build, and CE ranks do not all map one-to-one.

The general structure to reproduce is:

```text
enemy value + kill attribution
    → technique / multi-kill / survival-spree scoring
    → difficulty and active-rule adjustments
    → individual score and team total
```

This is a conceptual pipeline, not an asserted arithmetic formula. Exact
stacking, rounding, multi-kill timing, spree thresholds, assist treatment and
death/betrayal deductions need a small controlled Reach scoring fixture.
In particular, the documented original Reach campaign values (difficulty
0.75/1/1.25/1.5 and additive skull contributions) are leads to verify, not
permission to import campaign completion-time bonuses. MCC campaign scoring
also explicitly differs from Reach Firefight.
[Scoring systems and version distinctions](https://www.halopedia.org/Campaign_scoring).

Keep in-match points separate from Reach's career credits and commendations.
Our first useful persistence feature would be local best scores keyed by mode,
difficulty, player count, encounter seed and rules version. A deterministic
Score Attack preset makes comparisons meaningful. Bungie reset Score Attack
leaderboards when changing its settings, a useful precedent for invalidating
incomparable records. [October update](https://halo.bungie.org/bwu/index.html?item=299).

## What the current N64 prototype can support

The [existing squad appraisal](PVE_SQUAD.md) documents one Elite and four Grunts,
source-derived action selectors, 5 Hz decisions, 30 Hz movement/combat and a
25-by-25 local navigation grid. Grenade throwing and several evasion handlers
are disabled; friendly-line avoidance is incomplete. Dead actors remain in the
bounded actor pool. There is no wave director, shared-life economy or PvE score
ledger yet. The eight-slot capacity in `pve.h` is not a proven performance target.

Existing native Ares diagnostic measurements, with corrected ground:

| Fixture | Mean FPS |
| --- | ---: |
| One player, five enemies | 50.8 |
| Two players, five enemies | 28.0 |
| Four players, five enemies | 17.0 |
| Four players, empty arena | 35.2 |

These are earlier uncapped emulator measurements, not new measurements or
hardware results. Four-player CPU phases averaged 30.44 ms drawing/submission,
7.33 ms preparation and 9.12 ms simulation. AI decision/perception/path work was
1.26 ms within simulation; NPC animation/attachments/visibility was 4.43 ms
within preparation. The full four-camera frame averaged roughly 29,470 vertex
loads. These counters do not separately measure RSP/RDP utilization.

The immediate design constraint is therefore enemy presentation as well as AI.
Streaming a large wave through five actor slots can bound memory and population;
it does not make those five actors render faster. Performance work and encounter
design must proceed together before claiming a four-player 30 FPS experience.

## Proposed adaptation

### First playable round

Build one complete five-wave round on a deliberately bounded Blood Gulch combat
area. Use familiar cover, safe return routes and several authored enemy entry
lanes. The current local navigation grid must cover every allowed spawn and
pursuit route; the entire canyon should not become an accidental search area.

The following is a proposed encounter script, not an original Reach preset:

| Wave | Encounter | Purpose |
| --- | --- | --- |
| 1 | One Elite-led Grunt patrol | Establish target priority and leader-loss panic. |
| 2 | Grunt-heavy reinforcement packets | Practice quick kills, scavenging and lane awareness. |
| 3 | Mixed patrol entering from an alternate lane | Require repositioning without surrounding every safe retreat. |
| 4 | Overlapping mixed packets, within the same active cap | Sustain pressure and make shared supplies matter. |
| 5 | A deliberate Elite-led confrontation, then full clear | Establish a climax and a clear recovery boundary. |

Initially these use existing supported enemy types. A properly implemented
Jackal encounter should replace a repeated patrol before expanding to fifteen
waves. Hunters can later supply a distinct boss; a stronger Elite placeholder
should not become a permanently inflated-health substitute.

### Director and player scaling

Keep total wave strength separate from the simultaneous actor cap. Each wave
owns a finite queue of squads, costs, entry lanes and release conditions. Issue
reinforcements only when there is capacity and a valid arrival route. Use enemy
roles and weapons to define pressure, not just a raw head count.

Tune independent one-, two-, three- and four-player encounter budgets. Additional
players can justify more total opposition, additional lanes and shorter gaps;
they do not automatically justify four times as many active actors. Preserve CE
weapon effectiveness rather than compensating only through health multipliers.
Keep the renderer's safe cap deterministic for each tested configuration; do
not silently vary a scored encounter according to transient frame rate.

For ordinary wave progression, wait until all scheduled packets are issued and
the remaining resistance is small. Reach's three-survivor threshold would leave
60% of a five-enemy encounter alive, so it needs scaling. Start by testing a
single surviving enemy, still counted against the active cap; bosses require
zero. Mark the final survivors and provide a logged recovery path for enemies
that become unreachable. Do not grant points for deleting a stuck actor.

Recycle actors only after safely detaching corpses, weapons, projectiles and
render references. Bound all of those pools independently. Late waves must not
grow memory use or make scoring/death events fire twice.

### Survival and equipment

Use shared reserve lives and last-player-standing recovery as the central stakes.
Ten starting reserves is a reasonable first Limited-style test value, not an
already balanced choice for every party size. Test round-completion rewards of
one reserve per active human. Prevent near-simultaneous deaths from consuming
the same reserve twice; if a surviving player clears the round, restore the team
before assessing defeat.

Use CE health, shields, weapons and movement. Start with a deliberately modest
AR/pistol kit, finite grenades and authored health/ammunition access. The current
fixture's 120 spare pistol rounds and four of each grenade are test supplies,
not a settled economy. Make power-weapon availability a round event and track
whether scavenging actually changes player behavior. Safe respawns should not
be a cheap way to generate unlimited high-value ammunition.

Friendly fire off is a defensible default for local cooperative play. Offer a
harder ruleset later if desired. Reserve lives, weapon supply and difficulty
must be explicit menu/HUD information, with a short results screen and an
immediate replay route.

### Progression and scoring

After the five-wave loop feels good, extend to three distinct rounds and a
timed bonus. A finite set is the initial full-match target; endless survival is
a later preset using the same director. Begin with a test target of roughly
8–12 minutes per round and tune from actual completion distributions, not a
fixed delay after every kill. This duration is a proposal, not a Reach rule.

Implement grenade use/evasion before claiming Catch or Tough Luck fidelity.
Cloud is mechanically simpler, but meaningful lost information still depends
on readable combat. Until these behaviors exist, escalate through tested squad
composition and positioning. Do not label generic damage/health boosts as the
missing skull behavior.

Use a single authoritative kill-event ledger for scores and medals. Start with
enemy values, headshots, sticks, multi-kills and sustained survival rewards;
calibrate the exact arithmetic before advertising Reach-equivalent scoring.
Show a team total prominently while preserving individual contributions.
Decide assist credit explicitly so cooperative shield stripping is not made
invisible. Score Attack then becomes a fixed sequence and seed; Gruntpocalypse
or a CE Rocketfight can be small configuration changes after ordinary combat
and projectile budgets hold up.

## Acceptance and remaining reference checks

The next implementation appraisal should include:

- Every human count, 1–4: completion time, deaths, reserves used, damage taken,
  ammunition pressure, kills by type and time spent without a reachable target.
- A complete round including leader deaths, simultaneous player deaths, zero
  reserves, a last-survivor clear, delayed reinforcements and a blocked spawn.
- Fixed-seed score-event traces proving exactly-once attribution and reproducible
  totals; restarts, quit/re-entry and long-run actor recycling.
- Matched native photos and perf fixtures during the busiest combat, including
  split views, corpses, pickups and grenades. Measure phase costs and peak memory;
  preserve the corrected ground and existing movement paths.
- A four-player frame-time budget assessment against 33.3 ms, not a claim based
  on the menu, an empty arena or actor capacity alone.

Before claiming exact Reach rules, pin a specific retail/custom or matchmaking
variant and verify its bonus duration, bonus-score-to-life conversion, respawn
penalties, life cap and scoring arithmetic. ReachVariantTool documents an unused
bonus-target field, so that field alone cannot establish the actual reward.
[Scenario settings](https://davidjcobb.github.io/ReachVariantEditor/editor/main_window_ff/scenario.html).
Bonus duration is configurable, including disabling the bonus entirely.
[Bonus settings](https://davidjcobb.github.io/ReachVariantEditor/editor/main_window_ff/bonus-wave.html).

The concrete next step is a complete, repeatable five-wave survival round with
bounded reinforcement scheduling, resource recovery and trustworthy scores,
developed alongside the rendering improvements needed for four players.
