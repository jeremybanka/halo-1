#ifndef BG_RESIDENCY_H
#define BG_RESIDENCY_H
#include <stdbool.h>
/* Explicit application transitions, not an allocator or eviction policy.
 * Scene release functions retire RSP readers before freeing uncached buffers.
 * The menu backdrop has a separate, existing frontend_draw lifetime. */
void bg_residency_menu(bool release_bodies);
void bg_residency_quit_confirmation(void);
/* Reserve the existing large working sets before map/body allocations. */
void bg_residency_prepare_match(unsigned players, unsigned map);
void bg_residency_gameplay(void);
#endif
