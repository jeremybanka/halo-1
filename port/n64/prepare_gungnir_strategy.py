"""Reuse the game's original Elite/Grunt selectors for movement assistance."""
import argparse,hashlib,json
from pathlib import Path
from test_render_matrix import function
ROOT=Path(__file__).resolve().parents[2]


def run(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);bodies=[];inputs={}
    for filename,name,signature in [
        ('actions.c','actor_action_handle_panic_transition','static boolean actor_action_handle_panic_transition(long actor_index,short minimum_panic_type,boolean communicate_failure,short force_panic_type)'),
        ('actor_type_elite.c','elite_decide_action','static void elite_decide_action(long actor_index)'),
        ('actor_type_grunt.c','grunt_decide_action','static void grunt_decide_action(long actor_index)')]:
        path=ROOT/'source/ai'/filename;inputs[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest();bodies.append(signature+'{'+function(path.read_text(),name)+'}\n')
    target=output/'gungnir_strategy_source.inc';target.write_text('/* Verbatim original action-selector bodies; movement-only platform boundary. */\n'+'\n'.join(bodies))
    (output/'strategy-provenance.json').write_text(json.dumps(dict(inputs=inputs,output_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),scope='Same original selectors used by the in-game Elite/Grunt adapter; weapon/grenade/campaign services intentionally disabled for movement-only human assistance'),indent=2)+'\n')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output');a=p.parse_args();run(a.output)
