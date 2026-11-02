"""Preserve the owned retail Reach GUNGNIR customization and native rig.

Uses the Reach render-model layout documented by Reclaimer. Unlike Jorge's
single assembly, Spartan customization also requires permutation instance masks,
the instanced section's subsets, authored transforms and rigid parent bones.
"""
import argparse, hashlib, json, struct
from pathlib import Path
import numpy as np
from reach_cache import ReachCache
from extract_jorge import bitmap

SELECTION={'arms':'default','body':'default','decals':'default',
    'head':'player_kelly','flair_chest_a':'player_kelly',
    'flair_forearm':'player_kelly','flair_left_shoulder':'player_kelly',
    'flair_right_shoulder':'player_kelly','flair_knees':'default'}


def decode_bitmap(cache,tag,output):
    b=cache.block(tag['offset']+124,44)[0]
    if cache.unpack('h',b+8)[0]!=11:return bitmap(cache,tag,output)
    from arbytmap import Arbytmap,bitmap_io,FORMAT_A8R8G8B8,TYPE_2D
    from reclaimer.h3.util import get_virtual_dimension
    width,height,depth,flags=cache.unpack('HHBB',b);assert depth==1 and cache.data[b+6]==0
    refs=cache.block(tag['offset']+168,8);assert len(refs)==1 and not cache.block(tag['offset']+180,8)
    _,data=cache.resource(cache.u32(refs[0]));texture=[]
    bitmap_io.bitmap_bytes_to_array(data,0,texture,FORMAT_A8R8G8B8,1,1,1,width*height*4)
    output.mkdir(parents=True,exist_ok=True);target=output/(str(tag['id'])+'_'+tag['path'].split('\\')[-1]+'.png')
    image=Arbytmap();image.load_new_texture(texture_block=texture,texture_info=dict(width=width,height=height,depth=1,mipmap_count=0,swizzled=False,big_endian=True,packed=True,tiled=bool(flags&8),tile_method='DXGI',packed_width_calc=get_virtual_dimension,packed_height_calc=get_virtual_dimension,texture_type=TYPE_2D,sub_bitmap_count=1,format=FORMAT_A8R8G8B8,filepath=str(target)),tile_mode=False,swizzle_mode=False)
    image.save_to_file(keep_alpha=True);return str(target.resolve())


def bone_globals(nodes):
    result=[]
    for node in nodes:
        x,y,z,w=node['q']
        m=np.array([[1-2*(y*y+z*z),2*(x*y-z*w),2*(x*z+y*w),0],
                    [2*(x*y+z*w),1-2*(x*x+z*z),2*(y*z-x*w),0],
                    [2*(x*z-y*w),2*(y*z+x*w),1-2*(x*x+y*y),0],[0,0,0,1.]])
        m[:3,3]=node['p'];result.append(result[node['parent']]@m if node['parent']>=0 else m)
    return result


def extract(path,output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True);c=ReachCache(path)
    tag=next(t for t in c.by_class['mode'] if t['path']==r'objects\characters\spartans\spartans');m=tag['offset']
    nodes=[dict(name=c.sid(c.u32(n)),parent=c.unpack('h',n+4)[0],p=c.unpack('3f',n+12),q=c.unpack('4f',n+24)) for n in c.block(m+48,96)]
    bind=bone_globals(nodes);info,data=c.resource(c.u32(m+248));start=info['fixup_start']
    # Keep the untouched packed streams as well as decoded authoring geometry.
    (output/'render-resource.bin').write_bytes(data)
    nv=c.u32(start+info['fixup_size']-24);ni=c.u32(start+info['fixup_size']-12)
    vi=[(c.u32(start+i*28),c.u32(start+i*28+8)) for i in range(nv)]
    ii=[(c.u32(start+nv*40+i*28),c.u32(start+nv*40+i*28+8)) for i in range(ni)]
    bounds=c.unpack('10f',c.block(m+116,52)[0]+4);sections=c.block(m+104,92);maps=c.block(m+176,12)
    model=dict(tag=tag['path'],cache_build=c.build,vertices=[],uv=[],weights=[],faces=[],materials=[],regions=[],nodes=nodes,material_metadata=[],selection=SELECTION,attachments=[],source_vertex_records=[],markers={})
    for group in c.block(m+60,16):
        name=c.sid(c.u32(group));model['markers'][name]=[dict(node=c.data[p+2],p=c.unpack('3f',p+4),q=c.unpack('4f',p+16)) for p in c.block(group+4,48)]
    def mesh(si,region,subset=None,rigid_override=None,transform=None):
        s=sections[si];vb=c.unpack('h',s+24)[0];ib=c.unpack('h',s+40)[0];rigid,fmt=c.unpack('BB',s+46)
        count,length=vi[vb];stride=length//count;offset=info['fixups'][vb];it,il=ii[ib]
        assert fmt in (28,29) and stride in (16,24)
        indices=struct.unpack_from('>'+str(il//2)+'H',data,info['fixups'][nv*2+ib])
        parts=[(c.unpack('h',p)[0],*c.unpack('II',p+4)) for p in c.block(s,24)]
        if subset is not None:
            p=c.block(s+12,16)[subset];first,length,part=c.unpack('IIH',p);parts=[(parts[part][0],first,length)]
        selected=sorted({i for _,first,length in parts for i in indices[first:first+length]});lookup={};node_map=[c.data[p] for p in c.block(maps[si],1)] if maps else None
        for i in selected:
            at=offset+i*stride;pk=struct.unpack_from('>I',data,at)[0];uv=struct.unpack_from('>2H',data,at+4)
            point=np.array([bounds[a*2]+((pk>>(a*10))&1023)/1023*(bounds[a*2+1]-bounds[a*2]) for a in range(3)]+[1.])
            if transform is not None:point=transform@point
            if rigid_override is not None:weights=[(rigid_override,1.)]
            elif fmt==28:weights=[(rigid,1.)]
            else:
                bones=data[at+16:at+20];weights_raw=data[at+20:at+24];total=sum(weights_raw);assert total
                weights=[(node_map[b] if node_map else b,x/total) for b,x in zip(bones,weights_raw) if x]
            lookup[i]=len(model['vertices']);model['vertices'].append(point[:3].tolist());model['weights'].append(weights)
            model['uv'].append([bounds[6+a*2]+uv[a]/65535*(bounds[7+a*2]-bounds[6+a*2]) for a in range(2)])
            model['source_vertex_records'].append(dict(section=si,index=i,instance=subset,packed=data[at:at+stride].hex()))
        for material,first,length in parts:
            idx=indices[first:first+length]
            for i in range(0,len(idx)-2,3 if it==3 else 1):
                a,b,d=idx[i:i+3]
                if it==5 and i&1:a,b=b,a
                if len({a,b,d})<3:continue
                model['faces'].append([lookup[v] for v in (a,b,d)]);model['materials'].append(material);model['regions'].append(region)
    instances=c.block(m+32,60);selected_instances={}
    for r in c.block(m+12,16):
        region=c.sid(c.u32(r))
        if region not in SELECTION:continue
        p=next(p for p in c.block(r+4,24) if c.sid(c.u32(p))==SELECTION[region]);first,count=c.unpack('hh',p+4)
        for si in range(first,first+count):mesh(si,region)
        masks=c.unpack('4I',p+8)
        for i in range(len(instances)):
            if masks[i//32]&(1<<(i%32)):selected_instances[i]=region
    for i,region in sorted(selected_instances.items()):
        p=instances[i];bone=c.i32(p+4);scale=c.unpack('f',p+8)[0];values=np.array(c.unpack('12f',p+12)).reshape(4,3)
        xf=np.eye(4);xf[:3,:3]=values[:3].T*scale;xf[:3,3]=values[3];world=bind[bone]@xf
        name=c.sid(c.u32(p));model['attachments'].append(dict(index=i,name=name,region=region,bone=bone,authored_transform=xf.tolist(),bone_bind_transform=bind[bone].tolist(),coordinate_note='Instanced render vertices already occupy model bind space; the bone indexes rigid skinning, not a second bind-space placement'))
        mesh(c.i32(m+28),region,subset=i,rigid_override=bone,transform=xf)
    used_materials=set(model['materials'])
    for mi,p in enumerate(c.block(m+72,44)):
        shader=c.tag_ref(p);props=c.block(shader['offset']+56,172)
        refs=[c.tag_ref(v) for v in c.block(props[0]+16,24)] if props else []
        diffuse=next((t for t in refs if t and any(t['path'].endswith(s) for s in ('_diff','_diffuse','_base'))),None)
        meta=dict(path=shader['path'],diffuse=decode_bitmap(c,diffuse,output/'textures') if diffuse and mi in used_materials else None)
        cc=next((t for t in refs if t and t['path'].endswith('_cc')),None)
        if cc and mi in used_materials:meta['cc']=decode_bitmap(c,cc,output/'textures')
        model['material_metadata'].append(meta)
    target=output/'gungnir-original.json';target.write_text(json.dumps(model,separators=(',',':'))+'\n')
    provenance=dict(game='Halo: Reach retail',build=c.build,cache=str(c.path),cache_sha256=hashlib.sha256(c.path.read_bytes()).hexdigest(),tag=tag['path'],selection=SELECTION,attachments=model['attachments'],nodes=len(nodes),vertices=len(model['vertices']),triangles=len(model['faces']),coordinates='Authored Halo world units, Z up; native quaternion order XYZW; no scale edits',original_json_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),resource_sha256=hashlib.sha256(data).hexdigest(),extractor_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (output/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n');c.close()
    print(json.dumps({k:v for k,v in provenance.items() if k not in ('attachments','selection')},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('cache',type=Path);p.add_argument('output',type=Path);a=p.parse_args();extract(a.cache,a.output)
