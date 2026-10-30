"""Fixed four-player pose workload; identical state and source banks in each ROM."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time

ROOT = Path(__file__).resolve().parents[4]
OUT = ROOT / 'build/player-aim'
HERE = Path(__file__).resolve().parent
FIXTURE = r'''
/* Diagnostic only: no shots, damage, AI, or divergent combat outcomes. The
 * ordinary renderer, animation paths, graphics fences and profiler remain. */
void bg_tick(const bg_input inputs[BG_PLAYERS], float dt) {
    (void)inputs;static float time;time+=dt;bg_clear_events();
    for(unsigned i=0;i<bg_vehicle_count;i++)bg_vehicles[i].active=false;
    for(unsigned i=0;i<bg_pickup_count;i++)bg_pickups[i].active=false;
    unsigned mode=(unsigned)(time/15)%3;
    for(unsigned i=0;i<4;i++){
        bg_player*p=&bg_players[i];memset(p,0,sizeof(*p));
        p->pos[0]=(i&1)?1.2f:-1.2f;p->pos[2]=4+((i&2)?1.2f:-1.2f);
        p->pos[1]=bg_floor(p->pos[0],p->pos[2],100)+.015f;
        p->yaw=atan2f(p->pos[2]-4,-p->pos[0]);p->pitch=.6f*sinf(time*.7f+i);
        p->health=p->shield=100;p->camo_opacity=1;p->grounded=true;p->vehicle=-1;
        p->weapon=p->inventory[0]=BG_W_AR;p->inventory[1]=BG_W_PISTOL;p->ammo=60;p->reserve=120;
        p->velocity[0]=1;p->locomotion_time=time;p->gait=time*5;
        p->crouch_amount=.5f+.5f*sinf(time*.4f);p->crouched=p->crouch_amount>.5f;
        p->animation=BG_ANIM_RUN;p->fire_ticks[0]=10;
        if(mode==1){p->animation=BG_ANIM_FIRE;p->fire_ticks[0]=(unsigned)(time*30)%3;p->anim_time=p->fire_ticks[0]/30.f;p->flash=.05f;}
        if(mode==2){p->animation=BG_ANIM_RELOAD;p->reload_duration=3;p->reload=3-fmodf(time,3);p->anim_time=3-p->reload;}
    }
}
'''

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('step', choices=('build', 'run'))
    parser.add_argument('--settings', type=Path, default=OUT / 'ares.bml')
    args = parser.parse_args()
    if args.step == 'build':
        game = (ROOT / 'port/n64/game.c').read_text()
        assert game.count('void bg_tick(') == 1
        (OUT / 'controlled-game.c').write_text(game.replace('void bg_tick(', 'void bg_original_tick(') + FIXTURE)
        subprocess.run(['git', 'show', 'f40fefee:port/n64/scene.c'], cwd=ROOT, check=True,
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
                    if 'BENCH triangles world=' in text or 'assertion failed' in text.lower():break
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
        print(variant, results[variant], flush=True)
        (HERE / 'controlled.json').write_text(json.dumps(results, indent=2) + '\n')

if __name__ == '__main__':main()
