"""Equal-cost shoulder pilot: semantic cuts, constrained collapse and direct collapse."""
import sys,argparse,json,hashlib
from pathlib import Path
import bpy
sys.path.insert(0,str(Path(__file__).resolve().parent))
from demake_odst import components,source_part,reduce_part


def run(source,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);model=json.loads(Path(source).read_text());model['skin_weights']=model['weights'];parts=[p for p in components(model) if p['region']=='flair_left_shoulder']
    plate=next(p for p in parts if p['id']=='flair_left_shoulder-96:000');fasteners=[p for p in parts if p!=plate]
    clean,report=reduce_part(bpy.context.scene,model,plate,24)
    whole=dict(id='shoulder-direct',region='flair_left_shoulder',material=96,faces=[f for p in parts for f in p['faces']]);points,faces,_=source_part(model,whole)
    me=bpy.data.meshes.new('Direct collapse');me.from_pydata(points,[],faces);ob=bpy.data.objects.new('Direct collapse',me);bpy.context.scene.collection.objects.link(ob);mod=ob.modifiers.new('Equal-count direct collapse','DECIMATE');mod.ratio=len(clean)/len(faces);mod.use_collapse_triangulate=True;ev=ob.evaluated_get(bpy.context.evaluated_depsgraph_get());mesh=ev.to_mesh();mesh.calc_loop_triangles();direct=[[list(mesh.vertices[i].co) for i in t.vertices] for t in mesh.loop_triangles];ev.to_mesh_clear()
    result=dict(source_sha256=hashlib.sha256(Path(source).read_bytes()).hexdigest(),source_components=parts,omitted_components=[p['id'] for p in fasteners],decision='Remove the two inspected small shoulder fasteners; retain the broad original shoulder shell and its authored mount contour',source=[dict(p=[model['vertices'][i] for i in model['faces'][fi]],material=model['materials'][fi]) for p in parts for fi in p['faces']],cleaned=[dict(p=[model['vertices'][i] for i in model['faces'][fi]],material=model['materials'][fi]) for fi in plate['faces']],constrained=clean,direct=[dict(p=p,material=96) for p in direct],reduction=report)
    (output/'shoulder-pilot.json').write_text(json.dumps(result,indent=2)+'\n');print('PILOT',len(result['source']),len(result['cleaned']),len(clean),len(direct),report,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('source');p.add_argument('output');a=p.parse_args(sys.argv[sys.argv.index('--')+1:]);run(a.source,a.output)
