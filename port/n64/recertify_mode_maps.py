#!/usr/bin/env python3
"""Revalidate unchanged map banks after the multiplayer rules integration.

The old map report hashes game.c because its spawn solver certifies clearance.
This migration runs both legacy-map and new-mode fixtures before refreshing
that dependency; it cannot certify a changed geometry bank or exporter.
"""
import hashlib,json,subprocess,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    report_path=ROOT/'halo64-assets/generated/maps/maps-report.json'
    report=json.loads(report_path.read_text())
    stale={p for p,h in report['inputs'].items() if digest(ROOT/p)!=h}
    assert stale<={'port/n64/game.c'}, f'Unrelated map inputs changed: {stale}'
    bank=report_path.parent
    for p,h in report['files'].items():assert digest(bank/p)==h,p
    out=ROOT/'build/modes-tests';out.mkdir(parents=True,exist_ok=True)
    checks={}
    for flag,name in [('--maps-cycle','maps'),('--modes','rules')]:
        log=out/(name+'.log')
        with log.open('w') as f:
            subprocess.run([sys.executable,ROOT/'port/n64/test_maps.py',flag,'--output-dir',out/name],cwd=ROOT,stdout=f,stderr=subprocess.STDOUT,check=True)
        checks[name]=digest(log);print('PASS',name,flush=True)
    for p in stale:report['inputs'][p]=digest(ROOT/p)
    report['multiplayer_recertification']={'geometry_files_unchanged':True,'checks':checks,
        'method':'ASan/UBSan: thirteen maps, live menu cycles; 26 mode presets on all maps, capsule-clear starts and objective transitions.'}
    report_path.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':main()
