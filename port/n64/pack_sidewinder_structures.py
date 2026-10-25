"""Pack only accepted architecture components; retain every other batch exactly."""
import collections
import csv
import json
import math
import os
import re
import statistics
import struct
import subprocess
from sidewinder_structures import ROOT,PREVIOUS,OUT,sha
from remap_sidewinder_visibility import sections,batches
from pack_maps import bank,packed,uv_safe_triangles
from pack_terrain import indexed_terrain


def pack():
    source=json.loads((OUT/'source.json').read_text());candidate=json.loads((OUT/'candidate.json').read_text())
    assert sha((OUT/'source.json').read_bytes())==candidate['source_sha256']
    original=(PREVIOUS/'candidate-maps/sidewinder.map64').read_bytes();assert sha(original)==source['bank_sha256']==candidate['bank_sha256']
    ss=sections(original);visibility=json.loads((PREVIOUS/'data/visibility.json').read_text())
    source_faces={(r['batch'],r['face']):r for r in source['triangles']};removed=set();additions=collections.defaultdict(list)
    accepted={(r['material'],r['mask'],r['component']):r for r in candidate['report'] if r['accepted']}
    for r in accepted.values():
        assert r['sampled_boundary_error']<=candidate['boundary_limit'] and r['sampled_surface_error']<=candidate['surface_limit']
        assert r['sampled_uv_error_texels']<=candidate['uv_error_limit_texels'] and r['sampled_color_error']<=candidate['color_error_limit']
        for b,f in r['source_refs']:
            assert source_faces[b,f]['editable'];assert (b,f) not in removed;removed.add((b,f))
    for r in candidate['triangles']:
        key=r['material'],r['mask'],r['component']
        if key not in accepted:continue
        refs=accepted[key]['source_refs'];center=[sum(v[a] for v in r['triangle'])/3 for a in range(3)]
        nearest=min(refs,key=lambda ref:sum((sum(v[a] for v in source_faces[tuple(ref)]['triangle'])/3-center[a])**2 for a in range(3)))
        b=nearest[0];assert visibility['chunk_masks'][b]==r['mask'];additions[b].append(r['triangle'])
    affected={b for b,f in removed};rows=collections.defaultdict(list)
    for (b,f),r in source_faces.items():
        if b in affected and (b,f) not in removed:rows[b].append(r['triangle'])
    for b,tris in additions.items():rows[b].extend(tris)
    vertex=bytearray();indices=bytearray();chunks=[];proof=[];masks=[];unchanged=[]
    for b,c in enumerate(struct.iter_unpack('>IHH6hHH',ss[1])):
        first,count,material,*rest=c;at,n=rest[-2:];base_vertex=len(vertex)//16;base_index=len(indices)//2
        if b not in affected:
            v=ss[0][first//2*32:(first+((count+1)&~1))//2*32];ix=ss[2][at*2:(at+((n+3)&~3))*2]
            chunks.append((base_vertex,count,material,*rest[:6],base_index,n));vertex.extend(v);indices.extend(ix);proof.append({'old_batch':b,'unchanged':True});masks.append(visibility['chunk_masks'][b]);unchanged.append((b,len(chunks)-1));continue
        for batch in indexed_terrain(uv_safe_triangles(rows[b]),uv_period=1024):
            unique=batch['vertices'];ix=batch['indices'];first=len(vertex)//16;start=len(indices)//2
            padded=unique+([unique[-1]] if len(unique)%2 else [])
            pairs=[]
            for a,d in zip(padded[::2],padded[1::2]):
                rgba=lambda v:(v[3]<<24)|(v[4]<<16)|(v[5]<<8)|255
                pairs.append((*a[:3],0,*d[:3],0,rgba(a),rgba(d),*a[6:],*d[6:]))
            vertex.extend(packed('3hH3hHII4h',pairs));indices.extend(packed('H',[(i,) for i in ix]))
            while len(indices)%8:indices.extend(b'\0\0')
            bounds=[math.floor(min(v[a] for v in unique)/8) for a in range(3)]+[math.ceil(max(v[a] for v in unique)/8) for a in range(3)]
            chunks.append((first,len(unique),material,*bounds,start,len(ix)));proof.append({'old_batch':b,'unchanged':False});masks.append(visibility['chunk_masks'][b])
    assert len(chunks)<=512 and len(indices)//2<65536
    destination=OUT/'candidate-maps';destination.mkdir(exist_ok=True)
    for p in (PREVIOUS/'candidate-maps').iterdir():
        if p.name!='sidewinder.map64' and not (destination/p.name).exists():(destination/p.name).symlink_to(p.resolve())
    ss[0]=bytes(vertex);ss[1]=packed('IHH6hHH',chunks);ss[2]=bytes(indices)
    result=bank(destination/'sidewinder.map64',1,ss);payload=(destination/'sidewinder.map64').read_bytes()
    assert sections(payload)[3:]==sections(original)[3:]
    before=list(batches(original));after=list(batches(payload))
    for a,b in unchanged:assert before[a][1]==after[b][1]
    assert all(b not in affected for b in source['protected_batches'])
    result.update(baseline_sha256=sha(original),candidate_sha256=sha(payload),source_json_sha256=sha((OUT/'source.json').read_bytes()),candidate_json_sha256=sha((OUT/'candidate.json').read_bytes()),changed_source_batches=sorted(affected),unchanged_batches=len(unchanged),chunks=len(chunks),vertices=len(vertex)//16,triangles=sum(c[-1]//3 for c in chunks),unchanged_nonrender_sections=True,batches=proof,chunk_masks=masks)
    (OUT/'packing-report.json').write_text(json.dumps(result,indent=2)+'\n')
    # The previous hash-bound source classifier and PVS rows are unchanged.
    # Only the chunk-mask array and its count change in this private probe.
    c=(PREVIOUS/'cameras/visibility-data.c').read_text()
    c,n=re.subn(r'static const uint64_t chunks\[\]=\{[^}]+\};','static const uint64_t chunks[]={'+','.join('UINT64_C('+str(m)+')' for m in masks)+'};',c);assert n==1
    c,n=re.subn(r'(bg_world_pvs=\{nodes,planes,leaves,rows,chunks,\d+,\d+,\d+,35,)478,',lambda m:m[1]+str(len(chunks))+',',c);assert n==1
    (OUT/'visibility-data.c').write_text(c)
    print(json.dumps({k:result[k] for k in ['vertices','chunks','triangles','unchanged_batches']}))


def measure():
    sdk=ROOT.parent/'n64-3d-splitscreen/.build/tiny3d/src';solver=PREVIOUS/'cameras/solver';results={}
    for name,directory in [('replay',PREVIOUS/'cameras'),('photos',PREVIOUS/'after-census')]:
        output=OUT/name;output.mkdir(exist_ok=True);driver=(directory/'camera.c').read_text()
        if name=='replay':driver,n=re.subn(r'const unsigned maps\[\]=\{[^}]+\};','const unsigned maps[]={1};',driver);assert n==1
        if name=='photos':
            anchor=' camera(p,&eye,&matrix,&f);'
            assert driver.count(anchor)==1
            driver=driver.replace(anchor,anchor+'\n fprintf(stderr,"%u",tick);for(unsigned column=0;column<4;column++)for(unsigned row=0;row<4;row++)fprintf(stderr,",%.9g",matrix.m[column][row]);fputc(10,stderr);')
        (output/'camera.c').write_text(driver)
        flags=['-std=c17','-O2','-g','-fsanitize=address,undefined','-ffp-contract=off','-fno-fast-math','-fno-strict-aliasing','-fwrapv','-Wno-multichar','-Wno-unused-function','-Wno-incompatible-pointer-types','-DBG_STREAM_MAPS','-DBG_BODY_CANDIDATES','-I'+str(PREVIOUS/'cameras'),'-I'+str(sdk),'-Iport/n64','-Ibuild/n64/blam-core','-I'+str(solver)]
        sources=['map.c','game.c','combat_geometry.c','terrain.c','movement.c','blam/runtime.c','blam/core.c','blam/vehicle_physics.c','replay.c','render_pvs.c']
        generated=['combat_data.c','movement_data.c','interaction_defs.c','camera_data.c']
        cmd=['clang',*flags,str(output/'camera.c'),str(OUT/'visibility-data.c'),str(sdk/'t3d/t3dmath.c'),*(str(ROOT/'port/n64'/s) for s in sources),*(str(ROOT/'build/n64/generated'/s) for s in generated),str(ROOT/'halo64-assets/generated/maps/common_data.c'),str(solver/'vehicle_data.c'),'-lm','-o',str(output/'probe')]
        subprocess.run(cmd,cwd=ROOT,check=True)
        with (output/'poses.json').open('w') as stdout,(output/'matrix-trace.csv').open('w') as trace:subprocess.run([str(output/'probe'),str(output/'cameras.csv')],cwd=ROOT,check=True,stdout=stdout,stderr=trace,env={**os.environ,'BG_MAP_DIRECTORY':str(OUT/'candidate-maps')})
        before=[r for r in csv.DictReader((directory/'cameras.csv').open()) if r['map']=='1' and r['candidate']=='1'];after=[r for r in csv.DictReader((output/'cameras.csv').open()) if r['candidate']=='1']
        assert len(before)==len(after)
        for a,b in zip(before,after):assert all(a[k]==b[k] for k in ['map','tick','camera','eye_x','eye_y','eye_z','alive','zoom','pvs_mask'])
        if name=='photos':assert json.loads((output/'poses.json').read_text())==json.loads((directory/'poses.json').read_text())
        results[name]={'samples':len(after),'before_mean':statistics.mean(int(r['vertices']) for r in before),'after_mean':statistics.mean(int(r['vertices']) for r in after),'after_worst':max(int(r['vertices']) for r in after),'below_1500':sum(int(r['vertices'])<1500 for r in after),'matching_poses':True}
    (OUT/'measurements.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))

if __name__=='__main__':pack();measure()
