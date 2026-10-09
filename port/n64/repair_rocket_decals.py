"""Keep Xbox rocket label planes above the quantized receiver/cartridge shell."""
import json
from pathlib import Path
import numpy as np

def repair(data):
    w=data['weapons']['rocket']
    if w.get('decal_separation'):return
    selected=[i for i,t in enumerate(w['triangles']) if w['material_names'][t['material']].endswith(' decal')]
    distance=1.5/256
    def offset(points):
        p=np.array(points);normal=np.cross(p[1]-p[0],p[2]-p[0]);length=np.linalg.norm(normal)
        if length<1e-10:raise ValueError('Degenerate source decal')
        return (p+normal/length*distance).tolist()
    for i in selected:
        w['triangles'][i]['p']=offset(w['triangles'][i]['p'])
        for clip in w['clips'].values():
            for f in clip['frames']:f[i*3:i*3+3]=offset(f[i*3:i*3+3])
    w['decal_separation']={'triangles':len(selected),'distance':distance,'reason':'Keep label planes distinct after 1/256 quantization; original rigid bone weights retained.'}
if __name__=='__main__':
    p=Path('build/n64/assets/firstperson-reduced.json');data=json.loads(p.read_text());repair(data);p.write_text(json.dumps(data))
