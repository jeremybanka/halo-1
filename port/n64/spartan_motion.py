"""Compose CE recoil with the same base samples for render and collision banks."""
from pack_fp_ammo import overlay_states

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
