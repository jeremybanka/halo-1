#include "scope_mask.h"
#include "view_layout.h"
#include "hud_layout.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
int main(void) {
    uint8_t pixels[BG_SCOPE_LARGE_SIZE * BG_SCOPE_LARGE_SIZE];
    for (unsigned views = 1; views <= 4; views++) for (unsigned p = 0; p < views; p++) {
        bg_view_rect rect = bg_view_area(views,p);
        unsigned size = bg_scope_mask_size(rect.h);
        assert(size <= (unsigned)rect.w && size <= (unsigned)rect.h);
        for (unsigned edge = 128; edge <= 132; edge += 4) {
            bg_scope_mask_generate(pixels,size,edge);
            unsigned diameter_x=0,diameter_y=0;
            for (unsigned y=0;y<size;y++) for (unsigned x=0;x<size;x++) {
                unsigned a=pixels[y*size+x];
                assert(a==0 || a==edge);
                /* A circle is invariant under reflection and 90-degree rotation. */
                assert(a==pixels[y*size+size-1-x]);
                assert(a==pixels[(size-1-y)*size+x]);
                assert(a==pixels[x*size+y]);
                if(y==size/2 && a!=edge)diameter_x++;
                if(x==size/2 && a!=edge)diameter_y++;
                float dx=x-(size-1)*.5f,dy=y-(size-1)*.5f;
                float distance=sqrtf(dx*dx+dy*dy), radius=size==152?75:37;
                if(a==0)assert(distance<=radius);else assert(distance>radius);
            }
            assert(diameter_x==diameter_y && diameter_x==(size==152?150:74));
        }
    }
    puts("PASS: 1–4-player circular apertures, both weapon opacities, bilateral/rotational symmetry and no added outline");
}
