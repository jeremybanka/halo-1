"""Compose source actions with shared render/collision locomotion samples."""
from pack_fp_ammo import overlay_states

BODY_RELOAD_FRAMES=12  # Retain the existing third-person reload sample density.

def replacement_states(base, action, flags):
    # CE replacement_animation_apply replaces only channels present in the
    # source mask. In particular this reload does not animate pelvis or legs.
    assert not flags['scale'], 'Non-unit replacement scales need explicit skin support'
    return [{**b, 'q':a['q'] if flags['rot']&(1<<i) else b['q'],
             'p':a['p'] if flags['trans']&(1<<i) else b['p']}
            for i,(b,a) in enumerate(zip(base,action))]

def reload_cycles(raw, crouch_clips):
    action=raw['animations']['reload'];assert action['type']=='replacement'
    flags={key:action[key+'_flags'] for key in ('rot','trans','scale')}
    samples=[round(i*(len(action['frames'])-1)/(BODY_RELOAD_FRAMES-1)) for i in range(BODY_RELOAD_FRAMES)]
    rows=[]
    for index,base in enumerate([raw['animations']['idle'],raw['animations']['run'],*crouch_clips]):
        count=min(8 if index==0 else 10,len(base['frames'])) if index<2 else len(base['frames'])
        gait=[round(i*(len(base['frames'])-1)/max(1,count-1)) for i in range(count)]
        rows.append({'base':base.get('tag_name',base.get('name')),'source_samples':gait,
                     'action_samples':samples,'duration':base['duration'],'cycles':[
                         [replacement_states(base['frames'][i],action['frames'][j],flags) for i in gait]
                         for j in samples]})
    return rows

def firing_cycles(raw, crouch_clips):
    recoil=raw['animations']['fire']
    assert recoil['type']=='overlay' and len(recoil['frames'])==5
    assert abs(recoil['duration']-5/30)<1e-7
    flags={key:recoil[key+'_flags'] for key in ('rot','trans','scale')}
    bases=[raw['animations']['idle'],raw['animations']['run'],*crouch_clips]
    assert len(bases)==4
    rows=[]
    for index,base in enumerate(bases):
        count=min(8 if index==0 else 10,len(base['frames'])) if index<2 else len(base['frames'])
        samples=[round(i*(len(base['frames'])-1)/max(1,count-1)) for i in range(count)]
        rows.append({'base':base.get('tag_name',base.get('name')),'source_samples':samples,
                     'duration':base['duration'],'cycles':[
                         [overlay_states(base['frames'][i],overlay,flags) for i in samples]
                         for overlay in recoil['frames']]})
    return rows
