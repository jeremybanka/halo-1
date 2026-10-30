"""Fixed four-Warthog flash workload; identical state and source banks in each ROM."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'build/warthog-muzzle'
HERE = Path(__file__).resolve().parent
FIXTURE = r'''
/* Worst-case presentation fixture: all four guns produce a shot every tick.
 * No AI, damage or physics can make the two renderers diverge. */
void bg_tick(const bg_input inputs[BG_PLAYERS],float dt){
    (void)inputs;static float time;time+=dt;bg_clear_events();bg_pickup_count=0;bg_vehicle_count=4;
    for(unsigned i=0;i<4;i++){
        bg_vehicle*v=&bg_vehicles[i];memset(v,0,sizeof(*v));v->active=true;v->health=100;
        v->kind=BG_V_WARTHOG;v->pos[0]=-12.f+(i&1)*3;v->pos[2]=5+(i>>1)*3;
        v->pos[1]=bg_floor(v->pos[0],v->pos[2],100)+.2f;
        for(unsigned j=0;j<BG_VEHICLE_SEATS;j++)v->occupants[j]=-1;
        v->occupants[1]=i;v->turret_yaw=atan2f(v->pos[2]-6.5f,-10.5f-v->pos[0]);
        v->turret_pitch=.1f*sinf(time+i);
        bg_player*p=&bg_players[i];memset(p,0,sizeof(*p));p->health=p->shield=100;
        p->vehicle=i;p->seat=1;p->seat_state=BG_SEAT_STABLE;p->camo_opacity=1;
        p->yaw=v->turret_yaw;p->pitch=v->turret_pitch;p->animation=BG_ANIM_DRIVE;
        p->weapon=p->inventory[0]=BG_W_AR;p->inventory[1]=BG_W_PISTOL;
        bg_vehicle_seat_position(v,1,false,p->pos);
        event(BG_EVENT_FIRE,i,BG_W_AR,v->pos,1);
    }
}
'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step', choices=('build', 'run'))
    parser.add_argument('--settings', type=Path, default=ROOT / 'build/player-aim/ares.bml')
    args = parser.parse_args()
    if args.step == 'build':
        game = (ROOT / 'port/n64/game.c').read_text()
        assert game.count('void bg_tick(') == 1
        (OUT / 'controlled-game.c').write_text(game.replace('void bg_tick(', 'void bg_original_tick(') + FIXTURE)
        subprocess.run(['git', 'show', '9bd15eef:port/n64/scene.c'], cwd=ROOT, check=True,
                       stdout=(OUT / 'baseline-scene.c').open('w'))
        for variant in ('baseline', 'candidate'):
            flags = ['--scene-source', str(OUT / 'baseline-scene.c')] if variant == 'baseline' else []
            with (OUT / f'controlled-{variant}-build.log').open('w') as log:
                subprocess.run([str(ROOT / 'build/n64-python/bin/python'), 'port/n64/build.py',
                                '--benchmark', '--profile', '--preset', 'release', '--game-source', str(OUT / 'controlled-game.c'),
                                '--sdk', '/Users/jem/dojo/n64-2048/.build/libdragon', '--tiny3d',
                                '/Users/jem/dojo/halo-1/build/n64-sidewinder-throughput/tiny3d-unlit',
                                '--output-dir', str(OUT / ('controlled-' + variant)), *flags],
                               cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, check=True)
        return
    results = {}
    for variant in ('baseline', 'candidate'):
        manifest = json.loads(next((OUT / ('controlled-' + variant)).glob('*.build.json')).read_text())
        path = OUT / f'controlled-{variant}-native.log'
        with path.open('w') as log:
            proc = subprocess.Popen(['/Applications/ares.app/Contents/MacOS/ares', '--settings-file',
                                     str(args.settings.resolve()), '--no-file-prompt', manifest['rom']['path']],
                                    stdout=log, stderr=subprocess.STDOUT)
            start = time.monotonic()
            try:
                while proc.poll() is None and time.monotonic() - start < 360:
                    time.sleep(.5)
                    text = path.read_text(errors='replace')
                    if 'BENCH triangles world=' in text or 'assertion failed' in text.lower() or 'CPU EXCEPTION' in text:break
            finally:
                proc.terminate()
                try:proc.wait(timeout=5)
                except subprocess.TimeoutExpired:proc.kill();proc.wait()
        text = path.read_text(errors='replace');assert 'BENCH triangles world=' in text, text[-2000:]
        phase = re.search(r'BENCH phase_us (.*)', text)[1]
        groups = {}
        for line in re.findall(r'BENCH cpu_acquisition group=.*', text):
            group = line.split('group=')[1].split(' frames=')[0]
            values = {k:int(v) for k,v in re.findall(r'(\w+)=(\d+)', line)}
            values['fps'] = values['frames'] * 1e6 / values['elapsed_us']
            groups[group] = values
        results[variant] = dict(phase_us={k:int(v) for k,v in re.findall(r'(\w+)=(\d+)', phase)},
            groups=groups, rom_sha256=hashlib.sha256(Path(manifest['rom']['path']).read_bytes()).hexdigest(),
            rom_bytes=Path(manifest['rom']['path']).stat().st_size,
            log_sha256=hashlib.sha256(path.read_bytes()).hexdigest())
        print(variant, results[variant]['phase_us'], results[variant]['groups']['ALL FRAMES']['fps'], flush=True)
        (HERE / 'controlled.json').write_text(json.dumps(results, indent=2) + '\n')

if __name__ == '__main__':main()
