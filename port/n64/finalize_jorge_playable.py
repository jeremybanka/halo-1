"""Validate, bake and export one accepted playable checkpoint in Blender."""
import validate_jorge_playable as validation
import bake_jorge_playable as bake
import jorge_playable_reduce as task
import sys
if '--rebuild' in sys.argv:
    import seal_jorge_playable as seal
    import fit_jorge_coverage as fit
    import patch_jorge_seams as patch
    task.build();seal.run();fit.run();patch.run()
validation.run()
import json
assert json.loads((task.OUT/"coverage-validation.json").read_text())["game_scale_max_new_holes"] == 0
bake.run()
task.export()
task.ce.OUT=task.OUT;task.ce.proof_scene=task.proof_scene;task.ce.render()
