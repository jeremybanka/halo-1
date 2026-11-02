"""Review the four painted helmets and independently check color-only changes."""
import argparse,hashlib,json
from collections import Counter
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw
from gungnir_faces import render,textures_from_pngs,sha
from gungnir_assets import texture_path
from pack_gungnir import prepare_broad_colors,corner_colors


def topology(data):
    tracks=[hashlib.sha256(b''.join(data[f'frames_{i}'][:,v].tobytes() for i in range(39))).digest() for v in range(len(data['positions']))]
    triangles=[]
    for tri in data['triangles']:
        keys=tuple(tracks[i] for i in tri)
        triangles.append(min(keys,keys[1:]+keys[:1],keys[2:]+keys[:2]))
    return Counter(triangles)


def run(candidate,parent,parent_colors,bank,faces,output):
    output.mkdir(parents=True,exist_ok=True);source=json.loads(candidate.read_text());metadata=json.loads((faces/'faces.json').read_text());report=json.loads((bank/'gungnir-report.json').read_text());textures=textures_from_pngs(faces);prior_colors=json.loads(parent_colors.read_text())
    prepared=json.loads(candidate.read_text());diffuse={i:Image.open(texture_path(p,candidate)).convert('RGB') for i,p in enumerate(source['textures']) if p};prepare_broad_colors(prepared,diffuse);rows=[]
    for lod in range(2):
        old=np.load(parent/f'gungnir-{lod}-preview.npz');new=np.load(bank/f'gungnir-{lod}-preview.npz')
        assert topology(old)==topology(new),'Packed topology or animation changed'
        for i in range(39):assert np.array_equal(old[f'grips_{i}'],new[f'grips_{i}']),'Weapon socket changed'
        helmet=lambda i:source['lods'][lod]['triangles'][int(i)//3]['component']=='helmet-shell'
        for i,tri in enumerate(prepared['lods'][lod]['triangles']):
            if tri['component']!='helmet-shell':assert corner_colors(tri,source['materials'],diffuse)==tuple(prior_colors[lod][i]),'Authored colors outside the helmet changed'
        panels=Counter();front=0
        for tri in prepared['lods'][lod]['triangles']:
            if tri['component']!='helmet-shell':continue
            panels[tri['helmet_panel']]+=1;p=np.array(tri['p']);n=np.cross(p[1]-p[0],p[2]-p[0]);n/=np.linalg.norm(n)
            if n[0]>.7:assert tri['helmet_panel']=='faceplate';front+=1
        assert all(panels[p]>0 for p in ('faceplate','crown','cheek','jaw'))
        ids=np.array(metadata['lods'][lod]['vertices']);basis=np.c_[new['positions'][ids],np.ones(len(ids))];matrix=np.linalg.lstsq(basis,new['frames_0'][0,ids]/512,rcond=None)[0]
        forward=matrix[0]/np.linalg.norm(matrix[0]);right=matrix[2]/np.linalg.norm(matrix[2]);up=matrix[1]/np.linalg.norm(matrix[1]);angle=forward*.90+right*.55+up*.20;angle/=np.linalg.norm(angle)
        sheet=Image.new('RGB',(1200,704),'#202428');draw=ImageDraw.Draw(sheet)
        for row,(label,direction) in enumerate((('Front',forward),('Three-quarter',angle))):
            top=row*352
            for profile,name in enumerate(('Red / Artboard 1','Blue / Artboard 2','Gold / Artboard 3','Green / Artboard 4')):
                draw.text((profile*300+10,top+10),name+' / '+label,fill='white');image=render(bank,metadata,textures,lod,profile,direction,output,True,size=(300,320));sheet.paste(image,(profile*300,top+32))
        sheet.save(output/f'helmet-variants-lod-{lod}.png')
        rows.append(dict(lod=lod,panels=dict(panels),protected_front_triangles=front,packed_vertices=report['lods'][lod]['vertices'],triangles=report['lods'][lod]['triangles'],all_39_clip_packed_topology_and_motion_unchanged=True,all_weapon_sockets_unchanged=True,nonhelmet_authored_colors_unchanged=True))
    result=dict(schema=1,passed=True,candidate_sha256=sha(candidate),parent_bank_sha256=sha(parent/'gungnir.bin'),bank_sha256=sha(bank/'gungnir.bin'),source_recipe_sha256=sha(Path(__file__).with_name('pack_gungnir.py')),lods=rows,scope='Color-only crown, cheek and underside jaw blocking on retained source surfaces. Exact oriented packed triangle trajectories across all 39 sparse clips, sockets compare to the accepted parent. Nonhelmet authored colors remain exact; packed color welding retains its existing 24-level channel bound. Frontal faces remain silver; original art alpha/UV and native appearance are separate checks.')
    (output/'helmet-validation.json').write_text(json.dumps(result,indent=2)+'\n');print('HELMET',rows,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('candidate','parent','parent_colors','bank','faces','output'):p.add_argument(name,type=Path)
    a=p.parse_args();run(a.candidate,a.parent,a.parent_colors,a.bank,a.faces,a.output)
