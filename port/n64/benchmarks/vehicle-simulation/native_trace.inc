/* Diagnostic only. Hashes every completed tick, not wall-clock samples. */
static uint32_t query_hash=2166136261u,query_serial,query_shots;
static void query_add(const void*data,size_t size){const uint8_t*p=data;for(size_t i=0;i<size;i++){query_hash^=p[i];query_hash*=16777619u;}}
static void vehicle_query_trace(void){
#define QSAVE(x) query_add(&(x),sizeof(x))
 QSAVE(bg_players);QSAVE(bg_vehicles);QSAVE(bg_pve_actors);QSAVE(bg_vehicle_count);QSAVE(bg_pickups);QSAVE(bg_pickup_count);
 QSAVE(bg_event_count);query_add(bg_events,sizeof(*bg_events)*bg_event_count);QSAVE(pve_random);QSAVE(random_state);QSAVE(item_random);QSAVE(spawn_random);QSAVE(bg_ff);
 for(unsigned i=0;i<bg_event_count;i++)query_shots+=bg_events[i].kind==BG_EVENT_FIRE;
 for(unsigned i=0;i<BG_MAX_PROJECTILES;i++){const bg_projectile*q=bg_projectile_at(i);bool present=q!=NULL;QSAVE(present);if(q)query_add(q,sizeof(*q));}
#undef QSAVE
 if(++query_serial%30==0)debugf("QUERY_TRACE tick=%u hash=%08lx shots=%u\n",(unsigned)query_serial,(unsigned long)query_hash,(unsigned)query_shots);
}
