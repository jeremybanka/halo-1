"""Measure fitted backing against retained ODST plate fronts, separately from coverage.

Four source-key poses and three directions per region; this is a sampled depth
audit, not a proof of clearance throughout every animation or between keys.
"""
import argparse,json,math
from pathlib import Path
import numpy as np
from audit_jorge_armor_clearance import depth
from pack_assets import position

def run(folder,output):
    data=json.loads((folder/'solid.json').read_text());rows=[]
    groups=[('chest',lambda n:n.startswith('chest-'),['local-torso-lining'],1),
            ('left forearm',lambda n:n=='body-24:002',['local-sleeve-l'],1),
            ('right forearm',lambda n:n=='body-24:000',['local-sleeve-r'],1),
            ('pack',lambda n:n in ('gear-02:003','gear-02:004','gear-02:005'),['local-pack-lining'],-1)]
    for lod,model in enumerate(data['lods']):
        triangles=model['triangles'];names=np.array([t['component'] for t in triangles])
        rest=np.array([position(p,(0,0,0)) for t in triangles for p in t['p']]);faces=np.arange(len(rest)).reshape(-1,3)
        arrays=np.load(folder/f'poses-{lod}.npz')
        for region,select,backing,sign in groups:
            armor=faces[[select(n) for n in names]];under=faces[np.isin(names,backing)]
            if region=='chest':
                under=faces[[t['component']=='body-23:002' or t.get('source_component')=='body-23:002' for t in triangles]]
                bones={i for i,n in enumerate(data['nodes']) if n['name'] in ('bip01 spine','bip01 spine1')}
                allowed=[]
                for f in under:
                    influences={}
                    for ws in triangles[f[0]//3]['weights']:
                        for b,w in ws:influences[b]=influences.get(b,0)+w
                    if max(influences,key=influences.get) in bones:allowed.append(f)
                under=np.array(allowed)
            assert len(armor) and len(under),(lod,region)
            points=rest[armor];center=(points.min((0,1))+points.max((0,1)))/2
            ids=np.unique(armor);basis=np.c_[rest[ids],np.ones(len(ids))]
            normals=np.cross(points[:,1]-points[:,0],points[:,2]-points[:,0])
            front=(sign*normals[:,0]>.2*np.linalg.norm(normals,axis=1))&(sign*(points[:,:,0].mean(1)-center[0])>=0)
            # Report the oblique joint returns too, but distinguish them from
            # the broad plate front. Sleeve/hand overlap at a cuff is expected.
            broad=front&(sign*normals[:,0]>(.65 if 'forearm' in region else .2)*np.linalg.norm(normals,axis=1))
            broad_armor=armor[broad];armor=armor[front]
            assert len(armor),(lod,region,'missing outward original plate')
            scale=max(np.ptp(points[:,:,1]),np.ptp(points[:,:,2]))*1.3
            for name,fraction in [('idle',0),('run',.4),('melee',.4),('passenger',.5)]:
                ci=next(i for i,c in enumerate(model['animations']) if c['name']==name)
                frames=arrays['frames_'+str(ci)];posed=np.rint(frames[round(fraction*(len(frames)-1))]*512)/512
                transform=np.linalg.lstsq(basis,posed[ids],rcond=None)[0]
                local=(posed-transform[3])@np.linalg.inv(transform[:3])
                for angle in (-35,0,35):
                    theta=math.radians(angle);direction=(sign*math.cos(theta),0,math.sin(theta))
                    plate=depth(local,armor,center,scale,direction)
                    lining=depth(local,under,center,scale,direction)
                    broad_depth=depth(local,broad_armor,center,scale,direction)
                    broad_covered=np.isfinite(broad_depth)&(lining>broad_depth+1/512)
                    visible=np.isfinite(plate);covered=visible&(lining>plate+1/512)
                    interior=visible.copy()
                    for axis in (0,1):
                        for step in (-1,1):interior&=np.roll(visible,step,axis)
                    rows.append(dict(lod=lod,region=region,pose=name,angle=angle,
                        plate_pixels=int(visible.sum()),backing_in_front_pixels=int(covered.sum()),
                        interior_backing_in_front_pixels=int((covered&interior).sum()),
                        broad_front_backing_in_front_pixels=int(broad_covered.sum()),
                        backing_in_front_fraction=float(covered.sum()/max(1,visible.sum()))))
    output.write_text(json.dumps(rows,indent=2)+'\n')
    for region,_,_,_ in groups:
        r=[v for v in rows if v['region']==region]
        print(region,'maximum backing in front',max(v['backing_in_front_fraction'] for v in r),
            'maximum broad-front pixels',max(v['broad_front_backing_in_front_pixels'] for v in r))
    assert not any(r['broad_front_backing_in_front_pixels'] for r in rows),'Backing crosses a broad original plate front'

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('folder',type=Path);p.add_argument('output',type=Path)
    a=p.parse_args();run(a.folder,a.output)
