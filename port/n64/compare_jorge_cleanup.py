"""Validate the full surgical baseline and build review artifacts."""
from pathlib import Path
import json,struct,hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'halo64-assets/assets/jorge'
OUT=BASE/'full-cleanup'
REPORT=json.loads((OUT/'cleanup-report.json').read_text())
VIEWS=['front','back','left','right','three_quarter']
BG=(24,30,36);CELL=(31,38,44);INK=(232,239,244);MUTED=(164,184,200);GREEN=(161,205,174)
def font(n):return ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',n)
def tile(path,w,h):
    im=Image.open(path).convert('RGBA');im.thumbnail((w,h),Image.Resampling.LANCZOS)
    out=Image.new('RGB',(w,h),CELL);out.paste(im,((w-im.width)//2,(h-im.height)//2),im);return out

def validate_glb(path,expected):
    data=path.read_bytes();magic,version,length=struct.unpack_from('<III',data);assert magic==0x46546C67 and version==2 and length==len(data)
    size,typ=struct.unpack_from('<II',data,12);assert typ==0x4E4F534A
    doc=json.loads(data[20:20+size]);offset=20+size;blen,btyp=struct.unpack_from('<II',data,offset);assert btyp==0x004E4942
    binary=data[offset+8:offset+8+blen]
    def acc(i):
        a=doc['accessors'][i];v=doc['bufferViews'][a['bufferView']];dtype={5121:'u1',5123:'<u2',5125:'<u4',5126:'<f4'}[a['componentType']]
        n={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']];item=np.dtype(dtype).itemsize
        return np.ndarray((a['count'],n),dtype=dtype,buffer=binary,offset=v.get('byteOffset',0)+a.get('byteOffset',0),strides=(v.get('byteStride',n*item),item))
    tris=verts=0;normal_error=weight_error=0;weighted_bones=set();source=json.loads((OUT/'source-complete.json').read_text());bone_names={n['name'] for n in source['nodes']}
    for node in doc['nodes']:
        if 'mesh' not in node:continue
        skin=doc['skins'][node['skin']];names=[doc['nodes'][j]['name'] for j in skin['joints']];assert len(names)==85 and set(names)==bone_names
        for p in doc['meshes'][node['mesh']]['primitives']:
            assert p.get('mode',4)==4
            a=p['attributes'];indices=acc(p['indices']);positions=acc(a['POSITION']);normals=acc(a['NORMAL']);uv=acc(a['TEXCOORD_0']);w=acc(a['WEIGHTS_0']);j=acc(a['JOINTS_0'])
            assert np.isfinite(positions).all() and np.isfinite(normals).all() and np.isfinite(uv).all()
            assert indices.max()<len(positions) and j.max()<85 and (w>=0).all()
            we=float(np.max(abs(w.sum(axis=1)-1)));weight_error=max(weight_error,we);assert we<1e-6
            ne=float(np.max(abs(np.linalg.norm(normals,axis=1)-1)));normal_error=max(normal_error,ne)
            if expected==REPORT['clean_triangles']:assert ne<1e-5
            weighted_bones.update(names[int(k)] for k in np.unique(j[w>0]));tris+=len(indices)//3;verts+=len(positions)
    assert tris==expected,(path,tris,expected)
    assert all('bufferView' in im for im in doc['images'])
    return {'triangles':tris,'vertices_including_uv_splits':verts,'meshes':len(doc['meshes']),'bones':85,'weighted_bones':sorted(weighted_bones),'embedded_images':len(doc['images']),'materials':len(doc['materials']),
            'max_normal_unit_error':normal_error,'max_skin_weight_sum_error':weight_error,'sha256':hashlib.sha256(data).hexdigest()}

def validate():
    source=json.loads((OUT/'source-complete.json').read_text());clean=json.loads((OUT/'jorge-cleaned.json').read_text())
    for filename,digest in source['source_hashes'].items():assert hashlib.sha256((BASE/filename).read_bytes()).hexdigest()==digest
    assert hashlib.sha256((OUT/'source-complete.json').read_bytes()).hexdigest()==REPORT['source_complete_sha256']
    assert clean['nodes']==source['nodes'] and len(clean['faces'])==REPORT['clean_triangles']
    for key in ['vertices','normals','uv','weights']:assert clean[key]==[source[key][i] for i in clean['source_vertex_ids']]
    for f,fi in zip(clean['faces'],clean['source_face_ids']):assert [clean['source_vertex_ids'][i] for i in f]==source['faces'][fi]
    v=np.array(clean['vertices'])*3.048;f=np.array(clean['faces']);areas=np.linalg.norm(np.cross(v[f[:,1]]-v[f[:,0]],v[f[:,2]]-v[f[:,0]]),axis=1)/2
    assert (areas>=1e-12).all();assert len(set(f.flatten()))==len(v)
    REPORT['validation']['source_files_unchanged']=True;REPORT['validation']['clean_json_retained_attributes_exact']=True;REPORT['validation']['clean_zero_area_faces']=0
    REPORT['glb_validation']={'A':validate_glb(OUT/'jorge-source-reference.glb',REPORT['original_triangles']),'B':validate_glb(OUT/'jorge-cleaned.glb',REPORT['clean_triangles'])}
    REPORT['silhouette_iou']={}
    for view in VIEWS:
        masks=[np.array(Image.open(OUT/'renders'/f'{label}-clay-{view}.png'))[:,:,3]>=128 for label in 'AB'];a,b=masks
        REPORT['silhouette_iou'][view]=float(np.count_nonzero(a&b)/np.count_nonzero(a|b))
    (OUT/'cleanup-report.json').write_text(json.dumps(REPORT,indent=2))
    print(json.dumps({'triangles':REPORT['clean_triangles'],'silhouette_iou':REPORT['silhouette_iou'],'glb':REPORT['glb_validation']['B']},indent=2))

def sheets():
    for style,title in [('textured','Original surface appearance'),('clay','Untextured / no normal maps'),('wire','Triangle topology / no normal maps')]:
        left=145;w=240;h=300;top=130;canvas=Image.new('RGB',(left+5*w,top+2*h+95),BG);d=ImageDraw.Draw(canvas)
        d.text((24,20),'JORGE / SURGICAL CLEANUP',font=font(31),fill=INK);d.text((24,64),title+'  |  Identical camera, framing and lighting',font=font(19),fill=MUTED)
        for col,view in enumerate(VIEWS):d.text((left+col*w+16,105),view.replace('_',' ').upper(),font=font(16),fill=MUTED)
        for row,(label,name,count) in enumerate([('A','Original',33208),('B','Cleaned',26076)]):
            y=top+row*h;d.text((20,y+100),label+'  '+name,font=font(20),fill=INK);d.text((20,y+132),f'{count:,} tri',font=font(18),fill=GREEN if label=='B' else MUTED)
            for col,view in enumerate(VIEWS):canvas.paste(tile(OUT/'renders'/f'{label}-{style}-{view}.png',w,h),(left+col*w,y))
        d.text((24,top+2*h+19),'66 fasteners removed. All other surfaces retained; four zero-area chest faces cleaned.',font=font(21),fill=INK)
        d.text((24,top+2*h+54),'21.5% fewer triangles. Original positions, UVs and skin weights preserved. No global decimation.',font=font(19),fill=GREEN)
        canvas.save(OUT/f'comparison-{style}.png')
    canvas=Image.new('RGB',(1080,760),BG);d=ImageDraw.Draw(canvas);d.text((24,15),'ORIGINAL  /  CLEANED',font=font(28),fill=INK)
    for i,label in enumerate('AB'):canvas.paste(tile(OUT/'renders'/f'{label}-textured-three_quarter.png',540,675),(i*540,65))
    canvas.save(OUT/'comparison-hero.png')
    groups=list(REPORT['groups'])
    for page,start in enumerate(range(0,len(groups),6),1):
        chunk=groups[start:start+6];cw=260;rowh=320;canvas=Image.new('RGB',(cw*4,70+rowh*3),BG);d=ImageDraw.Draw(canvas)
        d.text((24,18),f'COMPONENT REVIEW / {page}   —   Original left, cleaned right',font=font(25),fill=INK)
        for i,g in enumerate(chunk):
            stats=REPORT['groups'][g];x=(i%2)*cw*2;y=70+(i//2)*rowh
            d.text((x+12,y+8),stats['name']+(' (left shown)' if g=='arms-01' else ''),font=font(22),fill=INK);d.text((x+12,y+38),f'{stats["original"]:,} → {stats["clean"]:,} triangles',font=font(18),fill=GREEN if stats['original']!=stats['clean'] else MUTED)
            for j,label in enumerate('AB'):canvas.paste(tile(OUT/'renders'/f'{label}-component-{g}.png',cw,cw),(x+j*cw,y+60))
        canvas.save(OUT/f'components-{page:02d}.png')
    changed=['arms-01','arms-04','body-00','backpack-14'];cw=280;rh=340;canvas=Image.new('RGB',(4*cw,70+rh*2),BG);d=ImageDraw.Draw(canvas)
    d.text((24,18),'WHERE THE TRIANGLES WENT / Original left, cleaned right',font=font(26),fill=INK)
    for i,g in enumerate(changed):
        stats=REPORT['groups'][g];x=(i%2)*cw*2;y=70+(i//2)*rh
        d.text((x+14,y+4),f'{stats["name"]}: {stats["original"]:,} → {stats["clean"]:,}',font=font(22),fill=INK)
        if g=='arms-01':d.text((x+14,y+29),'Left shown; counts include both arms',font=font(16),fill=MUTED)
        for j,label in enumerate('AB'):canvas.paste(tile(OUT/'renders'/f'{label}-component-{g}.png',cw,cw),(x+j*cw,y+50))
    canvas.save(OUT/'comparison-changed-components.png')
    poses=['rest','aiming','stride','crouch_twist','hands_and_head'];w=240;h=300;canvas=Image.new('RGB',(1200,720),BG);d=ImageDraw.Draw(canvas)
    d.text((20,14),'POSE CHECKS / Original above, cleaned below',font=font(27),fill=INK)
    for i,p in enumerate(poses):
        d.text((i*w+12,58),p.replace('_',' '),font=font(18),fill=MUTED)
        for row,label in enumerate('AB'):canvas.paste(tile(OUT/'renders'/f'{label}-pose-{p}.png',w,h),(i*w,90+row*h))
    d.text((20,694),'Retained vertex positions match exactly in all five pose checks. These are diagnostic poses, not animation clips.',font=font(17),fill=GREEN);canvas.save(OUT/'comparison-poses.png')
    canvas=Image.new('RGB',(1200,570),BG);d=ImageDraw.Draw(canvas);d.text((20,15),'REMOVED FASTENERS / highlighted in red',font=font(28),fill=INK)
    for i,view in enumerate(['front','back','three_quarter']):canvas.paste(tile(OUT/'renders'/f'removed-highlight-{view}.png',400,500),(i*400,60))
    canvas.save(OUT/'removed-details.png')

if __name__=='__main__':validate();sheets()
