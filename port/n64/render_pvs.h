#ifndef BG_RENDER_PVS_H
#define BG_RENDER_PVS_H
#include <stdbool.h>
#include <stdint.h>
typedef struct {int32_t plane,back,front;} bg_pvs_node;
typedef struct {float v[4];} bg_pvs_plane;
typedef struct {
    const bg_pvs_node *nodes;
    const bg_pvs_plane *planes;
    const int16_t *leaf_clusters;
    const uint16_t *rows,*chunk_masks;
    unsigned node_count,plane_count,leaf_count,cluster_count,chunk_count;
    float normal_limit;
} bg_pvs_data;
/* Union the PVS of every leaf touched by the camera uncertainty sphere.
 * Invalid/solid/outside leaves and bounded traversal exhaustion fail open.
 * The caller preserves ordinary frustum culling and every retained draw's order. */
uint16_t bg_pvs_camera_mask(const bg_pvs_data *data,const float source_eye[3],float radius);
bool bg_pvs_keep_chunk(const bg_pvs_data *data,uint16_t camera_mask,unsigned chunk);
#ifdef BG_CHIRON_PVS
extern const bg_pvs_data bg_chiron_pvs;
#endif
#endif
