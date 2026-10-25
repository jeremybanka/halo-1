"""Repeat the established SDK fixtures against the single-bend candidate."""
import inspect,json,sys
import measure_world_lod as shared
from sidewinder_canyon_rebuild import ROOT,OUT,BASE

def measure():
    function=inspect.getsource(shared.measure)
    # Preserve the validated driver and build path; compare with the latest
    # world-LOD baseline, and keep these experiment outputs isolated.
    namespace=dict(shared.__dict__);namespace['OUT']=OUT/'candidate';namespace['BASE']=BASE
    exec(function,namespace);namespace['measure']()
    (OUT/'measurements.json').write_text((OUT/'candidate/measurements.json').read_text())
if __name__=='__main__':measure()
