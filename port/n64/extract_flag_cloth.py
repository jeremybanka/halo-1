"""Extract the original cloth physics and per-map wind into the private bank."""
import argparse,contextlib,hashlib,json,math,random,re,struct
from pathlib import Path
from asset_ids import map_ids
from extract_extended import tag_values
ROOT=Path(__file__).resolve().parents[2]

def extract(source_root,output):
    from reclaimer.meta.wrappers.halo1_map import Halo1Map
    inputs={};maps={};physics=None
    with output.with_suffix('.log').open('w') as log,contextlib.redirect_stdout(log),contextlib.redirect_stderr(log):
        for name,id in map_ids().items():
            cache=source_root/'build/n64-map-survey'/f'{name}-decompressed.map'
            if name=='bloodgulch':cache=source_root/'build/n64/assets/bloodgulch-decompressed.map'
            inputs[name]=hashlib.sha256(cache.read_bytes()).hexdigest()
            h=Halo1Map();h.load_map(cache);es=h.tag_index.tag_index
            def meta(path,kind):return h.get_meta(next(i for i,e in enumerate(es) if e.path==path and e.class_1.enum_name==kind))
            if physics is None:physics=tag_values(meta(r'weapons\flag\flag cloth','point_physics'))
            bsp=h.get_meta(next(i for i,e in enumerate(es) if e.class_1.enum_name=='scenario_structure_bsp'))
            palettes=tag_values(bsp.weather_palettes);clusters=[int(c.weather) for c in bsp.clusters.STEPTREE]
            used={i for i in clusters if i>=0 and palettes[i].get('wind') and palettes[i]['wind_magnitude']>0}
            assert len(used)<=1,(name,'multiple active weather definitions require an extended selector')
            nodes=[];root=-1;params=dict(speed=[0,0],yaw=0,pitch=0,variation=[0,0],magnitude=0,local_weight=0,local_rate=0)
            if used:
                palette_id=next(iter(used));p=palettes[palette_id];w=tag_values(meta(p['wind'],'wind'))
                direction=[p['wind_direction'][a] for a in ('i','j','k')]
                params=dict(speed=[w['velocity']['from'],w['velocity']['to']],yaw=math.atan2(direction[1],direction[0]),
                    pitch=math.atan2(direction[2],math.hypot(*direction[:2])),variation=[w['variation_area']['y'],w['variation_area']['p']],
                    magnitude=p['wind_magnitude'],local_weight=w['local_variation_weight'],local_rate=w['local_variation_rate'])
                collision=bsp.collision_bsp.STEPTREE[0]
                raw_nodes=list(struct.iter_unpack('<3i',bytes(collision.bsp3d_nodes.STEPTREE)))
                planes=list(struct.iter_unpack('<4f',bytes(collision.planes.STEPTREE)))
                leaves=list(struct.iter_unpack('<6BHhhi',bytes(bsp.leaves.STEPTREE)))
                bank=(ROOT/'halo64-assets/generated/maps'/f'{name}.map64').read_bytes()
                origin=struct.unpack_from('>3f',bank,struct.unpack_from('>I',bank,16+21*12)[0])
                memo={}
                def prune(i):
                    if i==-1:return None  # Solid/unknown; no valid weather leaf to preserve.
                    if i<0:
                        cluster=leaves[i&0x7fffffff][-3]
                        return None if cluster<0 else (-2 if clusters[cluster]==palette_id else -1)
                    if i in memo:return memo[i]
                    plane,back,front=raw_nodes[i];b,f=prune(back),prune(front)
                    if b is None:value=f
                    elif f is None or b==f:value=b
                    else:
                        nx,ny,nz,d=planes[plane]
                        converted=[nx,nz,-ny,d-sum(a*b for a,b in zip((nx,ny,nz),origin))]
                        value=len(nodes);nodes.append({'plane':converted,'back':b,'front':f})
                    memo[i]=value;return value
                root=prune(0)
                if root is None:root=-1
                # Independent point queries through the full collision BSP
                # verify pruning and the source -> renderer plane conversion.
                vertices=list(struct.iter_unpack('<3fi',bytes(collision.vertices.STEPTREE)))
                lo=[min(v[a] for v in vertices) for a in range(3)];hi=[max(v[a] for v in vertices) for a in range(3)]
                rng=random.Random(0x464c4147);checked=0;states=set()
                for sample in range(30000):
                    point=[rng.uniform(lo[a],hi[a]) for a in range(3)];i=0
                    while i>=0:
                        plane,back,front=raw_nodes[i];n=planes[plane]
                        i=front if sum(n[a]*point[a] for a in range(3))>=n[3] else back
                    if i==-1:continue
                    cluster=leaves[i&0x7fffffff][-3]
                    if cluster<0:continue
                    expected=clusters[cluster]==palette_id
                    converted=[point[0]-origin[0],point[2]-origin[2],-point[1]+origin[1]];i=root
                    while i>=0:
                        n=nodes[i];i=n['front'] if sum(n['plane'][a]*converted[a] for a in range(3))>=n['plane'][3] else n['back']
                    assert (i==-2)==expected,(name,point,cluster)
                    checked+=1;states.add(expected)
                assert checked>0
                if -1 in clusters:assert states=={False,True},(name,'missing sheltered coverage')
                params['selector_validation']=dict(valid_queries=checked,wind_states=sorted(states))
            maps[name]=dict(id=id,**params,nodes=nodes,root=root,source_palettes=palettes,cluster_weather=clusters)
    original=(ROOT/'source/physics/physics.c').read_text()
    gravity=float(re.search(r'real global_gravity = ([0-9.e-]+)f;',original)[1])*900
    air_density=float(re.search(r'real global_air_density = ([0-9.e-]+)f;',original)[1])
    flags=physics['flags'];assert not any(flags.values()),'Unsupported cloth physics flags'
    cloth=json.loads((output.parent/'objective-details.json').read_text())['cloth']
    assert cloth['wind_noise']==0 and cloth['width']==16 and cloth['height']==13
    # Source wind uses three cyclic, cubic-smoothed tables. The port has its
    # own deterministic seed instead of consuming the original game RNG.
    rng=random.Random(0x464c4147);control=[]
    for axis in range(3):
        points=[]
        for i in range(8):
            v=[rng.uniform(-1,1) for _ in range(3)];length=math.sqrt(sum(x*x for x in v));points.append([x/length for x in v])
        control.append(points)
    noise=[]
    for axis in range(3):
        samples=[]
        for i in range(64):
            j,t=divmod(i,8);t/=8;f=[control[axis][(j+k)&7] for k in (-1,0,1,2)]
            # Literal divided-difference interpolation from real_math.h.
            value=[]
            for a in range(3):
                d1=f[1][a]-f[0][a];d2=f[2][a]-f[1][a];d3=f[3][a]-f[2][a]
                d3-=d2;d2-=d1
                value.append(f[0][a]+(t+1)*(d1+t*(d2+(t-1)*(d3-d2)/3)/2))
            samples.append([value[0],value[2],-value[1]])
        noise.append(samples)
    result=dict(schema=1,source_physics=physics,physics=dict(width=(cloth['width']-1)*cloth['cell_width'],height=(cloth['height']-1)*cloth['cell_height'],
        gravity=gravity*physics['air_gravity_scale'],drag=physics['air_friction']/((physics['scaled_density']+air_density*118613.34)*.02)),maps=maps,noise=noise,
        source_cache_sha256=inputs,source_files={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in
        [Path(__file__),ROOT/'source/objects/widgets/flags.c',ROOT/'source/physics/point_physics.c',ROOT/'source/physics/physics.c',ROOT/'source/scenario/wind.c']},
        adaptations=['6x5 grid samples every third authored point.','Private deterministic wind random stream/table; no gameplay RNG changes.','Solid/outside weather branches inherit adjacent valid weather; valid cluster weather remains exact.','Air-only cosmetic solver; no full Xbox render shader.'])
    output.write_text(json.dumps(result,indent=2)+'\n')
    print('Cloth physics',result['physics']);print('Weather selector nodes',{n:len(m['nodes']) for n,m in maps.items()})
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source-root',type=Path,required=True)
    p.add_argument('--output',type=Path,default=ROOT/'halo64-assets/assets/objectives/cloth-config.json')
    a=p.parse_args();extract(a.source_root,a.output)
