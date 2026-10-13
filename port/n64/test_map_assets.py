"""Map bank/provenance and accepted-map immutability contracts."""
import hashlib,json,struct,subprocess
from pathlib import Path
from asset_ids import map_ids
ROOT=Path(__file__).resolve().parents[2];directory=ROOT/'halo64-assets/generated/maps'
r=json.loads((directory/'maps-report.json').read_text())
for name,want in r['inputs'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==want,name
for name,want in r['files'].items():assert hashlib.sha256((directory/name).read_bytes()).hexdigest()==want,name
asset_reference=subprocess.check_output(['git','ls-tree','d240145d','halo64-assets'],cwd=ROOT,text=True).split()[2]
old=json.loads(subprocess.check_output(['git','-C',str(ROOT/'halo64-assets'),'show',asset_reference+':generated/maps/maps-report.json'],text=True))
for name in ('bloodgulch','wizard','hangemhigh','chillout','beavercreek'):
    for suffix in ('.map64','-world.bin'):
        assert r['files'][name+suffix]==old['files'][name+suffix],name
for name,ident in map_ids().items():
    data=(directory/(name+'.map64')).read_bytes();magic,version,id,length=struct.unpack_from('>4I',data)
    assert magic==0x484d3634 and version==1 and id==ident and length==len(data)
    sections=[struct.unpack_from('>3I',data,16+i*12) for i in range(23)]
    for offset,count,stride in sections:assert offset%16==0 and offset+count*stride<=len(data)
    textures=sections[3];flags=sections[6];assert textures[1]<=32 and sections[1][1]<=512
    modes=data[flags[0]:flags[0]+flags[1]];assert all(v<=7 and v&3!=3 for v in modes)
    if name not in ('bloodgulch','wizard'):
        info=r['maps'][name];assert sum(x['triangles'] for x in info['scenery'])==info['scenery_triangles']
        assert all(x['triangles']<=x['source_triangles'] for x in info['scenery'])
        limit=.075 if name in ('hangemhigh','chillout','beavercreek') else .2
        for correction in info['spawn_clearance_offsets']:assert sum(v*v for v in correction['delta'])<limit**2
        assert info['eligible_slayer_spawns']>=4 and info['vehicles']==(8 if name=='sidewinder' else 0)
        for chunk in struct.iter_unpack('>IHH6hHH',data[sections[1][0]:sections[1][0]+sections[1][1]*24]):
            assert chunk[1]<=60 and chunk[-1]<=120 and chunk[-1]%3==0
assert [r['maps'][n]['render_triangles'] for n in ('hangemhigh','chillout','beavercreek')]==[3218,3108,3317]
assert [r['maps'][n]['items'] for n in ('hangemhigh','chillout','beavercreek')]==[43,32,30]
remaining=('sidewinder','damnation','ratrace','prisoner','carousel','boardingaction','putput','longest')
assert [r['maps'][n]['render_triangles'] for n in remaining]==[10036,8618,2692,5234,2940,7142,10494,2319]
assert [r['maps'][n]['eligible_slayer_spawns'] for n in remaining]==[16,30,48,24,27,16,27,28]
assert [r['maps'][n]['items'] for n in remaining]==[47,40,26,29,30,50,40,26]
assert [r['maps'][n]['teleporters'] for n in remaining]==[4,2,4,0,4,8,30,0]
models=json.loads((directory/'scenery-reduced.json').read_text())['models']
for model in models.values():
    assert len(model['retained_source_faces'])==len(model['faces'])==len(model['materials'])
    assert model['retained_source_faces']==sorted(set(model['retained_source_faces']))
    assert all(0<=i<model['source_triangles'] for i in model['retained_source_faces'])
print('PASS: all thirteen bank IDs/ranges, 60-vertex/120-index budgets, source architecture, authored rules, retained scenery cards and five immutable accepted banks')
