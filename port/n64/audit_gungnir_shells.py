"""Independent front-side rear-shell and codpiece-contour regression evidence."""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw
from audit_models import Mesh, engine, matching_bounds
from demake_raster import Raster


def run(source, inventory, parent, candidate, output):
    output.mkdir(parents=True, exist_ok=True)
    original=json.loads(source.read_text());parts=json.loads(inventory.read_text())
    before=json.loads((parent/'solid.json').read_text());after=json.loads((candidate/'solid.json').read_text())
    ids=next(p['faces'] for p in parts if p['id']=='body-06:005')
    ps=np.array(original['vertices'])[np.array(original['faces'])[ids]]
    n=np.cross(ps[:,1]-ps[:,0],ps[:,2]-ps[:,0]);rear=ps[ps[:,:,0].mean(1)<-.04]
    src=Mesh(engine(rear.reshape(-1,3)).reshape(-1,3,3),rgb=np.full(rear.shape,180))
    belt_ids=next(p['faces'] for p in parts if p['id']=='body-06:025')
    lowest=float(np.array(original['vertices'])[np.array(original['faces'])[belt_ids]][:,:,2].min())
    raster=Raster(output);rows=[];contours=[]
    for lod in range(2):
        models=[]
        for data in (before,after):
            ts=[t for t in data['lods'][lod]['triangles'] if t['component'].startswith('torso-back')]
            points=engine(np.array([t['p'] for t in ts]).reshape(-1,3)).reshape(-1,3,3)
            models.append(Mesh(points,rgb=np.full(points.shape,180)))
        belt=np.array([t['p'] for t in after['lods'][lod]['triangles'] if t['component']=='belt'])
        old_belt=np.array([t['p'] for t in before['lods'][lod]['triangles'] if t['component']=='belt'])
        contours.append(dict(lod=lod,source_lowest_halo_units=lowest,before_lowest_halo_units=float(old_belt[:,:,2].min()),after_lowest_halo_units=float(belt[:,:,2].min())))
        assert float(belt[:,:,2].min())<=lowest+.003,'Codpiece lower contour was lost again'
        for angle,direction in [('front',(1,.02,0)),('front-left',(1,.02,-.5)),('front-right',(1,.02,.5))]:
            bounds=matching_bounds([src,*models],direction)
            masks=[];sheet=Image.new('RGB',(600,220),'#202428');draw=ImageDraw.Draw(sheet)
            for col,(mesh,label) in enumerate(zip([src,*models],('Intact source rear frame','Before / front-facing','After / front-facing'))):
                im,ids,_=raster.render(mesh,bounds,direction,width=200,height=200)
                sheet.paste(im,(200*col,20));draw.text((200*col+3,4),label,fill='white');masks.append(ids>=0)
            reference=masks[0].copy()
            for dy,dx in ((0,1),(0,-1),(1,0),(-1,0)):reference&=np.roll(masks[0],(dy,dx),(0,1))
            count=int(reference.sum());assert count
            old=int((masks[1]&reference).sum());new=int((masks[2]&reference).sum())
            rows.append(dict(lod=lod,angle=angle,source_interior_pixels=count,before_covered_pixels=old,after_covered_pixels=new,coverage_fraction=new/count))
            assert new>old,'Rear frame front-side coverage did not improve'
            assert new/count>=.90,'Rear frame lost a broad inward surface'
            sheet.save(output/f'{lod}-{angle}.png')
        # All retained exterior armor and the approved helmet are unchanged.
        unaffected=lambda d:[t for t in d['lods'][lod]['triangles'] if not t['component'].startswith(('garment-','torso-back')) and t['component']!='belt']
        # Recessing backing appends provenance only; compare actual armor data.
        def geometry(ts):return [(t['component'],t['p'],t['uv'],t['weights'],t['material']) for t in ts]
        assert geometry(unaffected(before))==geometry(unaffected(after))
    result=dict(schema=1,passed=True,candidate_sha256=hashlib.sha256((candidate/'solid.json').read_bytes()).hexdigest(),parent_sha256=hashlib.sha256((parent/'solid.json').read_bytes()).hexdigest(),source_sha256=hashlib.sha256(source.read_bytes()).hexdigest(),method='Front-face culled isolated rear frame, three views per LOD, one-pixel source rim excluded; actual exterior armor geometry unchanged; source lower codpiece extremum retained',views=rows,codpiece_contours=contours)
    (output/'shell-validation.json').write_text(json.dumps(result,indent=2)+'\n')
    print('SHELLS',rows,contours,flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser()
    for name in ('source','inventory','parent','candidate','output'):p.add_argument(name,type=Path)
    a=p.parse_args();run(a.source,a.inventory,a.parent,a.candidate,a.output)
