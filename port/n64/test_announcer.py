"""CE multikill audio tiers, generated clip order and source PCM provenance."""
from pathlib import Path
import json, re, subprocess, tempfile
ROOT=Path(__file__).resolve().parents[2]
with tempfile.TemporaryDirectory(prefix='halo-announcer-') as tmp:
    tmp=Path(tmp);(tmp/'t3d').mkdir()
    (tmp/'t3d/t3d.h').write_text('typedef struct { char data[32]; } T3DVertPacked;\n')
    (tmp/'test.c').write_text('''
#include <assert.h>
#include "announcer.h"
int main(void){
    assert(bg_multikill_sound(0)==BG_S_COUNT);
    assert(bg_multikill_sound(1)==BG_S_COUNT);
    assert(bg_multikill_sound(2)==BG_S_DOUBLE_KILL);
    assert(bg_multikill_sound(3)==BG_S_TRIPLE_KILL);
    for(unsigned n=4;n<100;n++)assert(bg_multikill_sound(n)==BG_S_KILLTACULAR);
    assert(bg_audio_assets[BG_S_KILLTACULAR].count==14048);
    assert(bg_audio_assets[BG_S_KILLTACULAR].rate==11025);
    assert(!bg_audio_assets[BG_S_KILLTACULAR].loop);
    assert(!bg_audio_assets[BG_S_KILLTACULAR].samples); // Streamed from ROM.
    assert(bg_audio_assets[BG_S_TRIPLE_KILL].samples!=bg_audio_assets[BG_S_KILLTACULAR].samples);
}
''')
    subprocess.run(['clang','-std=c17','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
        '-I'+str(tmp),'-I'+str(ROOT/'port/n64'),str(tmp/'test.c'),
        str(ROOT/'build/n64/generated/audio_data.c'),'-o',str(tmp/'test')],check=True)
    subprocess.run([str(tmp/'test')],check=True)
    subprocess.run(['clang','-std=c17','-O1','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',
        '-I'+str(ROOT/'port/n64'),str(ROOT/'port/n64/test_announcer_stream.c'),
        str(ROOT/'port/n64/sound_mix.c'),'-o',str(tmp/'stream')],check=True)
    subprocess.run([str(tmp/'stream'),str(ROOT/'build/n64/frontend-files/killtacular.s8')],check=True)
raw=json.loads((ROOT/'build/n64/assets/extended-raw.json').read_text())['audio']['killtacular']
assert raw['tag']==r'sound\dialog\multiplayer1\killtacular' and raw['source_cache']=='bloodgulch'
samples=Path(raw['file']).read_bytes()
data=(ROOT/'build/n64/generated/audio_data.c').read_text()
assert 'static const int8_t audio_killtacular' not in data
assert (ROOT/'build/n64/frontend-files/killtacular.s8').read_bytes()==samples
sound=(ROOT/'port/n64/sound.c').read_text()
assert re.search(r'case BG_EVENT_DOUBLE_KILL:\s*case BG_EVENT_TRIPLE_KILL:\s*bg_sound_announce\(bg_multikill_sound\(e->amount\)\)',sound)
assert 'bg_sound_stream_refill(&announcer_stream,&voices[12],' in sound
print('PASS: original CE 2/3/4+ tiers, generated sound IDs, decoded Killtacular PCM and production event dispatch')
