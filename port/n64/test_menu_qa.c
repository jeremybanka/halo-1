/* Execute the actual target QA script through the production menu/control
 * modules. The clock and game actions are simulated; no controller/rendering
 * code or game state is required. Assertions in menu_qa.c stay enabled. */
#include "menu_qa.h"
#include <assert.h>
#include <stdio.h>

int main(void){
    bg_menu menu;bg_menu_init(&menu,4);
    unsigned views=4,restarts=0,count_changes=0,gameplay_polls=0;
    unsigned visits[40]={0},last_step=0;
    uint64_t first_done=0;
    const uint64_t start=1234567;
    for(uint64_t now=start;now<=start+82000000;now+=2000){
        bg_control_state raw[BG_PLAYERS];bg_menu_input navigation[BG_PLAYERS];
        bg_input in[BG_PLAYERS]={0};
        bg_menu_qa_input(raw,now);
        unsigned step=bg_menu_qa_step();
        assert(step<40&&(step==last_step||step==last_step+1));
        if(step!=last_step)assert(now-start==(uint64_t)step*2000000);
        last_step=step;visits[step]++;
        bg_menu_inputs(&menu,raw,navigation);
        bg_menu_result result=bg_menu_update(&menu,navigation,views);
        if(result.action==BG_MENU_ACTION_PLAYER_COUNT){
            const unsigned expected[]={1,2,4};
            assert(count_changes<3&&result.player_count==expected[count_changes]);
            assert(menu.owner==0&&menu.open&&menu.page==BG_MENU_SETUP);
            views=result.player_count;count_changes++;
        }
        if(result.action==BG_MENU_ACTION_RESTART){
            restarts++;
            /* A game reset has no ownership of menu preferences. */
            assert(!menu.open&&views==4);
            for(unsigned p=0;p<BG_PLAYERS;p++)
                assert(menu.styles[p]==(p<3?BG_CONTROLS_XBOX:BG_CONTROLS_N64));
        }
        if(!result.consumed)for(unsigned p=0;p<views;p++)
            bg_controls_map(&in[p],&raw[p],menu.styles[p],false);
        bg_menu_qa_check(&menu,views,&result,in);
        if(step==27){
            gameplay_polls++;
            assert(!menu.open&&!result.consumed&&views==4);
            assert(in[0].forward==1&&in[0].fire&&in[1].strafe==1);
            assert(in[3].forward==.75f&&in[3].strafe==-1);
        }
        if(bg_menu_qa_done()&&!first_done)first_done=now;
        if(first_done){
            assert(step==39&&menu.open&&menu.owner==3&&menu.page==BG_MENU_CONTROLS);
            assert(result.action==BG_MENU_ACTION_NONE&&result.consumed);
        }
    }
    assert(bg_menu_qa_done()&&first_done==start+78000000);
    assert(restarts==1&&count_changes==3&&gameplay_polls==1000);
    for(unsigned step=0;step<39;step++)assert(visits[step]==1000);
    assert(visits[39]==2001); /* final PASS remains stable for four seconds */
    puts("PASS: actual menu QA, all 40 checkpoints at 2ms polls; 1/2/4 views, inactive ports, independent controls, restart and stable final PASS");
    return 0;
}
