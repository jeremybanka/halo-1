/* Exercise the retained solver against retail tags and map geometry, including
 * private contact state. This TU substitutes no physics/world implementation. */
#include "vehicle_physics.c"
#include "vehicle_pair_reference.c"
bg_vehicle bg_vehicles[BG_MAX_VEHICLES];
bg_player bg_players[BG_PLAYERS];
unsigned bg_vehicle_count;
extern bool reference_segment(const float*,const float*,bool,float*);
static bg_vehicle *setup(int kind,float height){
 memset(bg_vehicles,0,sizeof(bg_vehicles));memset(bg_players,0,sizeof(bg_players));bg_vehicle_count=1;
 bg_vehicle*v=bg_vehicles;v->active=true;v->kind=kind;v->occupants[0]=0;v->occupants[1]=v->occupants[2]=-1;v->pos[1]=height;v->pos[2]=4;
 bg_vehicle_physics_prepare();return v;
}
static void check_axes(const bg_vehicle*v){
 float ff=0,uu=0,fu=0;
 for(int a=0;a<3;a++){assert(isfinite(v->pos[a])&&isfinite(v->velocity[a])&&isfinite(v->angular_velocity[a]));ff+=v->forward[a]*v->forward[a];uu+=v->up[a]*v->up[a];fu+=v->forward[a]*v->up[a];}
 assert(fabsf(ff-1)<.003f&&fabsf(uu-1)<.003f&&fabsf(fu)<.003f);assert(isfinite(v->wheel_phase));
}
static void step(unsigned count,bg_input in){for(unsigned i=0;i<count;i++){bg_vehicle_physics_step(0,&in);check_axes(bg_vehicles);}}
static uint32_t random_seed=0xC064;
static float random_float(float lo,float hi){random_seed=random_seed*1664525u+1013904223u;return lo+(hi-lo)*(random_seed>>8)*(1.f/16777216);}
static void test_world_bank(void){
 /* Independently compare every packed scalar against the compiler's typed
  * arrays. This catches offset/stride/endianness drift in the N64-only loader. */
 const void*blocks[]={bg_vehicle_bsp.bsp3d.planes.address,bg_vehicle_bsp.surfaces.address,
  bg_vehicle_bsp.edges.address,bg_vehicle_bsp.vertices.address,bg_vehicle_bvh,
  bg_vehicle_surface_bounds,bg_vehicle_surface_indices};
 static const unsigned widths[7][8]={{4,4,4,4},{4,4,1,1,2},{2,2,2,2,2,2},
  {4,4,4,4},{2,2,2,2,2,2,2,2},{2,2,2,2,2,2},{2}};
 FILE*f=fopen("build/n64/frontend-files/vehicle-world.bin","rb");assert(f);
 for(unsigned b=0;b<7;b++){
  assert((unsigned)ftell(f)==bg_vehicle_world_layout[b][0]);const uint8_t*p=blocks[b];
  for(unsigned row=0;row<bg_vehicle_world_layout[b][1];row++)for(unsigned col=0;col<8&&widths[b][col];col++){
   unsigned width=widths[b][col];uint32_t got=0,want=0;
   for(unsigned j=0;j<width;j++){int byte=fgetc(f);assert(byte!=EOF);got=(got<<8)|(unsigned)byte;}
   if(width==4)memcpy(&want,p,4);
   else if(width==2){uint16_t v;memcpy(&v,p,2);want=v;}
   else want=*p;
   assert(got==want);p+=width;
  }
 }
 assert((unsigned)ftell(f)==bg_vehicle_world_bytes&&fgetc(f)==EOF);fclose(f);
 printf("N64 world bank: %u bytes match typed source geometry bit-for-bit\n",bg_vehicle_world_bytes);
}
static void test_pair_equivalence(void){
 unsigned collisions=0;
 for(unsigned j=0;j<5000;j++){
  setup(j%4,20);bg_vehicle_count=2;bg_vehicles[1]=bg_vehicles[0];
  bg_vehicles[1].kind=(j/4)%4;bg_vehicles[1].physics_valid=false;
  for(int b=0;b<2;b++){
   bg_vehicle*v=&bg_vehicles[b];v->physics_valid=false;
   for(int a=0;a<3;a++)v->pos[a]+=random_float(-2,2);
   v->yaw=random_float(-3.14f,3.14f);v->pitch=random_float(-1.55f,1.55f);
  }
  bg_vehicle_physics_prepare();
  struct vehicle_datum saved[2],expected[2];memcpy(saved,native,sizeof(saved));
  struct physics_instance a,b;physics_instance_new(&a,0);physics_instance_new(&b,1);
  bool ref=physics_compute_vehicle_collision_reference(&a,&b);memcpy(expected,native,sizeof(expected));
  memcpy(native,saved,sizeof(saved));bool actual=physics_compute_vehicle_collision(&a,&b);
  assert(ref==actual&&!memcmp(expected,native,sizeof(expected)));collisions+=actual;
 }
 printf("Vehicle-pair optimization: 5000 bit-exact original comparisons, %u contacts\n",collisions);
}
static void test_segments(void){
 unsigned hits=0;
 for(unsigned j=0;j<20000;j++){
  /* Above-ground suspension rays and short swept contacts on every original
   * face. Start just outside a convex polygon's center, cross its plane. */
  unsigned si=j%(unsigned)bg_vehicle_bsp.surfaces.count;
  const struct collision_surface*s=TAG_BLOCK_GET_ELEMENT(&bg_vehicle_bsp.surfaces,si,struct collision_surface);
  real_plane3d plane;bsp3d_get_plane_from_designator(&bg_vehicle_bsp.bsp3d,s->plane_designator,&plane);
  real_point3d points[8],p={0};int count=collision_surface_polygon(&bg_vehicle_bsp,si,points);
  for(int k=0;k<count;k++)for(int a=0;a<3;a++)p.n[a]+=points[k].n[a]/count;
  float distance=random_float(.01f,.5f);real_vector3d d;
  for(int a=0;a<3;a++){p.n[a]+=plane.n.n[a]*distance;d.n[a]=-plane.n.n[a]*distance*2;}
  struct collision_result hit;float expected=1;
  bool a=collision_test_vector(1,&p,&d,-1,&hit),b=reference_segment(p.n,d.n,false,&expected);
  if(a!=b||(a&&fabsf(hit.t-expected)>.003f)){fprintf(stderr,"surface %u BVH %d %.8f BSP %d %.8f\n",si,a,hit.t,b,expected);assert(false);}
  hits+=a;
 }
 printf("Original BSP oracle: 20000 contact sweeps, %u hits\n",hits);
 unsigned misses=0;
 for(unsigned j=0;j<10000;j++){
  real_point3d p={.n={random_float(35,110),random_float(-165,-70),random_float(15,40)}};
  real_vector3d d={.n={random_float(-.6f,.6f),random_float(-.6f,.6f),random_float(-1,.3f)}};
  struct collision_result hit;float expected=1;
  bool a=collision_test_vector(1,&p,&d,-1,&hit),b=reference_segment(p.n,d.n,false,&expected);
  if(a!=b||(a&&fabsf(hit.t-expected)>.003f)){fprintf(stderr,"random sweep %u BVH %d %.8f BSP %d %.8f\n",j,a,hit.t,b,expected);assert(false);}
  misses+=!a;
 }
 assert(misses>9000);printf("Original BSP oracle: 10000 short airborne sweeps, %u misses\n",misses);
}
int main(void){
 _Static_assert(sizeof(struct mass_point_definition)==128,"Xbox mass-point stride");
 _Static_assert(sizeof(struct physics_mass_point_definition)==128,"vehicle mass-point view");
 _Static_assert(sizeof(struct powered_mass_point_definition)==128,"Xbox powered-point stride");
 test_world_bank();
 test_segments();
 test_pair_equivalence();
 for(int kind=0;kind<4;kind++){
  bg_vehicle*v=setup(kind,1);step(90,(bg_input){0});float start=v->pos[0];
  if(kind==BG_V_GHOST)assert(v->pos[1]>.4f&&native[0].vehicle.hover>.8f);
  bg_players[0].pitch=kind==BG_V_BANSHEE?.3f:0;
  step(90,(bg_input){.forward=1});assert(v->pos[0]>start+3&&v->speed>3);
  if(kind==BG_V_BANSHEE)assert(v->pos[1]>3);
  float yaw=v->yaw;bg_players[0].yaw=.8f;step(1,(bg_input){.forward=1});assert(fabsf(v->yaw-yaw)<.1f);
  step(59,(bg_input){.forward=1});assert(v->yaw>.3f);
  printf("Vehicle %d: drive/steer, pose and contact checks passed\n",kind);
 }
 bg_vehicle*v=setup(BG_V_WARTHOG,20);v->velocity[2]=3;v->physics_valid=false;bg_vehicle_physics_prepare();
 bg_players[0].yaw=1.5f;step(30,(bg_input){.forward=1});
 printf("airtest yaw %.6f lateral %.6f height %.6f\n",v->yaw,v->velocity[2],v->pos[1]);
 assert(fabsf(v->yaw)<.05f&&v->velocity[2]>2.5f&&v->pos[1]<19);
 printf("Airborne Warthog: lateral velocity %.4f, yaw %.6f\n",v->velocity[2],v->yaw);
 v=setup(BG_V_WARTHOG,2);float rebound=0;bool touched=false;
 for(int i=0;i<150;i++){step(1,(bg_input){0});touched|=native[0].vehicle.on_ground_ticks>0;if(touched)rebound=MAX(rebound,v->velocity[1]);}
 assert(touched&&rebound>.1f&&v->up[1]>.9f);printf("Suspension landing: rebound %.4f units/s\n",rebound);
 v=setup(BG_V_WARTHOG,20);v->angular_velocity[0]=3;v->physics_valid=false;bg_vehicle_physics_prepare();step(30,(bg_input){0});assert(v->up[1]<-.5f);
 float local[3]={0,.5f,.3f},world[3];bg_vehicle_transform(v,local,world);assert(world[1]<v->pos[1]);
 bg_vehicle_physics_flip(0,(float[]){0,20,3});step(30,(bg_input){0});assert(v->up[1]>.5f);puts("Rollover, full-pose seat transform and original flip torque passed");
 /* Reset and reused slots must not inherit the previous body's spin. */
 v=setup(BG_V_SCORPION,20);step(10,(bg_input){0});assert(v->up[1]>.999f);
 v=setup(BG_V_WARTHOG,20);float blast[3]={v->pos[0],v->pos[1],v->pos[2]+.5f};
 bg_vehicle_physics_explosion(0,blast,BG_P_FRAG);assert(v->velocity[2]<-1&&fabsf(v->angular_velocity[0])>1);step(1,(bg_input){0});
 puts("Original grenade acceleration and angular kick passed");
 /* A moving chassis striking a sleeping chassis wakes it and transfers
  * equal/opposite collision forces; gravity is outside this isolated call. */
 v=setup(BG_V_WARTHOG,20);bg_vehicle_count=2;bg_vehicles[1]=*v;
 bg_vehicles[1].pos[0]+=1.5f;bg_vehicles[1].occupants[0]=-1;bg_vehicles[1].physics_valid=false;
 bg_vehicle_physics_prepare();native[0].object.translational_velocity.i=.1f;
 native[1].object.flags|=FLAG(_object_at_rest_bit);
 struct physics_instance a,b;physics_instance_new(&a,0);physics_instance_new(&b,1);
 physics_compute_vehicle_collision(&a,&b);
 assert(!TEST_FLAG(native[1].object.flags,_object_at_rest_bit));
 assert(magnitude_squared3d(&native[0].vehicle.collision_force)>0);
 for(int axis=0;axis<3;axis++)assert(fabsf(native[0].vehicle.collision_force.n[axis]+native[1].vehicle.collision_force.n[axis])<.01f);
 puts("Original vehicle-pair impulse transfer and wakeup passed");
 puts("PASS native vehicle physics");
}
