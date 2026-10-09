#include "combat_geometry.h"
#include "blam/vehicle_physics.h"
#include "terrain.h"
#include "movement.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
static float dot(const float*a,const float*b){return a[0]*b[0]+a[1]*b[1]+a[2]*b[2];}
static void cross(const float*a,const float*b,float*c){for(unsigned k=0;k<3;k++)c[k]=a[(k+1)%3]*b[(k+2)%3]-a[(k+2)%3]*b[(k+1)%3];}
/* Independent world-space plane/edge oracle, deliberately without a BVH. */
static float reference(const bg_vehicle*v,const float*o,const float*d){
 const bg_hit_mesh*m=bg_vehicle_collision_pose(v);float nearest=20;
 for(unsigned t=0;t<m->triangle_count;t++){
  float p[3][3],e[3][3],normal[3],delta[3];
  for(unsigned j=0;j<3;j++){float local[3];for(unsigned k=0;k<3;k++)local[k]=m->vertices[m->triangles[t][j]][k]/1024.f;bg_vehicle_transform(v,local,p[j]);}
  for(unsigned j=0;j<3;j++)for(unsigned k=0;k<3;k++)e[j][k]=p[(j+1)%3][k]-p[j][k];
  cross(e[0],e[1],normal);float den=dot(normal,d);if(fabsf(den)<1e-8f)continue;
  for(unsigned k=0;k<3;k++)delta[k]=p[0][k]-o[k];float hit=dot(delta,normal)/den;
  if(hit<0||hit>=nearest)continue;bool inside=true;
  for(unsigned j=0;j<3;j++){float side[3];for(unsigned k=0;k<3;k++)delta[k]=o[k]+hit*d[k]-p[j][k];cross(e[j],delta,side);if(dot(side,normal)<-1e-7f*dot(normal,normal))inside=false;}
  if(inside)nearest=hit;
 }return nearest;
}
static bool capsule_reference(const bg_vehicle*v,const bg_player*p){
 const bg_hit_mesh*m=bg_vehicle_collision_pose(v);
 for(unsigned t=0;t<m->triangle_count;t++){
  float points[3][3];bg_triangle tri={{points[0],points[1],points[2]}};
  for(unsigned j=0;j<3;j++){float local[3];for(unsigned a=0;a<3;a++)local[a]=m->vertices[m->triangles[t][j]][a]/1024.f;bg_vehicle_transform(v,local,points[j]);}
  float a[3],b[3];if(bg_capsule_triangle(p->pos,bg_body_height(p),bg_movement.radius,&tri,a,b)<bg_movement.radius*bg_movement.radius)return true;
 }
 return false;
}
/* Full per-vertex transform reference: no incremental masks, part matrices or
 * cache keys. Alternate models and change one articulated degree at a time. */
static void pose_reference(void){
 bg_vehicle vehicles[4]={{0}};unsigned checked=0;
 for(unsigned frame=0;frame<120;frame++)for(unsigned kind=0;kind<4;kind++){
  bg_vehicle*v=&vehicles[kind];v->kind=kind;
  switch(frame%5){case 0:v->turret_yaw=sinf(frame*.3f);break;case 1:v->turret_pitch=cosf(frame*.7f)*.6f;break;case 2:v->hatch=(frame%17)/16.f;break;case 3:v->hatch_closing=!v->hatch_closing;break;case 4:v->active=!v->active;break;}
  const bg_hit_mesh*source=&bg_vehicle_hit_meshes[kind],*actual=bg_vehicle_collision_pose(v);
  for(unsigned i=0;i<source->vertex_count;i++){
   const bg_hit_part*part=&source->parts[source->groups[i]];float p[3];for(unsigned a=0;a<3;a++)p[a]=source->vertices[i][a]/1024.f;
   if(part->kind==3){float x=p[0]-part->pivot[0],y=p[1]-part->pivot[1],angle=v->turret_pitch-v->pitch;
    p[0]=part->pivot[0]+cosf(angle)*x-sinf(angle)*y;p[1]=part->pivot[1]+sinf(angle)*x+cosf(angle)*y;}
   if(part->kind==2||part->kind==3){const float*q=source->parts[source->turret_part].pivot;float x=p[0]-q[0],z=p[2]-q[2];
    p[0]=q[0]+cosf(v->turret_yaw)*x+sinf(v->turret_yaw)*z;p[2]=q[2]-sinf(v->turret_yaw)*x+cosf(v->turret_yaw)*z;}
   if(part->kind==4&&v->active){const bg_hit_hatch*h=&bg_hit_hatches[kind==BG_V_BANSHEE][v->hatch_closing];float phase=v->hatch*(h->count-1),out[3]={0};unsigned a=phase,b=a+1<h->count?a+1:a;float weight=phase-a;
    for(unsigned k=0;k<3;k++)for(unsigned j=0;j<4;j++)out[k]+=(h->frames[a][j][k]*(1-weight)+h->frames[b][j][k]*weight)*(j?p[j-1]:1)/4096.f;
    for(unsigned k=0;k<3;k++)p[k]=out[k];}
   for(unsigned a=0;a<3;a++)assert(fabsf(actual->vertices[i][a]-p[a]*1024)<=1.01f);
   checked++;
  }
 }
 printf("Partial collision refits: %u vertices agree with full joint/hatch transforms\n",checked);
}
int main(void){
 pose_reference();
 unsigned hits=0,misses=0;
 for(unsigned kind=0;kind<4;kind++)for(unsigned angle=0;angle<3;angle++){
  bg_vehicle v={.kind=kind,.yaw=angle*.7f,.pitch=angle*.2f,.turret_yaw=angle*.8f,.turret_pitch=angle*.3f,.hatch=angle*.4f,.active=true,.pos={2,3,4}};
  if(angle){
   const float f[3]={1,0,0},u[3]={0,1,0};bg_vehicle_transform(&v,f,v.forward);bg_vehicle_transform(&v,u,v.up);
   for(unsigned k=0;k<3;k++){v.forward[k]-=v.pos[k];v.up[k]-=v.pos[k];}v.physics_valid=true;
  }
  for(unsigned i=0;i<200;i++){
   bg_player p={.pos={2+2.5f*sinf(i*1.231f),3+1.5f*cosf(i*.517f),4+2.5f*cosf(i*1.217f)},.crouch_amount=(i%3)*.5f};
   assert(bg_vehicle_contacts_player(&v,&p)==capsule_reference(&v,&p));
  }
  for(unsigned axis=0;axis<3;axis++)for(int x=-9;x<=9;x++)for(int y=-9;y<=9;y++){
   float local[3]={0},end[3],o[3],d[3];local[axis]=-4;local[(axis+1)%3]=x*.17391f+.01329f;local[(axis+2)%3]=y*.17173f+.02191f;
   bg_vehicle_transform(&v,local,o);local[axis]=4;bg_vehicle_transform(&v,local,end);
   for(unsigned k=0;k<3;k++)d[k]=(end[k]-o[k])/8;
   float expected=reference(&v,o,d),actual=bg_vehicle_hit_ray(&v,o,d,20);
   if(fabsf(expected-actual)>.001f)fprintf(stderr,"kind%u axis%u expected%f actual%f\n",kind,axis,expected,actual);
   assert(fabsf(expected-actual)<.001f);if(actual<20)hits++;else misses++;
  }
 }
 assert(hits&&misses);printf("PASS: collision BVH matches 2400 exhaustive capsule checks and original triangle ray oracle (%u hits, %u misses, four hulls and rotated poses)\n",hits,misses);
}
