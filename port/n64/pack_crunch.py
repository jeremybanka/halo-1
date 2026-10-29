"""Prepare the third Covenant tier with compact material palettes and clip bounds."""
import argparse,copy,gzip,json
from pathlib import Path
import numpy as np
from pack_assets import position
NAMES=('grunt','elite','jackal','hunter')
def bounds_source(data):
    from pack_pve import CLIPS
    rows=[]
    for name in NAMES:
        clips=[]
        for key in CLIPS:
            points=np.concatenate([np.rint(np.array([position(p,(0,0,0)) for frame in m['clips'][key]['frames'] for p in frame])*128)/128 for m in data[name]])
            lo=points.min(axis=0);hi=points.max(axis=0)
            fmt=lambda a:'{'+','.join(float(x).hex()+'f' for x in a)+'}'
            clips.append('{'+fmt(lo)+','+fmt(hi)+'}')
        rows.append('{'+','.join(clips)+'}')
    return ['const bg_bounds bg_pve_crunch_bounds[BG_PVE_KINDS][PVE_CLIPS]={'+','.join(rows)+'};']
def palette(model):
    # Source material regions never merge. Four representative colors retain
    # dark recesses and bright armor; fine baked gradients become chunky ramps.
    groups={}
    for t in model['triangles']:
        for rgb in t['colors']:groups.setdefault(t['material'],[]).append(rgb)
    palettes={}
    for mi,colors in groups.items():
        x=np.asarray(colors,dtype=float);order=np.argsort(x@np.array([.2126,.7152,.0722]));k=min(4,len(x))
        centers=x[order[np.linspace(0,len(x)-1,k).astype(int)]].copy()
        for _ in range(16):
            labels=np.argmin(((x[:,None,:]-centers[None,:,:])**2).sum(axis=2),axis=1)
            next_centers=np.array([x[labels==i].mean(axis=0) if np.any(labels==i) else centers[i] for i in range(k)])
            if np.allclose(next_centers,centers):break
            centers=next_centers
        palettes[mi]=np.rint(centers).clip(0,255).astype(int)
    for t in model['triangles']:
        p=palettes[t['material']];t['colors']=[p[np.argmin(((p-np.array(rgb))**2).sum(axis=1))].tolist() for rgb in t['colors']]
        t['tints']=[255 if v>=128 else 0 for v in t['tints']]
    model['crunch_palette']=True
    return {str(k):v.tolist() for k,v in palettes.items()}
def main():
    p=argparse.ArgumentParser();p.add_argument('capture',type=Path);a=p.parse_args();out=a.capture
    base=json.loads(gzip.decompress(Path('halo64-assets/assets/covenant-model-appraisal/source/squad-baked.json.gz').read_bytes()))
    reduced=json.loads(gzip.decompress((out/'reduced-baked.json.gz').read_bytes()));report={}
    for name in NAMES:
        micro=copy.deepcopy(reduced[name][2]);report[name]=palette(micro);base[name].append(micro)
    base['spirit'].append(copy.deepcopy(base['spirit'][1]))
    source=out/'source';source.mkdir(exist_ok=True)
    (source/'squad-baked.json.gz').write_bytes(gzip.compress(json.dumps(base,separators=(',',':')).encode(),mtime=0))
    (source/'squad-source.json').write_bytes((out/'reduced-source.json').read_bytes())
    (out/'palettes.json').write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
