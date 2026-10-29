"""Restore the intact CE shield as one rigid, animated forearm attachment.

Run prepare/pack on the host; bake() runs in Blender's mathutils environment.
All extracted geometry, textures and generated banks remain private.
"""
import argparse,copy,gzip,hashlib,json,shutil,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'build/jackal-shields'
BASE=ROOT/'halo64-assets/assets/firefight-roster'

def prepare():
    source=OUT/'source';source.mkdir(parents=True,exist_ok=True)
    raw=json.loads((BASE/'source/squad-source.json').read_text());m=raw['models']['jackal']
    high=m['source_geometry_lods']['base00 superhigh'];material=next(i for i,v in enumerate(m['material_metadata']) if v['path'].endswith('jackal shield'))
    faces=[f for f,mat in zip(high['faces'],high['materials']) if mat==material]
    assert len(faces)==76
    used=sorted({v for f in faces for v in f});assert {tuple(high['weights'][v]) for v in used}=={(26,-1,0)}
    geom={**high,'faces':faces,'materials':[material]*len(faces)}
    m['source_geometry_lods']={'source shield':geom};m['n64_lods']=['source shield']
    m['markers']={'right hand shield': [{'node':26,'p':[0,0,0],'q':[0,0,0,1]}]}
    raw['models']={'jackal':m}
    (source/'shield-source.json').write_text(json.dumps(raw,separators=(',',':')))
    # The existing shader's first bitmap is its source noise texture. Preserve
    # it for a bounded one-pass approximation, alongside the complete shader.
    shutil.copyfile(m['textures'][material],source/'noise.png')
    colors=[]
    for actor in (raw['actors']['jackal'],raw['roster']['variants']['jackal_major']):
        c=actor['biped']['obje_attrs']['change_colors'][2]['permutations'][0]
        colors.append([(lo+hi)*.5 for lo,hi in zip(c['color_lower_bound'].values(),c['color_upper_bound'].values())])
    report={'source_mesh':m['path'],'source_lod':'base00 superhigh','triangles':76,'bone':26,'bone_name':m['nodes'][26]['name'],
            'shield_colors':colors,'shader':m['material_metadata'][material]['shader'],
            'collision_shield':raw['actors']['jackal']['collision']['shield'],
            'baseline_source_sha256':hashlib.sha256((BASE/'source/squad-source.json').read_bytes()).hexdigest()}
    (source/'source-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print({k:report[k] for k in ('triangles','bone_name','shield_colors','collision_shield')})

def bake():
    from mathutils import Matrix,Quaternion,Vector
    from bake_pve_blender import bake as skin
    source=OUT/'source';skin(source/'shield-source.json',source/'shield-baked.json.gz',model_names=['jackal'])
    raw=json.loads((source/'shield-source.json').read_text());m=raw['models']['jackal'];g=m['source_geometry_lods']['source shield']
    matrices=[]
    for n in m['nodes']:
        x,y,z,w=n['q'];t=Quaternion((w,-x,-y,-z)).to_matrix().to_4x4();t.translation=Vector(n['p'])
        matrices.append(matrices[n['parent']]@t if n['parent']>=0 else t)
    inv=matrices[26].inverted();verts=[list(inv@Vector(v)) for v in g['vertices']]
    (source/'shield-local.json').write_text(json.dumps({'vertices':verts,'faces':g['faces'],'uv':g['uv']},separators=(',',':')))
    print('Rigid shield local mesh and 24 source attachment clips baked; active scene unchanged')

def pack():
    from PIL import Image
    from pack_mesh import indexed_mesh,emit_batches
    from pack_assets import position
    from pack_pve import braces as B,f as F
    source=OUT/'source';bank=OUT/'bank';shutil.copytree(BASE/'bank',bank,dirs_exist_ok=True)
    g=json.loads((source/'shield-local.json').read_text());baked=json.loads(gzip.decompress((source/'shield-baked.json.gz').read_bytes()))['jackal'][0]
    points=[];uv=[]
    for face in g['faces']:
        for v in face:points.append([round(c*1024) for c in position(g['vertices'][v],(0,0,0))]);uv.append(g['uv'][v])
    # UV identity participates in welding. Static geometry is shared by every
    # actor/LOD; only its forearm matrix and per-draw color vary.
    mesh=indexed_mesh(points,[[255]*3]*len(points),[0]*len(points),material_keys=[tuple(round(c*2048) for c in p) for p in uv])
    lines=['#include "jackal_shield.h"','static T3DVertPacked shield_vertices[] __attribute__((aligned(16)))={']
    for i in range(0,len(mesh['vertices']),2):
        a,b=mesh['vertices'][i:i+2];st=lambda j:B(round(c*32*32) for c in uv[mesh['sources'][j]])
        lines.append('{'+B(a[0])+',0,'+B(b[0])+',0,0xffffffff,0xffffffff,'+st(i)+','+st(i+1)+'},')
    lines.append('};');emit_batches(lines,'shield',mesh)
    lines.append('const bg_model_asset bg_jackal_shield_model='+B(['shield_vertices',len(mesh['vertices']),'2.f','shield_batches','shield_indices',len(mesh['batches']),76])+';')
    rows=[]
    for i,(key,hand) in enumerate(baked['grips'].items()):
        symbol='shield_hand_'+str(i)
        lines.append('static const bg_attachment_pose '+symbol+'[]='+B(B([B(map(F,p['pos'])),B(map(F,p['quat']))]) for p in hand['poses'])+';')
        rows.append(B([symbol,len(hand['poses']),F(hand['duration'])]))
    assert len(rows)==24
    lines.append('const bg_attachment_clip bg_jackal_shield_grips[PVE_CLIPS]='+B(rows)+';')
    report=json.loads((source/'source-report.json').read_text())
    lines.append('const float bg_jackal_shield_colors[2][3]='+B(B(map(F,c)) for c in report['shield_colors'])+';')
    noise=Image.open(source/'noise.png').convert('RGBA').resize((32,32),Image.Resampling.BOX)
    # Preserve the source noise as a dim/moderate energy pattern. Do not turn
    # dark noise into collision holes: physical gaps come from source triangles.
    pixels=[]
    for r,g,b,a in noise.getdata():
        value=round(160+95*max(r,g,b)/255);alpha=128
        pixels.append((value<<24)|(value<<16)|(value<<8)|alpha)
    lines.append('const uint32_t bg_jackal_shield_texture[1024] __attribute__((aligned(8)))='+B(hex(p) for p in pixels)+';')
    (bank/'pve_jackal_shield.c').write_text('\n'.join(lines)+'\n')
    report.update(vertices=len(mesh['vertices']),batches=len(mesh['batches']),loads=sum((b[1]+1)&~1 for b in mesh['batches']),
                  texture='32x32 RGBA32 source noise; one-pass color/alpha approximation; no animated seven-stage CE combiner',
                  geometry_shared_by_all_lods=True)
    (bank/'jackal-shield-report.json').write_text(json.dumps(report,indent=2)+'\n')
    print({k:report[k] for k in ('vertices','batches','loads')})

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['prepare','pack']);a=p.parse_args();globals()[a.action]()
