"""Host color preparation for Blender's independent Python ABI."""
import sys,json
from pathlib import Path
from PIL import Image
from pack_gungnir import prepare_broad_colors,corner_colors
from gungnir_assets import texture_path
data=json.loads(Path(sys.argv[1]).read_text());textures={i:Image.open(texture_path(p,sys.argv[1])).convert('RGB') for i,p in enumerate(data['textures']) if p};prepare_broad_colors(data,textures)
Path(sys.argv[2]).write_text(json.dumps([[corner_colors(t,data['materials'],textures) for t in lod['triangles']] for lod in data['lods']]))
