/* Native readback of both fight choices/countdowns, only in scripted shell QA. */
static void firefight_menu_photo(surface_t*screen,const bg_frontend*f){
    static unsigned exported;
    if(!f->firefight||f->fight>=BG_FF_FIGHTS||
       (f->page!=BG_FRONT_FIGHT&&f->page!=BG_FRONT_PREGAME))return;
    unsigned photo=f->fight*2+(f->page==BG_FRONT_PREGAME);
    if(exported&(1u<<photo))return;
    exported|=1u<<photo;rdpq_detach_wait();
    assertf(surface_get_format(screen)==FMT_RGBA16&&screen->width==320&&screen->height==240,"Menu photo format");
    debugf("FF_PHOTO_BEGIN tick=%u width=320 height=240 format=RGBA5551\n",photo);
    static const char digits[]="0123456789abcdef";
    for(unsigned first=0;first<320*240;first+=64){
        char hex[257];
        for(unsigned j=0;j<64;j++){
            unsigned n=first+j;const uint16_t*row=(const uint16_t*)((const uint8_t*)UncachedAddr(screen->buffer)+(n/320)*screen->stride);
            unsigned value=row[n%320];for(unsigned k=0;k<4;k++)hex[j*4+k]=digits[(value>>(12-k*4))&15];
        }
        hex[256]=0;debugf("FF_PIX %u %s\n",first,hex);
    }
    debugf("FF_PHOTO_END\n");rdpq_attach(screen,NULL);
}
