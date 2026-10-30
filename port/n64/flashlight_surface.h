/* Lamp queries use rendered triangles. Original collision surfaces need
 * not coincide with a simplified terrain mesh, and produce broken decals.
 * Gather local opaque batches once per lamp; all rays share that list. */
static uint16_t flashlight_candidates[BG_WORLD_CHUNK_CAPACITY];
static unsigned flashlight_candidate_count,flashlight_index_base,flashlight_index_stride;
static void flashlight_gather(const float eye[3]) {
    flashlight_candidate_count=0;
    int16_t encoded[2]={0,1};t3d_indexbuffer_convert(encoded,2);
    flashlight_index_base=(uint16_t)encoded[0]&0x3fff;
    flashlight_index_stride=((uint16_t)encoded[1]&0x3fff)-flashlight_index_base;
    for(unsigned b=0;b<bg_chunk_count;b++) {
        const bg_chunk *chunk=&bg_chunks[b];
        if(bg_texture_overlay[chunk->material])continue;
        bool nearby=true;
        for(unsigned a=0;a<3;a++)
            if(chunk->bounds[a]/BG_SCALE>eye[a]+6 || chunk->bounds[a+3]/BG_SCALE<eye[a]-6)nearby=false;
        if(nearby)flashlight_candidates[flashlight_candidate_count++]=b;
    }
}
static float flashlight_raycast(const float eye[3],const float ray[3],float normal[3]) {
    float best=6;
    for(unsigned i=0;i<flashlight_candidate_count;i++) {
        const bg_chunk *chunk=&bg_chunks[flashlight_candidates[i]];
        for(unsigned tri=0;tri<chunk->index_count;tri+=3) {
        float corners[3][3];
        for(unsigned v=0;v<3;v++) {
            unsigned encoded=(uint16_t)bg_chunk_indices[chunk->index_first+tri+v]&0x3fff;
            unsigned index=(encoded-flashlight_index_base)/flashlight_index_stride;
            assertf(index<chunk->count,"Flashlight render index");
            int16_t *position=t3d_vertbuffer_get_pos(bg_vertices+chunk->first/2,index);
            for(unsigned k=0;k<3;k++)corners[v][k]=position[k]/BG_TERRAIN_SCALE;
        }
        const bg_triangle triangle={{corners[0],corners[1],corners[2]}},*t=&triangle;
        float e[3],f[3],o[3],q[3],r[3];
        for(unsigned a=0;a<3;a++){e[a]=t->p[1][a]-t->p[0][a];f[a]=t->p[2][a]-t->p[0][a];o[a]=eye[a]-t->p[0][a];}
        q[0]=ray[1]*f[2]-ray[2]*f[1];q[1]=ray[2]*f[0]-ray[0]*f[2];q[2]=ray[0]*f[1]-ray[1]*f[0];
        float det=e[0]*q[0]+e[1]*q[1]+e[2]*q[2];if(fabsf(det)<1e-8f)continue;
        float u=(o[0]*q[0]+o[1]*q[1]+o[2]*q[2])/det;if(u<0||u>1)continue;
        r[0]=o[1]*e[2]-o[2]*e[1];r[1]=o[2]*e[0]-o[0]*e[2];r[2]=o[0]*e[1]-o[1]*e[0];
        float v=(ray[0]*r[0]+ray[1]*r[1]+ray[2]*r[2])/det;if(v<0||u+v>1)continue;
        float d=(f[0]*r[0]+f[1]*r[1]+f[2]*r[2])/det;if(d<.003f||d>=best)continue;
        best=d;normal[0]=e[1]*f[2]-e[2]*f[1];normal[1]=e[2]*f[0]-e[0]*f[2];normal[2]=e[0]*f[1]-e[1]*f[0];
        float length=sqrtf(normal[0]*normal[0]+normal[1]*normal[1]+normal[2]*normal[2]);
        float sign=(normal[0]*ray[0]+normal[1]*ray[1]+normal[2]*ray[2])>0?-1:1;
        for(unsigned a=0;a<3;a++)normal[a]*=sign/length;
    }
    }
    return best;
}
