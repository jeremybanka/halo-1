#ifndef BG_FRONTEND_QA_H
#define BG_FRONTEND_QA_H
#include "frontend.h"
void bg_front_qa_input(const bg_frontend*f,bg_control_state raw[4],uint64_t now);
void bg_front_qa_tick(bg_input in[4],float seconds);
unsigned bg_front_qa_step(void);
unsigned bg_front_qa_steps(void);
bool bg_front_qa_done(void);
#endif
