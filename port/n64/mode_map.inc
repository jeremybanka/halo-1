/* Private objective metadata, loaded alongside one selected map. The old
 * geometry bank stays byte-identical, including renderer candidate banks. */
static bg_mode_map mode_map;
static void *mode_memory;
const bg_mode_map *bg_current_mode_map(void) { return mode_memory?&mode_map:NULL; }
static void unload_mode_map(void) {
    free(mode_memory); mode_memory=NULL; memset(&mode_map,0,sizeof(mode_map));
}
static uint32_t spawn_fingerprint(void) {
    uint32_t hash=2166136261u;
    for(unsigned i=0;i<bg_spawn_count;i++)for(unsigned j=0;j<5;j++) {
        uint32_t word; memcpy(&word,(const uint8_t *)&bg_spawns[i]+4*j,4);
        for(int shift=24;shift>=0;shift-=8)hash=(hash^((word>>shift)&255))*16777619u;
    }
    return hash;
}
static void load_mode_map(unsigned index) {
#ifdef N64
    if((unsigned)get_memory_size()<8*1024*1024)return;
#endif
    char path[512];
#ifdef N64
    snprintf(path,sizeof(path),"rom:/maps/%s.modes64",catalog[index].name);
#else
    const char *directory=getenv("BG_MODE_DIRECTORY");
    if(!directory)directory=getenv("BG_MAP_DIRECTORY");
    snprintf(path,sizeof(path),"%s/%s.modes64",directory?directory:"halo64-assets/generated/maps",catalog[index].name);
#endif
    FILE *f=fopen(path,"rb");
#ifdef N64
    assertf(f,"Missing multiplayer metadata: %s",path);
#endif
    if(!f)return; /* Older asset banks remain a valid Slayer-only fixture. */
    uint8_t header[32];
    assertf(fread(header,1,32,f)==32,"Mode bank header");
    unsigned bytes=be32(header+12),spawns=be32(header+16),markers=be32(header+20),items=be32(header+24);
    assertf(be32(header)==0x484d4d44&&be32(header+4)==2&&be32(header+8)==current.id,
            "Mode bank identity");
    assertf(spawns==bg_spawn_count&&spawns<=128&&markers<=512&&items<=128&&
            bytes==32+80+16*spawns+20*markers+28*items&&be32(header+28)==spawn_fingerprint(),
            "Mode bank layout/starts");
    mode_memory=malloc(bytes-32);assertf(mode_memory,"Mode bank RAM");
    assertf(fread(mode_memory,1,bytes-32,f)==bytes-32&&fgetc(f)==EOF,"Mode bank payload");
    fclose(f);
    uint8_t *p=mode_memory;
    mode_map.starts=(const int (*)[4])p;p+=80;
    mode_map.spawn_modes=(const uint32_t *)p;p+=4*spawns;
    mode_map.spawn_positions=(const float (*)[3])p;p+=12*spawns;
    mode_map.markers=(const bg_mode_marker *)p;p+=20*markers;
    mode_map.items=(const bg_mode_item *)p;
    mode_map.spawn_count=spawns;mode_map.marker_count=markers;mode_map.item_count=items;
    _Static_assert(sizeof(bg_mode_marker)==20&&sizeof(bg_mode_item)==28,"Mode bank ABI");
#ifndef __MIPSEB__
    p=mode_memory;
    for(unsigned j=0;j<80+16*spawns;j+=4)swap32(p+j);
    p+=80+16*spawns;
    for(unsigned j=0;j<markers;j++,p+=20){for(unsigned k=0;k<16;k+=4)swap32(p+k);swap16(p+16);swap16(p+18);}
    for(unsigned j=0;j<items;j++,p+=28){host_order(BG_MAP_ITEMS,p,1,24);swap32(p+24);}
#endif
    for(unsigned i=0;i<5;i++) {
        const int *s=mode_map.starts[i];
        assertf(s[0]>=0&&s[0]<BG_WEAPON_COUNT&&s[1]>=-1&&s[1]<BG_WEAPON_COUNT&&
                s[2]>=0&&s[2]<=4&&s[3]>=0&&s[3]<=4,"Mode starting equipment");
    }
    for(unsigned i=0;i<spawns;i++)assertf(!(mode_map.spawn_modes[i]&~31u),"Mode spawn mask");
    for(unsigned i=0;i<markers;i++) {
        const bg_mode_marker *m=&mode_map.markers[i];
        assertf(m->kind<=BG_MARK_VEHICLE&&m->id<64,"Mode marker type/id");
        if(m->kind==BG_MARK_FLAG)assertf(m->id<2,"CTF team");
        if(m->kind==BG_MARK_RACE)assertf(m->id<32,"Race checkpoint");
    }
    for(unsigned i=0;i<items;i++) {
        const bg_mode_item *m=&mode_map.items[i];
        assertf(m->modes&&!(m->modes&~31u)&&m->item.period&&m->item.kind[0]>=0&&
                m->item.kind[0]<=BG_PICK_CAMO&&m->item.kind[1]>=-1&&m->item.kind[1]<=BG_PICK_CAMO&&
                m->item.first_weight&&m->item.first_weight<=m->item.total_weight,"Mode item");
    }
    resident+=bytes-32;
}
