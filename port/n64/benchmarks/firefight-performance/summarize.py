#!/usr/bin/env python3
"""Summarize the ordinary 2P opening and nested per-tick diagnostic counters."""
import argparse,hashlib,json,statistics,sys
from pathlib import Path
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[3]
sys.path.insert(0,str(HERE.parent/'firefight-limited'))
from collect import summarize,fields

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def detail_summary(rows):
    ticks=sum(r['tick_calls'] for r in rows)
    return {'windows':len(rows),'ticks':ticks,'first_tick':rows[0]['tick']-29,'last_tick':rows[-1]['tick'],
      'ms_per_tick':{k[:-3]:round(sum(r[k] for r in rows)/ticks/1000,4) for k in rows[0] if k.endswith('_us')},
      'totals':{k:sum(r[k] for r in rows) for k in rows[0] if k!='tick'}}
def main():
    p=argparse.ArgumentParser();p.add_argument('capture',type=Path);p.add_argument('--output',type=Path,default=HERE/'results.json');a=p.parse_args()
    cases={}
    for name in ['opening-2','detail-2']:
        path=a.capture/(name+'-native.log');d=summarize(path)
        both=[r for r in d['samples'][5:] if r['FF_STATE']['living']==2 and r['FF_STATE']['enemies']>0 and r['FF_STATE']['arriving']==0]
        d['both_humans_and_landed_enemies']={'observations':len(both),'fps_mean':round(statistics.mean(r['PERF']['fps'] for r in both),2),'fps_min':min(r['PERF']['fps'] for r in both),'fps_max':max(r['PERF']['fps'] for r in both)}
        d['phase_ms']={k:round(statistics.mean(r['PHASE'][k] for r in d['samples'][5:])/1000,3) for k in ('camera','anim','world','objects','fp','hud','audio','overlay')}
        d['log_sha256']=sha(path);d.pop('samples');cases[name]=d
    rows=[fields(l) for l in (a.capture/'detail-2-native.log').read_text().splitlines() if l.startswith('DETAIL ')]
    assert len(rows)>=75 and all(r['tick_calls']==30 for r in rows)
    out={'schema':1,'frame_cases':cases,'detail':{'notes':['Native timings in microseconds. Every DETAIL row accumulates 30 simulation ticks, independent of rendered-frame catch-up.','Top-level director/humans/vehicles/actors/projectiles/after are disjoint; sees/selectors/destination/path/capsule/hit are nested. Do not add the nested rows to the top-level rows.','path includes cache hits and rebuilds. bfs counts cache misses (including invalid goals); this run visits exactly 6464 nodes per miss.','hit_triangles counts triangles entering candidate loops, before material-specific shield skips. Instrumentation perturbs timing and frame sampling.'],
      'after_five_sim_seconds':detail_summary([r for r in rows if r['tick']>150]),
      'after_first_landing':detail_summary([r for r in rows if r['tick']>600]),
      'highest_simulation_window':max(rows,key=lambda r:r['tick_us']),
      'highest_projectile_window':max(rows,key=lambda r:r['projectiles_us'])}}
    a.output.write_text(json.dumps(out,indent=2)+'\n')
    print('baseline FPS',cases['opening-2']['living_players_and_landed_enemies'])
    print('tick timings',out['detail']['after_first_landing']['ms_per_tick'])
if __name__=='__main__':main()
