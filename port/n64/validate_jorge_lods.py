"""Compare quantized source/LOD coverage at each LOD's intended pixel sizes."""
from pathlib import Path
import json,sys,math,hashlib
from collections import Counter
sys.path.insert(0,str(Path(__file__).resolve().parent))
import numpy as np
import validate_jorge_solid as coverage
import jorge_lods as task

# Runtime (x,up,-y) to Blender (y,-x,up), in meters.
AXIS=np.array(((0,0,-1),(-1,0,0),(0,1,0)))

def posed(data,meta,clip,fraction):
    frames=data['frames_'+str(clip)];f=fraction*(len(frames)-1);a=int(f);b=min(a+1,len(frames)-1);t=f-a
    p=np.round(frames[a]*512)*(1-t)+np.round(frames[b]*512)*t
    p=p/512@AXIS.T*3.048
    keys=sorted(set(meta['components']));parts=np.array([keys.index(k)+1 for k in meta['components'][::3]])
    return p,data['triangles'],np.ones(len(data['triangles']),dtype=np.int16),parts,keys

def run(full=False):
    src=np.load(task.SOURCE/'gameplay-poses.npz');sm=json.loads((task.SOURCE/'gameplay-poses.json').read_text())
    samples=[(0,0),(0,.5),(1,.25),(1,.75),(2,.5),(3,.4),(3,.8)]
    if full:samples=[(i,f) for i in range(39) for f in (0,.45,.9)]
    directions=[(math.sin(i*math.pi/4),-math.cos(i*math.pi/4),.12) for i in range(8)]+[(.7,-1,.65),(-.7,1,.65)]
    for lod,sizes in [('near',(64,96)),('far',(32,48))]:
        if '--lod' in sys.argv and sys.argv[sys.argv.index('--lod')+1]!=lod:continue
        folder=task.OUT/lod;d=np.load(folder/'gameplay-poses.npz');meta=json.loads((folder/'gameplay-poses.json').read_text())
        source_hash=hashlib.sha256((folder/'gameplay-poses.npz').read_bytes()).hexdigest()
        rows=[];losses=Counter();patches={};minimum_area_ratio=1.
        # Every frame must stay finite, with no collapsed/inverted-to-zero
        # surface. Record the worst ratio; joint bending is not rigid motion.
        rest=d['rest'][d['triangles']]
        area=np.linalg.norm(np.cross(rest[:,1]-rest[:,0],rest[:,2]-rest[:,0]),axis=1)
        assert area.min()>1e-10
        for ci in range(39):
            frames=d['frames_'+str(ci)];assert np.isfinite(frames).all()
            tris=frames[:,d['triangles']]
            a=np.linalg.norm(np.cross(tris[:,:,1]-tris[:,:,0],tris[:,:,2]-tris[:,:,0]),axis=2)
            minimum_area_ratio=min(minimum_area_ratio,float((a/area).min()))
            assert np.array_equal(d['grips_'+str(ci)],src['grips_'+str(ci)])
        for ci,f in samples:
            before=posed(src,sm,ci,f);after=posed(d,meta,ci,f)
            # Vehicle clips move the root far from the idle origin. Follow
            # the source bounds with a shared camera for both meshes.
            center=(before[0].min(0)+before[0].max(0))/2-np.array((0,0,1.15))
            before=(before[0]-center,*before[1:]);after=(after[0]-center,*after[1:])
            for vi,direction in enumerate(directions):
                for size in sizes:
                    a,parts=coverage.raster(before,direction,size,size);b,_=coverage.raster(after,direction,size,size)
                    holes,growth=coverage.new_holes(a,b);missing=coverage.erode(a>0,1)&(b==0)
                    for pi in np.unique(parts[holes]):
                        if pi:losses[before[-1][pi-1]]+=int(((parts==pi)&holes).sum())
                    row=dict(clip=sm['clips'][ci]['name'],fraction=f,view=vi,pixels=size,
                             new_holes=int(holes.sum()),core_loss=int(missing.sum()),
                             largest_new_hole=coverage.largest_region(holes),
                             gap_growth=int(growth.sum()),iou=float(((a>0)&(b>0)).sum()/max(1,((a>0)|(b>0)).sum())))
                    rows.append(row)
                    if holes.any():
                        np.savez_compressed(folder/f'gap-{ci}-{f}-{vi}-{size}.npz',before=a,after=b,holes=holes)
            print('COVERAGE',lod,ci,f,'max new holes',max(r['new_holes'] for r in rows[-20:]),flush=True)
        assert hashlib.sha256((folder/'gameplay-poses.npz').read_bytes()).hexdigest()==source_hash
        report=dict(lod=lod,samples=len(rows),full=full,pose_bank_sha256=source_hash,minimum_triangle_area_ratio=minimum_area_ratio,
                    maximum_new_hole_pixels=max(r['new_holes'] for r in rows),
                    largest_new_hole=max(r['largest_new_hole'] for r in rows),
                    minimum_silhouette_iou=min(r['iou'] for r in rows),source_parts_at_new_holes=dict(losses),views=rows)
        (folder/('coverage-full.json' if full else 'coverage-pilot.json')).write_text(json.dumps(report,indent=2)+'\n')
        print('COVERAGE RESULT',{k:v for k,v in report.items() if k!='views'},flush=True)

if __name__=='__main__':run('--full' in sys.argv)
