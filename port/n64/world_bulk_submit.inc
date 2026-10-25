/* Included only in the isolated libdragon rspq.c override. Immutable Tiny3D
 * geometry blocks contain no RDP mode/texture commands or nested calls.
 * Emit the identical CALL words in the identical order, then invalidate the
 * CPU RDP tracking state once for the complete uninterrupted geometry run.
 * RDP tracking is only CPU metadata; no queued commands are removed here. */
void bg_rspq_geometry_run(rspq_block_t *const *blocks,unsigned count) {
    assertf(!rspq_block && rspq_ctx!=&highpri,"Bulk geometry requires ordinary immediate submission");
    for(unsigned i=0;i<count;i++) {
        rspq_block_t *b=blocks[i];
        assertf(!b->rdp_block && b->nesting_level==0,"Bulk geometry block contract");
        rspq_int_write(RSPQ_CMD_CALL,PhysicalAddr(b->cmds),0);
    }
    if(count)__rdpq_block_run(NULL);
}
