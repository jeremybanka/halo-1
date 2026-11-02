"""Fast face-ID/depth audits, calibrated against the existing model auditor."""
from pathlib import Path
import ctypes,subprocess
import numpy as np
from PIL import Image
from audit_models import camera_basis,render as reference_render


class Raster:
    def __init__(self,output):
        path=Path(output)/'demake-raster.dylib'
        subprocess.run(['clang','-O2','-std=c17','-Wall','-Wextra','-Werror','-shared','-fPIC',str(Path(__file__).with_suffix('.c')),'-o',str(path)],check=True)
        self.library=ctypes.CDLL(str(path.resolve()));pointer=ctypes.c_void_p
        self.library.bg_demake_raster.argtypes=[pointer,pointer,pointer,ctypes.c_uint,ctypes.c_uint,ctypes.c_uint,pointer,pointer,pointer]

    def render(self,mesh,bounds,direction,width=96,height=96):
        center,span=bounds;look,right,up=camera_basis(direction);points=np.asarray(mesh.p,dtype=np.float64);relative=points-center;scale=min(width/span[0],height/span[1])*.80
        screen=np.ascontiguousarray(np.stack((relative@right*scale+width/2,-relative@up*scale+height/2,relative@look),axis=-1),dtype=np.float64)
        facing=np.ascontiguousarray(np.cross(points[:,1]-points[:,0],points[:,2]-points[:,0])@look)
        colors=np.ascontiguousarray(mesh.rgb,dtype=np.float64) if mesh.rgb is not None else None
        rgb=np.zeros((height,width,3),dtype=np.uint8);ids=np.empty((height,width),dtype=np.int32);depth=np.empty((height,width),dtype=np.float64)
        self.library.bg_demake_raster(screen.ctypes.data,facing.ctypes.data,colors.ctypes.data if colors is not None else None,len(points),width,height,rgb.ctypes.data,ids.ctypes.data,depth.ctypes.data)
        return Image.fromarray(rgb),ids,depth

    def calibrate(self,mesh,bounds,direction):
        old,mask=reference_render(mesh,bounds,direction,width=96,height=96);new,ids,_=self.render(mesh,bounds,direction)
        assert np.array_equal(mask,ids>=0),'Face-ID raster differs from the accepted geometry auditor'
        error=int(np.abs(np.array(old).astype(int)-np.array(new).astype(int)).max());assert error<=1,error
        return dict(mask_pixels=int(mask.sum()),maximum_rgb_error=error)
