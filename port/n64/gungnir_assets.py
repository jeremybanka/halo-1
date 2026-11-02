"""Resolve preserved extraction texture references after private-bank restore."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def texture_path(path, source=None):
    name=Path(path).name
    candidates=[ROOT/'halo64-assets/assets/gungnir/demake-20261102/source/textures'/name]
    if source is not None:candidates.extend((Path(source).parent/'textures'/name,Path(source).parent/Path(path)))
    candidates.append(Path(path))
    for candidate in candidates:
        if candidate.is_file():return candidate
    raise FileNotFoundError('Restore the private GUNGNIR source texture: '+name)
