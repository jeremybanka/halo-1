"""Same SDK replay/photo fixtures with exact native cell and room selectors."""
import inspect
import measure_world_lod as shared
from sidewinder_budget_cells import ROOT,OUT,BASE

def measure():
    source=inspect.getsource(shared.measure)
    anchor="        (output/'camera.c').write_text(driver)"
    instrumentation='''        driver=driver.replace('#include "render_world_lod.h"','#include "render_world_lod.h"\\n#include "render_world_rep.h"\\n#include "render_world_cells.h"')
        driver=driver.replace(' uint8_t levels[BG_WORLD_LOD_MAX_GROUPS];',' bool representation=bg_world_rep_active(&bg_world_rep,bg_map_id(),eye.v);\\n const uint32_t *cell=representation||getenv("BG_CELL_DISABLE")?NULL:bg_world_cells_row_view(&bg_world_cells,bg_map_id(),eye.v,bg_players[p].health>0&&bg_players[p].zoom);\\n uint8_t levels[BG_WORLD_LOD_MAX_GROUPS];')
        driver=driver.replace('  const bg_chunk*k=&bg_chunks[b];','  const bg_chunk*k=&bg_chunks[b];\\n  if(!bg_world_rep_keep(&bg_world_rep,representation,b)||!bg_world_cells_keep(&bg_world_cells,cell,b))continue;')
'''
    assert anchor in source
    source=source.replace(anchor,instrumentation+anchor).replace("'-DBG_WORLD_LOD'","'-DBG_WORLD_LOD','-DBG_WORLD_REP','-DBG_WORLD_CELLS'")
    namespace=dict(shared.__dict__);namespace.update(OUT=OUT,BASE=BASE)
    exec(source,namespace);namespace['measure']()

if __name__=='__main__':measure()
