"""Generate isolated feature-cache experiments; leave the release adapter intact."""


def candidate_source(source, slots):
    if slots not in (128, 512):
        raise ValueError('Feature-cache experiments support 128 or 512 entries')
    for old, new in (
        ('prisms[32]', f'prisms[{slots}]'),
        ('cylinders[64]', f'cylinders[{slots}]'),
        ('unsigned slot=(unsigned)si%32;', f'unsigned slot=(unsigned)si%{slots};'),
        ('((uint32_t)edge*2654435761u)&63u', f'((uint32_t)edge*2654435761u)&{slots-1}u'),
    ):
        if source.count(old) != 1:
            raise ValueError('Feature-cache adapter changed: ' + old)
        source = source.replace(old, new, 1)
    marker = ' if(world_loaded)return;'
    if source.count(marker) != 1:
        raise ValueError('Feature-cache world lifecycle changed')
    return source.replace(marker, marker + '''
#ifdef N64
 assertf(get_memory_size()>=8*1024*1024,"Feature-cache experiment requires Expansion Pak");
#endif''', 1)
