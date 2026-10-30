# Firefight fight selection

See [the rules and validation report](../../FIREFIGHT_FIGHTS.md).

- `test.py`: host sanitizer checks and logs, with original Onslaught schedule oracle.
- `host.json`: exact host input hashes and compiler flags.
- `refresh_maps.py`: independently reproduce unchanged Blood Gulch before recertifying the restart-only `game.c` edit.
- `run.py`: native menu QA and paced release builds; only terminates its owned emulator process.
- `test_firefight_fights.log`: exact party-size species/variant counts and finite-set results.

The previous vehicle-simulation/LOD evidence is preserved in its original
benchmark directories. These are new encounter rules, not a matched performance
optimization; the existing FPS numbers do not measure Gauntlet.
