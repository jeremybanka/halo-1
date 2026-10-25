#ifndef BG_RENDER_WORLD_HIERARCHY_H
#define BG_RENDER_WORLD_HIERARCHY_H
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <string.h>
#include "render_world_lod.h"

#define BG_HIERARCHY_NONE UINT16_MAX
#define BG_HIERARCHY_LEAF 0x8000u
#define BG_HIERARCHY_LOD 0x4000u
#define BG_HIERARCHY_VALUE 0x3fffu
#define BG_HIERARCHY_STACK 64
typedef struct {
    int16_t bounds[6];
    uint16_t first, second, code;
} bg_hierarchy_node;
typedef struct {
    const bg_hierarchy_node *nodes;
    unsigned count, chunks, groups, map_id, depth;
} bg_hierarchy_data;
extern const bg_hierarchy_data bg_world_hierarchy;
typedef struct {
    const float (*planes)[4];
    const uint8_t (*selected)[3];
    const float (*camera)[4], (*projection)[4];
    const float *eye;
    float width, height, near_plane;
    const bg_world_lod_data *lod;
} bg_hierarchy_view;
typedef struct {
    unsigned nodes, planes, leaves, lod_groups, lod_us;
} bg_hierarchy_stats;
#ifndef BG_HIERARCHY_CLOCK
#define BG_HIERARCHY_CLOCK() 0u
#endif
#ifndef BG_HIERARCHY_COUNT
#define BG_HIERARCHY_COUNT(s, member) ((void)(s))
#endif

/* Same strict expression grouping as bg_frustum_box_cached. A cleared bit
 * certifies every point of this parent is inside that plane. Children are
 * enclosed by the parent's integer bounds, so inherit the certificate.
 * Leaves only need the positive-vertex rejection test, not an inside test. */
static inline int bg_hierarchy_clip(const bg_hierarchy_view *v,
        const int16_t box[6],unsigned mask,bool leaf,bg_hierarchy_stats *stats) {
    unsigned result=mask;
    for(unsigned i=0;i<6;i++)if(mask&(1u<<i)) {
        BG_HIERARCHY_COUNT(stats,planes);
        const float *p=v->planes[i];const uint8_t *s=v->selected[i];
        float x=p[0]*box[s[0]],y=p[1]*box[s[1]];
        float threshold=-p[3]-p[2]*box[s[2]];
        if(!(x+y>threshold))return -1;
        if(!leaf) {
            x=p[0]*box[s[0]<3?s[0]+3:s[0]-3];
            y=p[1]*box[s[1]<3?s[1]+3:s[1]-3];
            threshold=-p[3]-p[2]*box[s[2]<3?s[2]+3:s[2]-3];
            if(x+y>threshold)result&=~(1u<<i);
        }
    }
    return (int)result;
}

/* Eligibility excludes view-dependent LOD and frustum decisions. Node order
 * is preorder, so this reverse pass propagates leaf eligibility to parents.
 * caller supplies one byte per chunk, using the existing cell/room/PVS rules. */
static inline void bg_hierarchy_eligibility(const bg_hierarchy_data *data,
        const uint8_t *chunks,uint8_t *nodes) {
    for(unsigned i=data->count;i-->0;) {
        const bg_hierarchy_node *n=&data->nodes[i];
        if(n->code&BG_HIERARCHY_LEAF)nodes[i]=chunks[n->code&BG_HIERARCHY_VALUE];
        else nodes[i]=(n->first!=BG_HIERARCHY_NONE&&nodes[n->first]) ||
            (n->second!=BG_HIERARCHY_NONE&&nodes[n->second]);
    }
}

/* No queue commands or allocations here. Visible IDs are emitted later in
 * their original order. levels=255 denotes an unevaluated, invisible group. */
static inline void bg_hierarchy_visible(const bg_hierarchy_data *data,
        const uint8_t *eligible,const bg_hierarchy_view *view,uint32_t *visible,
        uint8_t *levels,bg_hierarchy_stats *stats) {
    typedef struct {uint16_t node;uint8_t mask;} entry;
    entry stack[BG_HIERARCHY_STACK];
    unsigned top=0;
    memset(visible,0,((data->chunks+31)/32)*sizeof(*visible));
    memset(levels,255,data->groups);
    if(!data->count)return;
    stack[top++]=(entry){0,63};
    while(top) {
        --top;
        unsigned index=stack[top].node,mask=stack[top].mask;
        if(!eligible[index])continue;
        const bg_hierarchy_node *n=&data->nodes[index];
        bool leaf=(n->code&BG_HIERARCHY_LEAF)!=0;
        BG_HIERARCHY_COUNT(stats,nodes);
        if(mask) {
            int remaining=bg_hierarchy_clip(view,n->bounds,mask,leaf,stats);
            if(remaining<0)continue;
            mask=(unsigned)remaining;
        }
        if(leaf) {
            unsigned b=n->code&BG_HIERARCHY_VALUE;
            visible[b/32]|=1u<<(b%32);
            BG_HIERARCHY_COUNT(stats,leaves);
        } else if(n->code&BG_HIERARCHY_LOD) {
            unsigned group=n->code&BG_HIERARCHY_VALUE;
            unsigned begin=BG_HIERARCHY_CLOCK();
            bool far=bg_world_lod_far(&view->lod->groups[group],view->camera,
                view->projection,view->width,view->height,view->near_plane,view->eye);
            stats->lod_us+=BG_HIERARCHY_CLOCK()-begin;
            BG_HIERARCHY_COUNT(stats,lod_groups);
            levels[group]=far;
            unsigned next=far?n->second:n->first;
            if(next!=BG_HIERARCHY_NONE) {
                assert(top<BG_HIERARCHY_STACK);
                stack[top++]=(entry){next,mask};
            }
        } else {
            assert(top+2<=BG_HIERARCHY_STACK);
            stack[top++]=(entry){n->second,mask};
            stack[top++]=(entry){n->first,mask};
        }
    }
}
#endif
