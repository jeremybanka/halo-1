#include "render_pvs.h"
#include <string.h>
static bool finite_value(float value){
    uint32_t bits;memcpy(&bits,&value,4);return (bits&0x7f800000u)!=0x7f800000u;
}
uint16_t bg_pvs_camera_mask(const bg_pvs_data*d,const float eye[3],float radius){
    if(!d||!d->cluster_count||d->cluster_count>16)return UINT16_MAX;
    uint16_t all=(uint16_t)((1u<<d->cluster_count)-1u),visible=0;
    if(!d->node_count||!finite_value(radius)||radius<0)return all;
    for(unsigned a=0;a<3;a++)if(!finite_value(eye[a]))return all;
    int32_t stack[128]={0};unsigned pending=1,visited=0;
    /* More than 512 branches is an uncertainty case, never permission to hide. */
    float margin=radius*d->normal_limit+.005f;
    while(pending){
        int32_t index=stack[--pending];
        if(++visited>512)return all;
        if(index<0){
            unsigned leaf=(uint32_t)index&0x7fffffffu;
            if(index==-1||leaf>=d->leaf_count)return all;
            int cluster=d->leaf_clusters[leaf];
            if(cluster<0||(unsigned)cluster>=d->cluster_count)return all;
            visible|=d->rows[cluster];
            if(visible==all)return all;
            continue;
        }
        if((unsigned)index>=d->node_count)return all;
        const bg_pvs_node*n=&d->nodes[index];
        if(n->plane<0||(unsigned)n->plane>=d->plane_count)return all;
        const float*p=d->planes[n->plane].v;
        float distance=((p[0]*eye[0]+p[1]*eye[1])+p[2]*eye[2])-p[3];
        if(!finite_value(distance))return all;
        if(distance<=margin){if(pending==128)return all;stack[pending++]=n->back;}
        if(distance>=-margin){if(pending==128)return all;stack[pending++]=n->front;}
    }
    return visible?visible:all;
}
bool bg_pvs_keep_chunk(const bg_pvs_data*d,uint16_t camera_mask,unsigned chunk){
    return !d||chunk>=d->chunk_count||!d->chunk_masks[chunk]||
           (d->chunk_masks[chunk]&camera_mask)!=0;
}
