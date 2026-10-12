"""Shared stable IDs for ROM service poses; reject malformed/reordered slots."""
from pathlib import Path
import re
SERVICE_SCHEMA = Path(__file__).with_name('interaction_services.def')
MAP_SCHEMA = Path(__file__).with_name('map_catalog.def')
def map_ids():
    rows=re.findall(r'^BG_MAP\((\d+), (\w+), "([^"]+)"\)$',MAP_SCHEMA.read_text(),re.M)
    ids={name:int(id) for id,_,name in rows}
    if len(ids)!=len(rows) or len(set(ids.values()))!=len(ids):raise ValueError('Duplicate map ID/cache')
    return ids
def service_keys():
    rows = re.findall(r'^BG_SERVICE\((\d+), (\w+), "([^"]+)", "([^"]+)"\)$', SERVICE_SCHEMA.read_text(), re.M)
    if not rows or [int(row[0]) for row in rows] != list(range(len(rows))):
        raise ValueError('Service IDs must be unique and contiguous in ROM order')
    return [(weapon, clip) for _, _, weapon, clip in rows]
