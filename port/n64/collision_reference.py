"""Extract the pre-optimization collision implementations as independent oracles."""
import re, subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE='f303c4c9ee0648522a6e8b65147d5ed88c06a301'
def generate(out):
    out=Path(out)
    def old(name):return subprocess.check_output(['git','show',BASE+':port/n64/'+name],cwd=ROOT,text=True)
    terrain=old('terrain.c')
    for name in ('bg_capsule_triangle','bg_terrain_reset','bg_terrain_clearance','bg_can_stand','bg_move_capsule'):
        terrain=re.sub(r'\b'+name+r'\b','reference_'+name,terrain)
    (out/'collision_reference_terrain.c').write_text(terrain)
    hits=old('pve_collision.inc').split('static bool pve_needle_impact')[0]
    # Feed new weapon poses into the old exhaustive triangle oracle. Keep its
    # interpolation, ray arithmetic, triangle order and material selection.
    # The wider identity only prevents alternate clips aliasing base clips.
    needle='const bg_pve_animation*c=&m->clips[a->clip];'
    assert needle in hits
    hits=hits.replace(needle,needle+'''\n#ifdef BG_PVE_ROSTER
    if(a->armament)c=&bg_pve_alt_hit_clips[a->kind][a->clip];
#endif
''')
    hits=hits.replace('(a->kind<<28)+(a->clip<<24)', '(a->kind<<29)+(bg_pve_render_clip(a)<<24)')
    for name in ('pve_hit_pose','pve_hit_normals','pve_hit_keys','pve_hit_generations','pve_clip_once','pve_clip_frame','pve_triangle_ray','bg_pve_hit_ray'):
        hits=re.sub(r'\b'+name+r'\b','reference_'+name,hits)
    (out/'collision_reference_hits.inc').write_text(hits)
