"""Build isolated native vehicle fixtures, leaving the research checkout alone."""
import argparse,subprocess,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[4];OUT=ROOT/'build/pve-vehicles'
p=argparse.ArgumentParser();p.add_argument('--players',type=int,nargs='*',default=[1,2,3,4]);p.add_argument('--fixtures',type=int,nargs='*',default=[8,9]);p.add_argument('--photo',action='store_true');p.add_argument('--play',action='store_true');p.add_argument('--maps',action='store_true');p.add_argument('--probe',action='store_true');a=p.parse_args()
python=ROOT/'build/n64-python/bin/python';base=[str(python),'port/n64/build.py','--pve-crunch','--pve-roster','--pve-jackal-shields','--pve-model-bank','build/pve-vehicles/bank','--enemy-vehicle-bank','build/pve-vehicles/bank','--map-bank-override','build/pve/ground/bloodgulch.map64','--sdk','/Users/jem/dojo/n64-2048/.build/libdragon','--tiny3d','/Users/jem/dojo/halo-1/build/n64-sidewinder-throughput/tiny3d-unlit']
cases=[(f'final-{fixture}-{players}',['--pve-squad','--pve-players',str(players),'--pve-qa',str(fixture),'--profile','--collision-profile','--pve-prep-profile']) for fixture in a.fixtures for players in a.players]
if a.photo:cases.append(('final-photo',['--pve-squad','--pve-players','4','--enemy-vehicle-qa']))
if a.play:cases.append(('play',['--firefight','--preset','release']))
if a.maps:cases.append(('maps-cycle',['--firefight','--maps-cycle','--preset','release']))
if a.probe:cases.insert(0,('map-probe',['--firefight','--initial-map','beavercreek','--snapshot-tick','0','--geometry-census','--lto','--rspq-buffer-kib','32']))
for name,flags in cases:
 with (OUT/(name+'-build.log')).open('w') as log:subprocess.run(base+flags+['--output-dir',str(OUT/name)],cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,check=True)
 roms=list((OUT/name).glob('*.z64'));assert len(roms)==1
 print(name,roms[0].name,roms[0].stat().st_size,flush=True)
