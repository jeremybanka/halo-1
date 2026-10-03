#ifndef BG_MENU_QA_H
#define BG_MENU_QA_H
#include "menu.h"
/* Only linked by --menu-qa. Injects controller samples before the production
 * input/menu pipeline; it never directly mutates menu or gameplay state. */
void bg_menu_qa_input(bg_control_state raw[BG_PLAYERS],uint64_t now_us);
void bg_menu_qa_check(const bg_menu *menu,unsigned views,
    const bg_menu_result *result,const bg_input input[BG_PLAYERS]);
unsigned bg_menu_qa_step(void);
bool bg_menu_qa_done(void);
#endif
