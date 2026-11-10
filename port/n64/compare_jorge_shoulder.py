"""Build matched comparison sheets and validate portable GLB outputs."""
from pathlib import Path
import json,struct,hashlib
import numpy as np
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'halo64-assets/assets/jorge/shoulder-study'
REPORT=json.loads((OUT/'study-report.json').read_text())
VIEWS=['front','side','three_quarter']
NAMES={'A':'Original','B':'Surgical culling','C':'Culling + constrained','D':'Direct decimation'}
def font(size):
    return ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',size)

def tile(path,size):
    im=Image.open(path).convert('RGBA');im.thumbnail((size,size),Image.Resampling.LANCZOS)
    out=Image.new('RGB',(size,size),(30,35,41));out.paste(im,((size-im.width)//2,(size-im.height)//2),im)
    return out

def sheets():
    for style,title in [('textured','Original surface appearance / C and D rebaked'),('clay','Untextured / no normal map'),('wire','Triangle topology / no normal map')]:
        cell=344;left=110;top=142
        canvas=Image.new('RGB',(left+cell*4,top+cell*3+85),(20,25,31));dr=ImageDraw.Draw(canvas)
        dr.text((25,18),'JORGE / LEFT SHOULDER',font=font(30),fill=(236,240,244))
        dr.text((25,58),title+'  |  Identical camera, scale and lighting',font=font(19),fill=(172,189,202))
        for col,label in enumerate('ABCD'):
            x=left+col*cell
            dr.text((x+12,98),f'{label}  {NAMES[label]}',font=font(19),fill=(234,238,241))
            dr.text((x+12,122),f'{REPORT["counts"][label]["triangles"]:,} triangles',font=font(16),fill=(157,188,161) if label=='C' else (168,181,193))
            for row,view in enumerate(VIEWS):
                y=top+row*cell;canvas.paste(tile(OUT/'renders'/f'{label}-{style}-{view}.png',cell),(x,y))
                dr.line((x,y,x+cell,y),fill=(53,62,72))
        for row,name in enumerate(['FRONT','SIDE','3/4']):dr.text((18,top+row*cell+cell//2),name,font=font(17),fill=(183,198,209))
        dr.text((25,top+3*cell+15),'B removes ten fasteners; every original armor-plate triangle remains. C and D have identical triangle counts.',font=font(18),fill=(201,211,220))
        dr.text((25,top+3*cell+43),'C: 372 protected edges retained. Sampled plate error: 0.096 mm RMS / 0.779 mm maximum.',font=font(18),fill=(158,188,164))
        canvas.save(OUT/f'comparison-{style}.png')
    poses=['rest','arm_raised','aiming','pad_articulation'];cell=320
    canvas=Image.new('RGB',(cell*4,cell+100),(20,25,31));dr=ImageDraw.Draw(canvas)
    dr.text((20,15),'Original 85-bone skeleton / rigid shoulder attachment / C',font=font(25),fill=(230,237,243))
    for i,p in enumerate(poses):
        canvas.paste(tile(OUT/'renders'/f'C-pose-{p}.png',cell),(i*cell,70));dr.text((i*cell+16,48),p.replace('_',' '),font=font(18),fill=(170,189,204))
    dr.text((20,cell+76),'Camera follows the pad. These are shoulder attachment checks, not full-character animation validation.',font=font(17),fill=(184,197,209));canvas.save(OUT/'comparison-poses.png')
    # A small image-scale comparison reveals whether tiny details matter in play.
    canvas=Image.new('RGB',(660,240),(20,25,31));dr=ImageDraw.Draw(canvas)
    dr.text((16,12),'At 128-pixel shoulder preview size',font=font(22),fill=(230,237,243))
    for i,label in enumerate('ABCD'):
        x=12+i*164;dr.text((x,49),f'{label} / {REPORT["counts"][label]["triangles"]} tri',font=font(18),fill=(180,199,211))
        canvas.paste(tile(OUT/'renders'/f'{label}-textured-side.png',128),(x,80))
    canvas.save(OUT/'comparison-small.png')

def glb(path):
    data=path.read_bytes();magic,version,length=struct.unpack_from('<III',data)
    assert magic==0x46546C67 and version==2 and length==len(data)
    size,typ=struct.unpack_from('<II',data,12);assert typ==0x4E4F534A
    doc=json.loads(data[20:20+size]);offset=20+size
    blen,btyp=struct.unpack_from('<II',data,offset);assert btyp==0x004E4942
    binary=data[offset+8:offset+8+blen]
    def acc(i):
        a=doc['accessors'][i];v=doc['bufferViews'][a['bufferView']]
        dtype={5121:'u1',5123:'<u2',5125:'<u4',5126:'<f4'}[a['componentType']]
        n={'SCALAR':1,'VEC2':2,'VEC3':3,'VEC4':4,'MAT4':16}[a['type']]
        item=np.dtype(dtype).itemsize
        return np.ndarray((a['count'],n),dtype=dtype,buffer=binary,offset=v.get('byteOffset',0)+a.get('byteOffset',0),strides=(v.get('byteStride',n*item),item))
    tris=0;verts=0;max_norm_error=0;names=set();texture_uv_sets=set()
    for node in doc['nodes']:
        if 'mesh' not in node:continue
        skin=doc['skins'][node['skin']];assert len(skin['joints'])==85
        joint_names=[doc['nodes'][j]['name'] for j in skin['joints']]
        for p in doc['meshes'][node['mesh']]['primitives']:
            assert p.get('mode',4)==4
            attrs=p['attributes'];inds=acc(p['indices']);positions=acc(attrs['POSITION']);normals=acc(attrs['NORMAL']);uv=acc(attrs['TEXCOORD_0'])
            mat=doc['materials'][p['material']]
            for tex in [mat['pbrMetallicRoughness']['baseColorTexture'],mat['normalTexture']]:
                uv_set=tex.get('texCoord',0);texture_uv_sets.add(uv_set);assert np.isfinite(acc(attrs[f'TEXCOORD_{uv_set}'])).all()
            weights=acc(attrs['WEIGHTS_0']);joints=acc(attrs['JOINTS_0']);assert np.allclose(weights.sum(axis=1),1)
            assert np.isfinite(positions).all() and np.isfinite(normals).all() and np.isfinite(uv).all()
            assert inds.max()<len(positions)
            for j in np.unique(joints[weights>0]):names.add(joint_names[int(j)])
            tris+=len(inds)//3;verts+=len(positions);max_norm_error=max(max_norm_error,float(np.max(abs(np.linalg.norm(normals,axis=1)-1))))
    assert names=={'b_l_shoulderpad'}
    assert len(doc['images'])==2 and all('bufferView' in i for i in doc['images'])
    return {'triangles':tris,'export_vertices_including_uv_splits':verts,'bones':85,'weighted_bones':sorted(names),'embedded_images':len(doc['images']),'texture_uv_sets':sorted(texture_uv_sets),'max_unit_normal_error':max_norm_error,'sha256':hashlib.sha256(data).hexdigest()}

def validate():
    REPORT['glb_validation']={label:glb(OUT/f'shoulder-{label}.glb') for label in 'ABCD'}
    for label,r in REPORT['glb_validation'].items():assert r['triangles']==REPORT['counts'][label]['triangles']
    REPORT['silhouette_iou']={}
    for view in VIEWS:
        masks={label:np.array(Image.open(OUT/'renders'/f'{label}-clay-{view}.png'))[:,:,3]>=128 for label in 'ABCD'}
        REPORT['silhouette_iou'][view]={baseline:{label:float(np.count_nonzero(masks[baseline]&masks[label])/np.count_nonzero(masks[baseline]|masks[label])) for label in 'BCD'} for baseline in 'AB'}
    assert hashlib.sha256((OUT/'shoulder-original.json').read_bytes()).hexdigest()==REPORT['source_sha256']
    original=OUT.parent/'jorge-original.json'
    assert hashlib.sha256(original.read_bytes()).hexdigest()=='9be4eac2cf7082fa3ddb8fc40e93bc3f0ee294253172ce5ba61158ed115094e0'
    REPORT['whole_character_source_unchanged']=True
    (OUT/'study-report.json').write_text(json.dumps(REPORT,indent=2))
    print(json.dumps({'exports':REPORT['glb_validation'],'silhouettes':REPORT['silhouette_iou']},indent=2))

if __name__=='__main__':
    validate();sheets()
