"""Same SDK fixtures, including the regional representation selection."""
import inspect
import measure_world_lod as shared
from sidewinder_budget import ROOT,OUT,BASE

def measure():
    function=inspect.getsource(shared.measure)
    anchor="        (output/'camera.c').write_text(driver)"
    instrumentation='''        driver=driver.replace('#include "render_world_lod.h"','#include "render_world_lod.h"\\n#include "render_world_rep.h"')
        driver=driver.replace(' uint8_t levels[BG_WORLD_LOD_MAX_GROUPS];',' bool representation=bg_world_rep_active(&bg_world_rep,bg_map_id(),eye.v);\\n uint8_t levels[BG_WORLD_LOD_MAX_GROUPS];')
        driver=driver.replace('  const bg_chunk*k=&bg_chunks[b];','  const bg_chunk*k=&bg_chunks[b];\\n  if(!bg_world_rep_keep(&bg_world_rep,representation,b))continue;')
'''
    assert anchor in function;function=function.replace(anchor,instrumentation+anchor)
    namespace=dict(shared.__dict__);namespace['OUT']=OUT;namespace['BASE']=BASE
    exec(function,namespace);namespace['measure']()
if __name__=='__main__':measure()
