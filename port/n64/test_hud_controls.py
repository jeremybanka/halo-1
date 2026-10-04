"""Exercise actual cached HUD status selection for both controller layouts."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
from test_render_matrix import compact, function

ROOT = Path(__file__).resolve().parents[2]


def run(output):
    source = (ROOT/'port/n64/hud.c').read_text()
    declarations = re.search(r'enum \{ HUD_EXIT,.*?status_strings\[HUD_STATUS_COUNT\]=\{.*?\};', source, re.S)
    assert declarations
    init = compact(function(source, 'bg_hud_init'))
    assert 'for(unsignedsplit=0;split<2;split++)for(unsignedi=0;i<HUD_STATUS_COUNT;i++)' in init
    assert 'status_layouts[split][i]=rdpq_paragraph_build(' in init
    draw = compact(function(source, 'bg_hud_draw'))
    assert draw.count('status=control_status(status,style);') == 1
    assert draw.index('status=control_status(status,style);') < draw.index('rdpq_paragraph_render(status_layouts[width<200][status]')
    assert 'rdpq_paragraph_build' not in draw
    harness = '#include "controls.h"\n#include <assert.h>\n#include <stdio.h>\n#include <string.h>\n'
    harness += declarations.group()+'\n'
    harness += 'static int control_status(int status,bg_control_style style){'+function(source, 'control_status')+'}\n'
    harness += r'''
int main(void) {
    const char *legacy[]={"B EXIT","B PICK UP","B ENTER","Reloading","Overheated",
        "Respawn in 0","Respawn in 1","Respawn in 2","Respawn in 3"};
    const char *xbox[]={"C-LEFT EXIT","C-LEFT PICK UP","C-LEFT ENTER"};
    assert(HUD_EXIT==0&&HUD_ENTER==2&&HUD_RESPAWN_0==5&&HUD_RESPAWN_3==8);
    assert(HUD_XBOX_EXIT==9&&HUD_STATUS_COUNT==12);
    for(int status=-1;status<HUD_STATUS_COUNT;status++) {
        assert(control_status(status,BG_CONTROLS_N64)==status);
        assert(control_status(status,(bg_control_style)-1)==status);
        assert(control_status(status,BG_CONTROLS_COUNT)==status);
        int result=control_status(status,BG_CONTROLS_XBOX);
        if(status>=0&&status<3)assert(strcmp(status_strings[result],xbox[status])==0);
        else assert(result==status);
        if(status>=0&&status<9)assert(strcmp(status_strings[status],legacy[status])==0);
    }
    /* Changing one player's style needs no mutation of shared strings or
     * existing paragraph slots; the next N64 player still selects B. */
    assert(control_status(HUD_ENTER,BG_CONTROLS_XBOX)==HUD_XBOX_ENTER);
    assert(control_status(HUD_ENTER,BG_CONTROLS_N64)==HUD_ENTER);
    puts("PASS: cached B/C-LEFT interaction labels; legacy status IDs/text unchanged; all statuses/styles; no per-draw layout build");
}
'''
    output.mkdir(parents=True, exist_ok=True)
    c = output/'hud-controls.c';c.write_text(harness)
    binary = output/'test-hud-controls'
    command = ['clang','-std=c17','-O1','-g','-Wall','-Wextra','-Werror',
               '-fsanitize=address,undefined','-I'+str(ROOT/'port/n64'),str(c),'-o',str(binary)]
    subprocess.run(command, check=True)
    result = subprocess.run([str(binary)], check=True, capture_output=True, text=True)
    print(result.stdout.strip())
    (output/'hud-controls-proof.json').write_text(json.dumps({
        'hud_sha256':hashlib.sha256(source.encode()).hexdigest(),
        'test_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'command':command,'output':result.stdout.strip(),
        'extra_cached_paragraphs':6,'extra_paragraph_pointer_bytes_on_N64':24,
        'limitation':'Paragraph payload memory depends on SDK font layout; no claim of total heap cost.'
    },indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/n64/controls-qa')
    run(parser.parse_args().output.resolve())
