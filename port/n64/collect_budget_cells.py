"""Collect completed native logs and bind the broader Sidewinder appraisal."""
import collections,csv,hashlib,json,re,shutil
from pathlib import Path
from sidewinder_budget_cells import ROOT,OUT,BASE,validate,sections,signature,decode

PHASES=['sim','camera','animation','matrix','world','objects','firstperson','hud','audio','wait',
        'geometry_rsp_wait','geometry_rdp_wait','queue_stall','hull','pose','pill','player_geometry',
        'body_prepare','vehicle_prepare','pickup_prepare','view_prepare','players','physics','shots',
        'ground','features','tests','sweeps','pairs','suspend','world_camera','hull_camera','aim_camera',
        'force','integrate','control','publish','step','player_hit','sky','decode','scatter','writeback',
        'sample','pose_lerp','dma','meshes','poses','poll_samples','dp_busy_polls','sp_halted_polls',
        'repeat_last','repeat_frame']

def timings():
    results={};records=[]
    for mode in ('one','four'):
        pair=[]
        for variant in ('baseline','candidate'):
            path=OUT/f'{mode}-{variant}.log';text=path.read_text();groups={}
            for line in text.splitlines():
                if 'BENCH vi_fresh group=' not in line:continue
                group=re.search(r'group=(\w+)',line)[1];values={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)}
                if group in groups:assert groups[group]==values
                groups[group]=values
            assert set(groups)=={'ALL','EARLY','LATE'}
            r=dict(workload=mode,label=variant,groups=groups,initial_free_bytes=int(re.search(r'RAM=8388608 free=(\d+)',text)[1]),source_log=path.name)
            r['fps']=groups['ALL']['frames']*1e6/groups['ALL']['elapsed_us'];pair.append(r);records.append(r)
        a,b=pair;results[mode]=dict(baseline_fps=a['fps'],candidate_fps=b['fps'],gain_percent=100*(b['fps']/a['fps']-1),baseline_p95_ms=a['groups']['ALL']['p95_us']/1000,candidate_p95_ms=b['groups']['ALL']['p95_us']/1000,baseline_max_ms=a['groups']['ALL']['max_us']/1000,candidate_max_ms=b['groups']['ALL']['max_us']/1000,initial_additional_ram_bytes=a['initial_free_bytes']-b['initial_free_bytes'],scope='Fresh quiet native Ares pair; NTSC, 8 MiB, release LTO, three surfaces, 32 KiB queues, one-second warmup and 75-second fresh-pose sample. Instrumented CPU and serialized pipeline runs are separate.')
    (OUT/'timing-records.json').write_text(json.dumps(records,indent=2)+'\n');(OUT/'timing.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))

def profiles():
    assert len(PHASES)==53
    runs={}
    for label in ('cpu-baseline','cpu-candidate','pipeline-baseline','pipeline-candidate','pipeline-empty'):
        groups={}
        for line in (OUT/(label+'.log')).read_text().splitlines():
            match=re.search(r'BENCH attribution group=(\d+) frames=(\d+) elapsed_us=(\d+) phases=([\d,]+)',line)
            if not match:continue
            g,frames,elapsed,values=match.groups();values=list(map(int,values.split(',')));assert len(values)==53
            groups[('ALL','EARLY','LATE')[int(g)]]=dict(frames=int(frames),elapsed_us=int(elapsed),mean_phase_us=dict(zip(PHASES[:46],values[:46])),mean_counters=dict(zip(PHASES[46:],values[46:])),dp_busy_poll_percent=100*values[49]/values[48] if values[48] else None,sp_halted_poll_percent=100*values[50]/values[48] if values[48] else None)
        assert len(groups)==3,label;runs[label]=dict(source_log=label+'.log',groups=groups)
    data=dict(method='Fresh native means per rendered frame, inclusive. CPU mode retains normal pipelining. Pipeline mode deliberately serializes remaining RSP/RDP work before HUD. Empty-scissor mode suppresses 3D coverage while retaining geometry commands. Same NTSC/8 MiB/replay/75-second setup. These are not the quiet release FPS runs.',runs=runs,limits=['Queue/audio/world intervals overlap and cannot be summed as exclusive phases.','Faster/slower rendered frames accumulate different counts of fixed simulation ticks.','RSP fence wait is remaining work after CPU submission, including RDP backpressure and audio servicing; it is not total RSP execution time.','RDP drain after the RSP fence is only residual RDP work; a small value does not imply a free RDP.','DP busy percentages are conditional polling observations, not total hardware utilization.'])
    (OUT/'profiling.json').write_text(json.dumps(data,indent=2)+'\n');print('Collected five native attribution runs')

def native_images():
    import numpy as np
    from PIL import Image
    records=[]
    repeat_a=np.array(Image.open(OUT/'native-target600-before.png').convert('RGB'));repeat_b=np.array(Image.open(OUT/'native-target600-repeat.png').convert('RGB'));repeat=int(np.count_nonzero(np.any(repeat_a!=repeat_b,axis=2)));assert repeat==0
    for key,label in [('target600','Native tick 600 / full four-camera frame'),('target1950','Native tick 1950 / full four-camera frame'),('photo14','Native photo 14 / EAST BEND'),('photo20','Native photo 20 / WEST BASE ROOF')]:
        a=np.array(Image.open(OUT/f'native-{key}-before.png').convert('RGB'));b=np.array(Image.open(OUT/f'native-{key}-after.png').convert('RGB'));assert a.shape==b.shape==(240,640,3)
        diff=np.abs(a.astype(np.int16)-b.astype(np.int16));Image.fromarray(np.clip(diff*6,0,255).astype(np.uint8)).save(OUT/f'native-{key}-difference.png')
        record=dict(label=label,prefix='native-'+key,shape=list(a.shape),changed_pixels=int(np.count_nonzero(diff.max(2))),mean_rgb_error=float(diff.mean()),baseline_repeat_changed_pixels=repeat)
        if key.startswith('photo'):
            record['debug_overlay_changed_pixels']=int(np.count_nonzero(diff[194:].max(2)));assert record['debug_overlay_changed_pixels']==0
            lines=[]
            for variant in ('before','after'):
                text=(OUT/f'{key}-{variant}.log').read_text();pose=re.findall(r'PHOTO \d+ tick=.*',text);assert pose;lines.append(pose)
            assert lines[0]==lines[1];record['native_full_precision_pose_match']=True;record['pose_log']=lines[0]
        else:
            record['per_camera_changed_pixels']=[int(np.count_nonzero(diff[(p//2)*120:(p//2+1)*120,(p%2)*320:(p%2+1)*320].max(2))) for p in range(4)]
        records.append(record)
        if key=='target600':
            y,x=120,0
            for variant in ('before','after','difference'):
                im=Image.open(OUT/f'native-{key}-{variant}.png');im.crop((x,y,x+320,y+120)).save(OUT/f'native-{key}-p2-{variant}.png')
            records.append(dict(label='Native tick 600 / worst outdoor camera P2',prefix='native-target600-p2',changed_pixels=record['per_camera_changed_pixels'][2],scope='Camera-2 crop of the same raw full frame.'))
    (OUT/'native-images.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(records,indent=2))

def native_cell_controls():
    import numpy as np
    from PIL import Image
    records=[]
    for tick in (600,1950):
        a=np.array(Image.open(OUT/f'native-target{tick}-after.png').convert('RGB'));b=np.array(Image.open(OUT/f'native-cell-control{tick}.png').convert('RGB'));assert a.shape==b.shape==(240,640,3)
        diff=np.abs(a.astype(np.int16)-b.astype(np.int16));count=int(np.count_nonzero(diff.max(2)))
        Image.fromarray(np.clip(diff*6,0,255).astype(np.uint8)).save(OUT/f'native-cell-control{tick}-difference.png')
        records.append(dict(tick=tick,changed_pixels=count,mean_rgb_error=float(diff.mean()),cameras=4,scope='Same candidate bank, LOD and batching; control makes every cell mask fail open. Raw native 640x240 scanout.'))
        assert count==0,(tick,count)
    (OUT/'native-cell-controls.json').write_text(json.dumps(records,indent=2)+'\n');print(json.dumps(records,indent=2))

def final_validation():
    bank=(OUT/'candidate-maps/sidewinder.map64').read_bytes();data=json.loads((OUT/'visibility.json').read_text());validate(data,bank)
    canonical=ROOT/'halo64-assets/generated/maps/sidewinder.map64';assert hashlib.sha256(canonical.read_bytes()).hexdigest()=='200a3e01cd0c29a4f3f6f2ab71a1737c81342d2d3950bf763e3e9417606f7948'
    photos=json.loads((OUT/'photos-images.json').read_text());replay=json.loads((OUT/'replay-images.json').read_text());extra=json.loads((OUT/'extra-images.json').read_text());assert len(photos)==24 and len(replay)==68 and len(extra)==56
    assert all(r['cell_control_changed_pixels']==0 for r in photos+replay+extra)
    assert all(r['pvs_control_changed_pixels']==0 for r in photos+replay)
    import numpy as np
    scenery=json.loads((OUT/'scenery-authored.json').read_text());support=[]
    for g in scenery:
        if g['omitted_subpixel'] or len(g['far'])>=len(g['rows'])*.85:continue
        original=np.array(list(dict.fromkeys(tuple(v[:3]) for r in g['rows'] for v in r['triangle'])))
        pins=set()
        for a in (-1,0,1):
          for b in (-1,0,1):
           for c in (-1,0,1):
            if a or b or c:pins.add(tuple(original[int(np.argmax(original@np.array([a,b,c])))]))
        actual={tuple(v[:3]) for r in g['far'] for v in r['triangle']};assert pins<=actual,(g['id'],'support vertex missing')
        pp=np.array(list(actual))/256
        # The source AABB is the near-exclusion reference, not a proxy
        # frustum bound. Collapse can bulge slightly beyond it. Both meshes
        # must fit the original sphere used for the screen-size decision;
        # each packed draw batch has its own actual geometry AABB.
        outside=np.maximum(np.maximum(np.array(g['bounds'][:3])-pp,pp-np.array(g['bounds'][3:])),0)
        assert np.linalg.norm(pp-g['center'],axis=1).max()<=g['radius']+1e-7
        support.append(dict(component=g['id'],pins=len(pins),source_triangles=len(g['rows']),proxy_triangles=len(g['far']),maximum_source_aabb_overshoot_world_units=float(np.linalg.norm(outside,axis=1).max()),lod_sphere_contains_proxy=True))
    (OUT/'scenery-support-checks.json').write_text(json.dumps(support,indent=2)+'\n')
    native=[]
    for label,root,tick in [('census600-baseline',BASE,600),('census600-candidate',OUT,600),('census1950-candidate',OUT,1950)]:
        text=(OUT/(label+'.log')).read_text();observed=[]
        for line in text.splitlines():
            if not line.startswith('CENSUS '):continue
            observed.append({k:int(v) for k,v in re.findall(r'(\w+)=(\d+)',line)})
        assert len(observed)==4,label
        expected=[r for r in csv.DictReader((root/'replay/cameras.csv').open()) if r['candidate']=='1' and int(r['tick'])==tick]
        for a,b in zip(observed,expected):
            assert a['camera']==int(b['camera']) and a['tick']==tick
            for x,y in [('vertices','vertices'),('triangles','triangles'),('chunks','chunks'),('materials','material_changes')]:assert a[x]==int(b[y]),(label,x,a[x],b[y])
        native.append(dict(label=label,tick=tick,observed=observed,all_match=True))
    (OUT/'native-census-checks.json').write_text(json.dumps(native,indent=2)+'\n')
    controls=json.loads((OUT/'native-cell-controls.json').read_text());assert len(controls)==2 and all(r['changed_pixels']==0 for r in controls)
    rdp=json.loads((OUT/'rdp-validation.json').read_text());assert rdp['errors']==rdp['warnings']==0
    names=['sidewinder_budget_cells.py','render_world_cells.h','test_world_cells.c','measure_budget_cells.py','report_budget_cells.py','collect_budget_cells.py','main.c','scene.c','world.h','map_qa.h','build.py','export_chiron_visibility.py','runtime_source.py','test_scene_equivalence.py']
    destination=OUT/'source-snapshot/port/n64';destination.mkdir(parents=True,exist_ok=True);hashes={}
    for name in names:
        source=ROOT/'port/n64'/name;shutil.copy2(source,destination/name);hashes['port/n64/'+name]=hashlib.sha256(source.read_bytes()).hexdigest()
    proof=dict(candidate_bank_sha256=hashlib.sha256(bank).hexdigest(),baseline_bank_sha256=hashlib.sha256((BASE/'candidate-maps/sidewinder.map64').read_bytes()).hexdigest(),canonical_bank_sha256=hashlib.sha256(canonical.read_bytes()).hexdigest(),canonical_unchanged=True,all_texture_and_gameplay_sections_identical=True,all_original_expanded_near_attributes_retained=True,source_pvs_memberships_not_narrowed_by_repacking=True,matching_replay_camera_states=68,matching_complete_photo_player_states=24,cell_control_pixel_identity_cameras=148,pvs_control_pixel_identity_cameras=92,native_counter_cameras_match=12,scenery_support_components=len(support),scenery_proxy_lod_spheres_verified=True,adoption='Unadopted; stopped for appraisal',limitations=['Most views remain above 1500 static vertex loads.','Extra directional batches increase CPU submission overhead.','Finite image/zoom/cell-edge checks; not an all-view transition or combat-visibility proof.','Outside-grid positions fail open and are not represented in the performance sample.','Previously retained east-room bank still lacks scoped validation and hysteresis.','Native results are Ares emulator measurements.'],working_source_sha256=hashes)
    proof.update(native_cell_control_pixel_identity_frames=2,native_cell_control_pixel_identity_cameras=8,native_rdp_errors=rdp['errors'],native_rdp_warnings=rdp['warnings'],checks=['ASan/UBSan SDK replay and photo fixtures','Cell layout, boundaries and finite fallback under target fast-math flags','36 legacy renderer helper equivalence checks','2000 legacy material command streams','World LOD selector ASan/UBSan checks','Native full-precision photo pose and overlay identity','Native culling-only pixel controls at two four-camera frames'])
    (OUT/'validation.json').write_text(json.dumps(proof,indent=2)+'\n');print(json.dumps({k:v for k,v in proof.items() if k!='working_source_sha256'},indent=2))

if __name__=='__main__':
    import sys
    {'timings':timings,'profiles':profiles,'images':native_images,'cell-controls':native_cell_controls,'validation':final_validation}[sys.argv[1]]()
