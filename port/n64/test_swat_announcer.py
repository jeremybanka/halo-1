"""Check Reach source provenance, exact PCM conversion, dispatch and ROM streaming."""
import argparse, hashlib, json, subprocess, tempfile, wave
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ffmpeg',default='ffmpeg')
    args=parser.parse_args()
    assets=ROOT/'halo64-assets'
    report=json.loads((assets/'assets/swat-announcer/provenance.json').read_text())
    assert report['line']=='SWAT. Slayer.' and report['game']=='Halo: Reach retail'
    assert [r['tag'] for r in report['recordings']]==[
        r'sound\dialog\multiplayer\reach\multiplayer_game_types\swat',
        r'sound\dialog\multiplayer\slayer\slayer']
    assert report['extractor_sha256']==hashlib.sha256((ROOT/'port/n64/extract_reach_swat_voice.py').read_bytes()).hexdigest()
    for name,record in report['files'].items():
        data=(assets/name).read_bytes()
        assert len(data)==record['bytes'] and hashlib.sha256(data).hexdigest()==record['sha256']
    source=assets/'assets/swat-announcer'
    def read_wave(name):
        with wave.open(str(source/name),'rb') as f:
            assert (f.getnchannels(),f.getsampwidth(),f.getframerate())==(1,2,44100)
            return f.readframes(f.getnframes())
    assert read_wave('swat-slayer.wav')==read_wave('swat.wav')+b'\0\0'*round(report['gap_seconds']*44100)+read_wave('slayer.wav')
    pcm=assets/'frontend-files/mode_swat.s8'
    assert report['samples']==len(pcm.read_bytes())==26603
    with tempfile.TemporaryDirectory(prefix='halo-swat-announcer-') as temp:
        temp=Path(temp);(temp/'t3d').mkdir()
        (temp/'t3d/t3d.h').write_text('typedef struct { char data[32]; } T3DVertPacked;\n')
        converted=temp/'voice.s8'
        subprocess.run([args.ffmpeg,'-v','error','-y','-i',str(source/'swat-slayer.wav'),'-ar','11025','-ac','1','-f','s8',str(converted)],check=True)
        assert converted.read_bytes()==pcm.read_bytes()
        (temp/'routing.c').write_text('''
#include <assert.h>
#include <stddef.h>
#include <string.h>
#include "announcer.h"
int main(void) {
    assert(!bg_mode_announcement(BG_MODE_SLAYER));
    assert(!strcmp(bg_mode_announcement(BG_MODE_TEAM_SLAYER),"mode_team_slayer.s8"));
    assert(!strcmp(bg_mode_announcement(BG_MODE_SWAT),"mode_swat.s8"));
    assert(!strcmp(bg_mode_announcement(BG_MODE_TEAM_SWAT),"mode_swat.s8"));
    const char *names[]={NULL,"mode_capture_the_flag.s8","mode_oddball.s8","mode_king_of_the_hill.s8","mode_race.s8"};
    const char *team[]={"mode_team_slayer.s8","mode_capture_the_flag.s8","mode_team_oddball.s8","mode_team_king_of_the_hill.s8","mode_team_race.s8"};
    for(unsigned m=0;m<BG_SOURCE_MODE_COUNT;m++) {
        const bg_mode_rules *r=bg_mode_preset(m);
        const char *expected=(r->teams?team:names)[r->engine],*actual=bg_mode_announcement(m);
        assert(expected?actual&&!strcmp(actual,expected):!actual);
    }
}
''')
        flags=['clang','-std=c17','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined','-I'+str(temp),'-I'+str(ROOT/'port/n64')]
        subprocess.run(flags+[str(temp/'routing.c'),'-o',str(temp/'routing')],check=True)
        subprocess.run([str(temp/'routing')],check=True)
        subprocess.run(flags+['-DBG_TEST_PCM_BYTES='+str(report['samples']),str(ROOT/'port/n64/test_announcer_stream.c'),str(ROOT/'port/n64/sound_mix.c'),'-o',str(temp/'stream')],check=True)
        subprocess.run([str(temp/'stream'),str(pcm)],check=True)
    print('PASS: Reach SWAT / Slayer provenance, unchanged recording concatenation, exact 11025 Hz PCM, both mode routes and 26 original announcements')


if __name__=='__main__':main()
