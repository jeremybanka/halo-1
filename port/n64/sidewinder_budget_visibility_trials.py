"""Rejected exploratory visibility-only trials; not used by the candidate renderer.\nThe adopted candidate is the regional near/far scene bank in sidewinder_budget.\n"""
from sidewinder_budget import *

def hull2(points):
    ps=sorted(set(tuple(p) for p in points))
    cross=lambda a,b,c:(b[0]-a[0])*(c[1]-a[1])-(b[1]-a[1])*(c[0]-a[0])
    lo=[];hi=[]
    for seq,out in ((ps,lo),(ps[::-1],hi)):
        for p in seq:
            while len(out)>=2 and cross(out[-2],out[-1],p)<=0:out.pop()
            out.append(p)
    return lo[:-1]+hi[:-1]


def area2(poly):return abs(sum(p[0]*q[1]-p[1]*q[0] for p,q in zip(poly,poly[1:]+poly[:1])))


def occluders():
    """Convex unions of exact coplanar opaque source faces, retaining openings."""
    rows=json.loads((OUT/'source.json').read_text())['rows'];planes=collections.defaultdict(list)
    for r in rows:
        if r['label'][0] not in ('structures','terrain'):continue
        a,b,c=(np.array(v[:3],dtype=np.int64) for v in r['triangle']);n=np.cross(b-a,c-a);g=math.gcd(*map(int,n))
        if not g:continue
        n=n//g;d=int(n@a);key=(*map(int,n),d);planes[key].append(r)
    output=[]
    for key,rs in planes.items():
        n=np.array(key[:3]);axes=[a for a in range(3) if a!=int(np.argmax(abs(n)))];xyz={tuple(v[a] for a in axes):v[:3] for r in rs for v in r['triangle']};polys=[hull2([tuple(v[a] for a in axes) for v in r['triangle']]) for r in rs];polys=[p for p in polys if len(p)>=3]
        # Merge only when the convex hull has exactly the combined area; no
        # openings, recesses or concave corners can be filled by this operation.
        again=True
        while again:
            again=False
            for i in range(len(polys)):
                for j in range(i+1,len(polys)):
                    if not set(polys[i])&set(polys[j]):continue
                    h=hull2(polys[i]+polys[j])
                    if len(h)<=8 and area2(h)==area2(polys[i])+area2(polys[j]):
                        polys[i]=h;polys.pop(j);again=True;break
                if again:break
        for poly in polys:
            ps=np.array([xyz[p] for p in poly],dtype=float)/256
            if np.linalg.norm(np.cross(ps[1]-ps[0],ps[2]-ps[0]))<.1:continue
            if area2(poly)/65536<.5:continue
            # Preserve original triangle orientation; shrink the planar polygon
            # geometrically at use time, and require a positive depth margin.
            if np.dot(np.cross(ps[1]-ps[0],ps[2]-ps[0]),n)<0:ps=ps[::-1]
            output.append(dict(points=ps.tolist(),normal=(n/np.linalg.norm(n)).tolist(),source_faces=len(rs),plane=list(key),area=area2(poly)/131072))
    output.sort(key=lambda p:p['area'],reverse=True)
    (OUT/'occluders.json').write_text(json.dumps(output,indent=2)+'\n')
    print('occluders',len(output),'largest',[(round(p['area'],2),len(p['points'])) for p in output[:20]])


def occlusion_test():
    payload=(BASE/'candidate-maps/sidewinder.map64').read_bytes();vis=json.loads((BASE/'visibility.json').read_text());chunks=list(struct.iter_unpack('>IHH6hHH',sections(payload)[1]));target=json.loads((OUT/'target.json').read_text());eye=np.array([float(target['pose'][k]) for k in ('eye_x','eye_y','eye_z')]);occ=json.loads((OUT/'occluders.json').read_text());volumes=[]
    for i,o in enumerate(occ):
        ps=np.array(o['points']);n=np.array(o['normal']);d=n@ps[0];distance=n@eye-d
        if abs(distance)<.1:continue
        # Both sides for diagnostic only; report which source orientation wins.
        n=n*(1 if distance<0 else -1);d=n@ps[0];centroid=ps.mean(0);planes=[(n,d+.03)]
        for p,q in zip(ps,np.roll(ps,-1,axis=0)):
            v=np.cross(q-eye,p-eye);v/=np.linalg.norm(v)
            if v@(centroid-eye)<0:v=-v
            # Ten millimeter edge inset avoids relying on shared-edge coverage.
            planes.append((v,v@eye+.01))
        volumes.append((i,planes,distance))
    kept=[];removed=[];contributors=collections.Counter()
    for b in target['chunks']:
        c=chunks[b];lo=np.array(c[3:6])/32;hi=np.array(c[6:9])/32
        # Full AABB must lie strictly within one certified opaque shadow.
        witness=next(((i,side) for i,planes,side in volumes if all(n@np.where(n>=0,lo,hi)>d for n,d in planes)),None)
        if witness:removed.append(b);contributors[witness]+=((c[1]+1)&~1)
        else:kept.append(b)
    print('old',target['vertices'],'new',sum((chunks[b][1]+1)&~1 for b in kept),'kept chunks',len(kept),'occluders',len(volumes))
    print('top contributors',contributors.most_common(15))
    (OUT/'target-occlusion-test.json').write_text(json.dumps(dict(kept=kept,removed=removed,vertices=sum((chunks[b][1]+1)&~1 for b in kept)),indent=2)+'\n')


def cell_visible(rows,lo,hi,occluders,near=1.30):
    # Every pyramid inequality is affine in the eye and in the target point.
    # Testing all eight camera-cell corners and all target AABB corners
    # therefore bounds their entire Cartesian product, not sampled positions.
    lo=np.array(lo);hi=np.array(hi);eyes=np.array([[hi[a] if bits>>a&1 else lo[a] for a in range(3)] for bits in range(8)])
    ps=np.array([[v[:3] for v in r['triangle']] for r in rows],dtype=float)/256;low=ps.min(1)-.004;high=ps.max(1)+.004;visible=np.ones(len(rows),dtype=bool);contributors=collections.Counter()
    for oi,o in enumerate(occluders):
        p=np.array(o['points']);n=np.array(o['normal']);d=n@p[0]
        # World-bank winding is inward-facing under CULL_FRONT. Only the
        # original front-facing side may occlude. Require scoped near-plane
        # clearance (1 world unit) for every eye in the whole cell.
        distances=eyes@n-d
        if distances.max()>-near:continue
        if np.min(np.linalg.norm(p-eyes.mean(0),axis=1))>120:continue
        # Shrink all edges by .04 units without moving the supporting plane.
        center=p.mean(0);radius=max(np.linalg.norm(p-center,axis=1));p=center+(p-center)*max(0,1-.08/max(radius,.001))
        keep=np.ones(len(rows),dtype=bool)
        # Target must be behind the solid face, beyond quantization margin.
        keep&=(np.where(n>=0,low,high)@n)>d+.015
        if not (keep&visible).any():continue
        for eye in eyes:
            for a,b in zip(p,np.roll(p,-1,axis=0)):
                normal=np.cross(b-eye,a-eye);length=np.linalg.norm(normal)
                if length<1e-9:keep[:]=False;break
                normal/=length
                if normal@(center-eye)<0:normal=-normal
                keep&=(np.where(normal>=0,low,high)@normal)>normal@eye+.005
            if not (keep&visible).any():break
        contributors[oi]+=int(np.count_nonzero(keep&visible));visible&=~keep
    return visible,contributors


def cell_trial():
    from photo_sidewinder_structures import load_bank,render
    from report_world_lod import subset
    from PIL import Image
    rows=json.loads((OUT/'source.json').read_text())['rows'];occ=json.loads((OUT/'occluders.json').read_text());eye=np.array([52.2788773,.792942643,-24.1915627])
    for radius in (.1,.25,.5,1.):
        lo=eye-[radius,.2,radius];hi=eye+[radius,.2,radius];keep,c=cell_visible(rows,lo,hi,occ);selected=[r for r,k in zip(rows,keep) if k]
        print('radius',radius,'visible all-direction triangles',len(selected),collections.Counter(r['label'][0] for r in selected),'occluders',c.most_common(8),flush=True)
        (OUT/f'cell-{radius}.json').write_text(json.dumps(dict(lo=lo.tolist(),hi=hi.tolist(),rows=selected,contributors=dict(c)),separators=(',',':'))+'\n')


def merged_occluders():
    from shapely.geometry import Polygon,MultiPoint
    from shapely.ops import unary_union,triangulate
    rows=json.loads((OUT/'source.json').read_text())['rows'];planes=collections.defaultdict(list)
    for r in rows:
        if r['label'][0] not in ('structures','terrain'):continue
        a,b,c=(np.array(v[:3],dtype=np.int64) for v in r['triangle']);n=np.cross(b-a,c-a);g=math.gcd(*map(int,n))
        if not g:continue
        n=n//g;d=int(n@a);key=(*map(int,n),d);planes[key].append(r)
    output=[]
    for key,rs in planes.items():
        n=np.array(key[:3]);drop=int(np.argmax(abs(n)));axes=[a for a in range(3) if a!=drop];polygons=[Polygon([[v[a]/256 for a in axes] for v in r['triangle']]) for r in rs];union=unary_union(polygons)
        pieces=[]
        for t in triangulate(union):
            # Delaunay fills holes unless explicitly filtered.
            if union.covers(t):pieces.append(t)
        changed=True
        while changed:
            changed=False
            for i in range(len(pieces)):
                for j in range(i+1,len(pieces)):
                    if not pieces[i].intersects(pieces[j]):continue
                    u=pieces[i].union(pieces[j]);h=u.convex_hull
                    if abs(h.area-u.area)<1e-9 and len(h.exterior.coords)<=9:
                        pieces[i]=h;pieces.pop(j);changed=True;break
                if changed:break
        for p in pieces:
            if p.area<.2:continue
            assert union.buffer(1e-10).covers(p)
            # Shrink the *merged* polygon; internal triangulation edges are
            # not apertures and no longer leave artificial occlusion cracks.
            p=p.buffer(-.035,join_style=2)
            if p.is_empty or p.geom_type!='Polygon':continue
            ps=[]
            for q in list(p.exterior.coords)[:-1]:
                xyz=np.zeros(3);xyz[axes]=q;xyz[drop]=(key[3]/256-n[axes]@q)/n[drop];ps.append(xyz)
            ps=np.array(ps)
            if np.dot(np.cross(ps[1]-ps[0],ps[2]-ps[0]),n)<0:ps=ps[::-1]
            output.append(dict(points=ps.tolist(),normal=(n/np.linalg.norm(n)).tolist(),source_faces=len(rs),plane=list(key),area=p.area,merged=True))
    output.sort(key=lambda p:p['area'],reverse=True);(OUT/'occluders.json').write_text(json.dumps(output,indent=2)+'\n');print('merged',len(output))


def cell_shadow_planes(lo,hi,near=.16):
    occ=json.loads((OUT/'occluders.json').read_text());lo=np.array(lo);hi=np.array(hi);eyes=np.array([[hi[a] if bits>>a&1 else lo[a] for a in range(3)] for bits in range(8)]);volumes=[]
    for oi,o in enumerate(occ):
        p=np.array(o['points']);n=np.array(o['normal']);d=n@p[0]
        if (eyes@n-d).max()>-near:continue
        if np.min(np.linalg.norm(p-eyes.mean(0),axis=1))>120:continue
        # Inset a planar convex polygon by intersecting its edge halfspaces.
        center=p.mean(0);plane=[np.r_[n,d+.02]]
        for eye in eyes:
            for a,b in zip(p,np.roll(p,-1,axis=0)):
                normal=np.cross(b-eye,a-eye);length=np.linalg.norm(normal)
                if length<1e-9:break
                normal/=length
                if normal@(center-eye)<0:normal=-normal
                plane.append(np.r_[normal,normal@eye+.012])
        volumes.append((oi,np.array(plane)))
    return volumes


def polygon_clip(poly,n,d,positive=True):
    result=[]
    for a,b in zip(poly,poly[1:]+poly[:1]):
        da=n@a-d;db=n@b-d
        if not positive:da=-da;db=-db
        if da>=0:result.append(a)
        if (da>=0)!=(db>=0):result.append(a+(b-a)*(da/(da-db)))
    return result


def union_visible(rows,lo,hi):
    from shapely.geometry import Polygon
    volumes=cell_shadow_planes(lo,hi);ps=np.array([[v[:3] for v in r['triangle']] for r in rows],dtype=float)/256;possible=[]
    for oi,planes in volumes:
        dist=ps@planes[:,:3].T-planes[:,3];eligible=(dist.max(1)>=0).all(1);possible.append((oi,planes,eligible))
    kept=[];fully_hidden=0;partial=0
    for ri,(r,p) in enumerate(zip(rows,ps)):
        covers=[];normal=np.cross(p[1]-p[0],p[2]-p[0]);drop=int(np.argmax(abs(normal)));axes=[a for a in range(3) if a!=drop];original=Polygon(p[:,axes]);done=False
        if original.area<1e-12:kept.append(r);continue
        for oi,planes,eligible in possible:
            if not eligible[ri]:continue
            if np.all(p@planes[:,:3].T>=planes[:,3]):done=True;break
            poly=list(p)
            for plane in planes:
                poly=polygon_clip(poly,plane[:3],plane[3])
                if len(poly)<3:break
            if len(poly)<3:continue
            q=Polygon(np.array(poly)[:,axes])
            if q.area>0:covers.append(q)
        if not done and covers:
            from shapely.ops import unary_union
            remaining=original.difference(unary_union(covers));done=remaining.area<1e-10
            if not done:partial+=1
        if done:fully_hidden+=1
        else:kept.append(r)
    print('union',len(rows),'->',len(kept),'fully hidden',fully_hidden,'partial',partial,'volumes',len(volumes),flush=True)
    return kept


def union_trial():
    rows=json.loads((OUT/'source.json').read_text())['rows'];eye=np.array([52.2788773,.792942643,-24.1915627]);lo=eye-[.25,.12,.25];hi=eye+[.25,.12,.25];kept=union_visible(rows,lo,hi)
    (OUT/'cell-union.json').write_text(json.dumps(dict(lo=lo.tolist(),hi=hi.tolist(),rows=kept),separators=(',',':'))+'\n')


def beam_trial(step=math.pi/12,cell=.5):
    from shapely.geometry import Polygon
    from shapely.ops import unary_union
    rows=json.loads((OUT/'source.json').read_text())['rows'];ps=np.array([[v[:3] for v in r['triangle']] for r in rows],dtype=float)/256
    t=json.loads((OUT/'target.json').read_text());eye=np.array([float(t['pose'][k]) for k in ('eye_x','eye_y','eye_z')]);matrix=np.array(t['matrix_columns']);f=matrix[:3,3];f/=np.linalg.norm(f);yaw=math.atan2(-f[2],f[0]);pitch=math.asin(f[1]);yb=math.floor(yaw/step);pb=math.floor(pitch/step);yc=(yb+.5)*step;pc=(pb+.5)*step
    direction=np.array([math.cos(pc)*math.cos(yc),math.sin(pc),-math.cos(pc)*math.sin(yc)]);right=np.cross(direction,[0,1,0]);right/=np.linalg.norm(right);up=np.cross(right,direction)
    # Diagonal field angle plus total possible yaw/pitch rotation and a
    # generous native clipping margin, expressed as an enclosing square cone.
    diag=math.atan(math.tan(1.08/2)*math.hypot(4/3,1));angle=diag+step+math.radians(3);slope=math.tan(angle)
    th=math.tan(1.08/2)*(4/3)*(1+8/160)+.03;tv=math.tan(1.08/2)*(1+8/120)+.03
    eps=2*math.sin(step/2)*math.sqrt(1+th*th+tv*tv);hs=(th+eps)/(1-eps);vs=(tv+eps)/(1-eps)
    lo=np.floor(eye/cell)*cell;hi=lo+cell;volumes=cell_shadow_planes(lo,hi);beam=[]
    for n in (direction,*[s*direction+sign*axis for axis,s in ((right,hs),(up,vs)) for sign in (-1,1)]):beam.append(np.r_[n,np.where(n>=0,lo,hi)@n-.005])
    potential=[]
    for oi,planes in volumes:
        dist=ps@planes[:,:3].T-planes[:,3];eligible=(dist.max(1)>=0).all(1);potential.append((oi,planes,eligible))
    kept=[];clipped=hidden=backface=0
    flags=list(sections((BASE/'candidate-maps/sidewinder.map64').read_bytes())[6]);eyes=np.array([[hi[a] if bits>>a&1 else lo[a] for a in range(3)] for bits in range(8)])
    for ri,(r,p) in enumerate(zip(rows,ps)):
        normal=np.cross(p[1]-p[0],p[2]-p[0]);drop=int(np.argmax(abs(normal)));axes=[a for a in range(3) if a!=drop]
        if not flags[r['material']]&4 and np.min((eyes-p[0])@normal)>.0001:backface+=1;continue
        poly=list(p)
        for plane in beam:
            poly=polygon_clip(poly,plane[:3],plane[3])
            if len(poly)<3:break
        if len(poly)<3:clipped+=1;continue
        original=Polygon(np.array(poly)[:,axes]);covers=[];done=False
        if original.area<1e-12:kept.append(r);continue
        for oi,planes,eligible in potential:
            if not eligible[ri]:continue
            if np.all(np.array(poly)@planes[:,:3].T>=planes[:,3]):done=True;break
            points=poly
            for plane in planes:
                points=polygon_clip(points,plane[:3],plane[3])
                if len(points)<3:break
            if len(points)>=3:
                q=Polygon(np.array(points)[:,axes])
                if q.area>0:covers.append(q)
        if not done and covers:done=original.difference(unary_union(covers)).area<1e-10
        if done:hidden+=1
        else:kept.append(r)
    print('beam rows',len(rows),'->',len(kept),'frustum',clipped,'occlusion',hidden,'backface',backface,'cell',lo,hi,'yaw/pitch',yb,pb,'angle',math.degrees(angle),collections.Counter(r['label'][0] for r in kept),flush=True)
    record=dict(lo=lo.tolist(),hi=hi.tolist(),yaw_bin=yb,pitch_bin=pb,step=step,cone_angle=angle,rows=kept,clip=clipped,hidden=hidden,backface=backface)
    (OUT/'beam-trial.json').write_text(json.dumps(record,separators=(',',':'))+'\n')
