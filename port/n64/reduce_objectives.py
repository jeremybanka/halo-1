"""Reduce objective viewmodels, preserving the flag's visible gripping hand.

Run in an independent Blender background process after extract_objectives.py.
The generic 200-triangle hand collapses finger/palm surfaces inside the flag
shaft. Preserve those source surfaces; reduce the forearms and the other hand.
"""
import argparse,json,sys,tempfile
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from reduce_firstperson import reduce_firstperson

FLAG_GRIP_PARTS=tuple('frame l '+part for part in
                      ('wriste','thumb','index','middle','ring','pinky'))

def reduce_objectives(source,output):
    import bpy
    raw=json.loads(Path(source).read_text());output=Path(output)
    results={};scenes=set()
    with tempfile.TemporaryDirectory(prefix='halo-objective-grip-') as directory:
        temp=Path(directory)
        for kind in ('ball','flag'):
            subset={**raw,'weapons':{kind:raw['weapons'][kind]}}
            src=temp/(kind+'-raw.json');dst=temp/(kind+'-reduced.json')
            src.write_text(json.dumps(subset));before=set(bpy.data.scenes)
            reduce_firstperson(src,dst,hand_budget=560 if kind=='flag' else 200,
                hand_topology='anatomy' if kind=='flag' else 'connected',
                gun_budgets={kind:240},
                preserve_hand_parts=FLAG_GRIP_PARTS if kind=='flag' else ())
            results[kind]=json.loads(dst.read_text())
            for scene in set(bpy.data.scenes)-before:
                scene.name='Objective - '+('flag grip' if kind=='flag' else 'skull')
                scenes.add(scene)
    result=results['ball']
    result['weapons']={kind:results[kind]['weapons'][kind] for kind in ('flag','ball')}
    result['hand_triangle_counts']={kind:w['hand_triangle_count'] for kind,w in result['weapons'].items()}
    result['reduction_report']['flag']=results['flag']['reduction_report']['flag']
    result['reduction_report']['flag_grip_hands']=results['flag']['reduction_report']['hands']
    result['flag_grip']={'preserved_source_parts':FLAG_GRIP_PARTS,'hand_budget':560,
        'reason':'Preserve the source closed grip and shaft occlusion in first person.'}
    output.write_text(json.dumps(result))
    bpy.data.libraries.write(str(output.with_suffix('.blend')),scenes)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('source');p.add_argument('output')
    a=p.parse_args(sys.argv[sys.argv.index('--')+1:])
    reduce_objectives(a.source,a.output)
