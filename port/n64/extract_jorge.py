"""Extract Jorge's intact retail Reach model for semantic reconstruction.
Reads owned m05.map/shared.map/campaign.map; writes private source JSON and PNGs.
"""
import json,struct,hashlib
from pathlib import Path
from reach_cache import ReachCache

def bitmap(cache,tag,output):
 from arbytmap import Arbytmap,bitmap_io,FORMAT_DXT1,FORMAT_DXT3,FORMAT_DXT5,FORMAT_DXT5AY,FORMAT_CTX1,FORMAT_A8,FORMAT_A8L8,FORMAT_DXN,TYPE_2D
 from reclaimer.h3.util import get_virtual_dimension
 output.mkdir(parents=True,exist_ok=True)
 target=output/(str(tag['id'])+'_'+tag['path'].split('\\')[-1]+'.png')
 b=cache.block(tag['offset']+124,44)[0]
 width,height,depth,flags=cache.unpack('HHBB',b)
 typ=cache.data[b+6];fmt=cache.unpack('h',b+8)[0]
 if typ!=0 or depth!=1:raise ValueError((tag['path'],'not 2D',typ,depth))
 formats={38:FORMAT_DXN,44:FORMAT_DXN,0:FORMAT_A8,3:FORMAT_A8L8,14:FORMAT_DXT1,15:FORMAT_DXT3,16:FORMAT_DXT5,39:FORMAT_CTX1}
 refs=cache.block(tag['offset']+168,8)
 if len(refs)!=1 or cache.block(tag['offset']+180,8):raise ValueError('Interleaved bitmap')
 _,data=cache.resource(cache.u32(refs[0]));size=width*height//2 if fmt in (14,39) else width*height*(2 if fmt==3 else 1)
 texture=[];bitmap_io.bitmap_bytes_to_array(data,0,texture,formats[fmt],1,1,1,size)
 a=Arbytmap();a.load_new_texture(texture_block=texture,texture_info=dict(width=width,height=height,
 depth=1,mipmap_count=0,swizzled=False,big_endian=True,packed=True,tiled=bool(flags&8),tile_method='DXGI',
 packed_width_calc=get_virtual_dimension,packed_height_calc=get_virtual_dimension,texture_type=TYPE_2D,
 sub_bitmap_count=1,format=formats[fmt],filepath=str(target)),tile_mode=False,swizzle_mode=False)
 a.save_to_file(keep_alpha=True)
 return str(target.resolve())

def extract(path,out,tag_name='spartan_jorge\\spartan_jorge',name='jorge-original'):
 out=Path(out);out.mkdir(parents=True,exist_ok=True);c=ReachCache(path)
 tag=next(t for t in c.by_class['mode'] if t['path'].endswith(tag_name));m=tag['offset']
 nodes=[{'name':c.sid(c.u32(n)),'parent':c.unpack('h',n+4)[0], 'p':c.unpack('3f',n+12),'q':c.unpack('4f',n+24)} for n in c.block(m+48,96)]
 info,data=c.resource(c.u32(m+248));start=info['fixup_start']
 nv=c.u32(start+info['fixup_size']-24);ni=c.u32(start+info['fixup_size']-12)
 vi=[(c.u32(start+i*28),c.u32(start+i*28+8)) for i in range(nv)]
 ii=[(c.u32(start+nv*40+i*28),c.u32(start+nv*40+i*28+8)) for i in range(ni)]
 bounds=c.unpack('10f',c.block(m+116,52)[0]+4);sections=c.block(m+104,92);maps=c.block(m+176,12)
 model={'tag':tag['path'],'cache_build':c.build,'vertices':[],'uv':[],'weights':[],'faces':[],'materials':[],'regions':[],'nodes':nodes,'material_metadata':[]}
 for r in c.block(m+12,16):
  region=c.sid(c.u32(r));p=c.block(r+4,24)[0];first,n=c.unpack('hh',p+4)
  for si in range(first,first+n):
   s=sections[si];vb=c.unpack('h',s+24)[0];ib=c.unpack('h',s+40)[0];rigid,fmt=c.unpack('BB',s+46)
   count,length=vi[vb];stride=length//count;offset=info['fixups'][vb];it,il=ii[ib]
   print(region,count,stride,fmt,it,flush=True)
   assert fmt in (28,29) and stride in (16,24)
   indices=struct.unpack_from('>'+str(il//2)+'H',data,info['fixups'][nv*2+ib]);base=len(model['vertices'])
   node_map=[c.data[p] for p in c.block(maps[si],1)] if maps else None
   for i in range(count):
    at=offset+i*stride;pk=struct.unpack_from('>I',data,at)[0];uv=struct.unpack_from('>2H',data,at+4)
    model['vertices'].append([bounds[a*2]+((pk>>(a*10))&1023)/1023*(bounds[a*2+1]-bounds[a*2]) for a in range(3)])
    model['uv'].append([bounds[6+a*2]+uv[a]/65535*(bounds[7+a*2]-bounds[6+a*2]) for a in range(2)])
    if fmt==28:w=[(rigid,1.)]
    else:
     bones=data[at+16:at+20];weights=data[at+20:at+24];total=sum(weights)
     w=[(node_map[b] if node_map else b,x/total) for b,x in zip(bones,weights) if x]
    model['weights'].append(w)
   for part in c.block(s,24):
    mat=c.unpack('h',part)[0];first,length=c.unpack('II',part+4);idx=indices[first:first+length]
    for i in range(0,len(idx)-2,3 if it==3 else 1):
     a,b,d=idx[i:i+3]
     if it==5 and i&1:a,b=b,a
     if len({a,b,d})<3:continue
     assert max(a,b,d)<count
     model['faces'].append([base+a,base+b,base+d]);model['materials'].append(mat);model['regions'].append(region)
 for p in c.block(m+72,44):
  sh=c.tag_ref(p);prop=c.block(sh['offset']+56,172)[0]
  refs=[c.tag_ref(v) for v in c.block(prop+16,24)];meta={'path':sh['path'],'diffuse':bitmap(c,refs[0],out/'textures')}
  cc=next((t for t in refs if t and t['path'].endswith('_cc')),None)
  if cc:meta['cc']=bitmap(c,cc,out/'textures')
  model['material_metadata'].append(meta)
 (out/(name+'.json')).write_text(json.dumps(model,separators=(',',':')))
 print('triangles',len(model['faces']),'nodes',len(nodes))
 c.close()
if __name__=='__main__':
 import sys
 extract(*sys.argv[1:])
