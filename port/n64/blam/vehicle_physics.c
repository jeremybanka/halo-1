/* Native CE solvers with bounded object, tag, and Blood Gulch world adapters. */
#include "vehicle_physics.h"
#include "vehicle_private.h"
#include "../telemetry.h"
#include "../word_round.h"
#include "vehicle_profile.h"
#include <stdlib.h>
#ifdef N64
#include <libdragon.h>
#endif
static struct vehicle_datum native[BG_MAX_VEHICLES];
static float body_radius[BG_VEHICLE_COUNT];
static float vehicle_steering[BG_MAX_VEHICLES];
struct surface_candidates {int32_t bounds[6];uint16_t ids[64],count;bool valid;};
struct vehicle_workspace {
 struct surface_candidates candidates[16];
 struct mass_point_datum contact[22];
 struct powered_mass_point_datum power[2];
 struct collision_feature_list features;
 uint8_t *stamps[2]; /* exact edge/vertex counts, one owned allocation */
 struct {struct collision_prism prism;int32_t surface;bool valid;} prisms[32];
 struct {struct collision_cylinder cylinder;int32_t edge;bool valid,produced;} cylinders[64];
};
#ifdef N64
static struct vehicle_workspace *vehicle_workspace;
#else
static struct vehicle_workspace host_workspace;
static struct vehicle_workspace *vehicle_workspace=&host_workspace;
#endif
static const real_vector3d zero3={.n={0,0,0}},up3={.n={0,0,1}},down3={.n={0,0,-1}},forward3={.n={1,0,0}};
static const real_vector2d zero2={.n={0,0}};
static const real_quaternion identityq={.v={.n={0,0,0}},.w=1};
static const real_vector3d *global_zero_vector3d=&zero3,*global_up3d=&up3,*global_down3d=&down3,*global_forward3d=&forward3;
static const real_vector2d *global_zero_vector2d=&zero2;
static const real_quaternion *global_identity_quaternion=&identityq;
static const real global_gravity=.0035651792f,global_physics_collision_depth=.2f;
static const real_plane3d depths_of_hell={.n={.n={0,0,1}},.d=-256};
static const boolean debug_physics_disable_penetration_freeze=FALSE;
static struct vehicle_datum *vehicle_datum_get(int32_t i){assert(i>=0&&i<(int32_t)bg_vehicle_count);return &native[i];}
static struct object_datum *object_get(int32_t i){return (struct object_datum*)vehicle_datum_get(i);}
static struct vehicle_definition *vehicle_specific_definition_get(int32_t i){assert(i>=0&&i<4);return (struct vehicle_definition*)&bg_vehicle_drive_defs[i];}
static struct unit_definition *vehicle_definition_get(int32_t i){return &vehicle_specific_definition_get(i)->unit;}
static struct object_definition *object_definition_get(int32_t i){return (struct object_definition*)vehicle_definition_get(i);}
static struct physics_definition *physics_definition_get(int32_t i){assert(i>=0&&i<4);return (struct physics_definition*)&bg_vehicle_physics_defs[i];}
static void object_get_origin(int32_t i,real_point3d*p){*p=native[i].object.position;}
static void object_get_orientation(int32_t i,real_vector3d*f,real_vector3d*u){*f=native[i].object.forward;*u=native[i].object.up;}
static void object_set_position(int32_t i,const real_point3d*p,const real_vector3d*f,const real_vector3d*u){native[i].object.position=*p;native[i].object.forward=*f;native[i].object.up=*u;}
/* Blood Gulch has no water/media volumes. No generic water stub is exposed. */
static float scenario_location_water_depth(const struct location*l,const real_point3d*p){(void)l;(void)p;return 0;}
static void scenario_location_from_point(struct location*l,const real_point3d*p){(void)p;memset(l,0,sizeof(*l));}
static const struct material_definition *scenario_material_definition_get(int i){return &bg_vehicle_materials[i<0?0:i];}
static int16_t get_material_type(int32_t object,int16_t material){(void)object;return material;}
static int object_get_type(int32_t i){(void)i;return 0;}
static void object_deplete_shield(int32_t i){(void)i;/* static world contacts never have an object handle */}
static boolean unit_driven_by_ai(int32_t i){(void)i;return FALSE;}
static void create_ghost_effect(int32_t i){(void)i;/* rendering/audio stays in the demake event layer */}
static boolean collision_get_features_in_sphere(uint32_t flags,const real_point3d*p,real radius,real height,real width,int32_t ignore,struct collision_feature_list*out);
static boolean collision_test_vector(uint32_t flags,const real_point3d*p,const real_vector3d*d,int32_t ignore,struct collision_result*out);
static void physics_compute_unit_collisions(int32_t i);
#define global_projection3d_mappings vehicle_projection3d_mappings
#if defined(N64) && defined(BG_PROFILE)
bg_vehicle_metrics bg_vehicle_profile;
#include "vehicle_profile.c"
#else
#include "vehicle_original.c"
#endif

static void stamps_load(void){
 unsigned edges=bg_vehicle_bsp.edges.count,vertices=bg_vehicle_bsp.vertices.count;
 assert(edges&&vertices);
 uint8_t*storage=calloc(edges+vertices,1);assert(storage);
 vehicle_workspace->stamps[0]=storage;vehicle_workspace->stamps[1]=storage+edges;
}

/* Typed floats/topology have exactly the same big-endian representation as
 * the prior static N64 arrays. Only their residency changes at menu boundaries. */
#ifdef N64
static void *world_blocks[7];
static bool world_loaded;
static void world_load(void){
 if(world_loaded)return;
 vehicle_workspace=calloc(1,sizeof(*vehicle_workspace));assertf(vehicle_workspace,"Vehicle workspace RAM");
 FILE*f=fopen("rom:/vehicle-world.bin","rb");assertf(f,"Vehicle world bank");
 for(unsigned i=0;i<7;i++){
  unsigned end=i<6?bg_vehicle_world_layout[i+1][0]:bg_vehicle_world_bytes;
  unsigned size=end-bg_vehicle_world_layout[i][0];
  world_blocks[i]=malloc(size);assertf(world_blocks[i],"Vehicle world RAM block %u (%u bytes)",i,size);
  assertf(fread(world_blocks[i],1,size,f)==size,"Vehicle world read");
 }
 fclose(f);
 bg_vehicle_bsp=(struct collision_bsp){.bsp3d={.planes={bg_vehicle_world_layout[0][1],world_blocks[0],NULL}},
  .surfaces={bg_vehicle_world_layout[1][1],world_blocks[1],NULL},.edges={bg_vehicle_world_layout[2][1],world_blocks[2],NULL},
  .vertices={bg_vehicle_world_layout[3][1],world_blocks[3],NULL}};
 bg_vehicle_bvh=world_blocks[4];bg_vehicle_surface_bounds=world_blocks[5];bg_vehicle_surface_indices=world_blocks[6];
 stamps_load();world_loaded=true;
}
void bg_vehicle_world_release(void){
 if(!world_loaded)return;
 for(unsigned i=0;i<7;i++){free(world_blocks[i]);world_blocks[i]=NULL;}
 free(vehicle_workspace->stamps[0]);free(vehicle_workspace);vehicle_workspace=NULL;
 world_loaded=false;memset(&bg_vehicle_bsp,0,sizeof(bg_vehicle_bsp));
 bg_vehicle_bvh=NULL;bg_vehicle_surface_bounds=NULL;bg_vehicle_surface_indices=NULL;
}
#else
static void world_load(void){if(!vehicle_workspace->stamps[0])stamps_load();}
void bg_vehicle_world_release(void){}
#endif

/* The BVH only selects candidates; all contacts use original feature tests. */
static uint8_t stamp;
static unsigned next_stamp(void){
 if(!vehicle_workspace||!vehicle_workspace->stamps[0])world_load();
 if(++stamp==0){memset(vehicle_workspace->stamps[0],0,(unsigned)bg_vehicle_bsp.edges.count+(unsigned)bg_vehicle_bsp.vertices.count);stamp=1;}
 return stamp;
}
struct surface_query {uint16_t stack[32],pending,first,remaining;int32_t bounds[6];const struct surface_candidates*cached;};
static void query_begin_raw(struct surface_query*q,const float lo[3],const float hi[3]){
 q->cached=NULL;
 q->pending=1;q->stack[0]=0;q->remaining=0;
 for(int a=0;a<3;a++){q->bounds[a]=bg_floor_word(lo[a]*64);q->bounds[a+3]=bg_ceil_word(hi[a]*64);}
}
static bool overlaps(const int32_t a[6],const int16_t b[6]){
 return a[3]>=b[0]&&a[0]<=b[3]&&a[4]>=b[1]&&a[1]<=b[4]&&a[5]>=b[2]&&a[2]<=b[5];
}
static int query_next_raw(struct surface_query*q){
 for(;;){
  while(q->remaining){q->remaining--;unsigned si=bg_vehicle_surface_indices[q->first++];if(overlaps(q->bounds,bg_vehicle_surface_bounds[si]))return si;}
  if(!q->pending)return -1;
  unsigned ni=q->stack[--q->pending];const struct vehicle_bvh_node*n=&bg_vehicle_bvh[ni];
  if(!overlaps(q->bounds,n->bounds))continue;
  if(n->count){q->first=n->first;q->remaining=n->count;}
  else{assert(q->pending+2<=32);q->stack[q->pending++]=n->first;q->stack[q->pending++]=ni+1;}
 }
}
/* Cache immutable candidate indices, never contacts or impulses. Small
 * mass-point/suspension queries share a two-unit cell; short camera fans
 * use proportionally larger cells. Exact bounds filtering
 * and original BVH order are retained; overflow takes the uncached path. */
static void query_begin(struct surface_query*q,const float lo[3],const float hi[3]){
 query_begin_raw(q,lo,hi);
 float extent=MAX(hi[0]-lo[0],MAX(hi[1]-lo[1],hi[2]-lo[2]));if(extent>8){BG_COUNT(BG_COUNT_WORLD_BYPASS,1);return;}
 int32_t half=extent>4?4:extent>2?2:1,cell[3];uint32_t hash=half-1;
 for(unsigned a=0;a<3;a++){cell[a]=bg_floor_word((lo[a]+hi[a])*(.25f/half));hash=hash*31u+(uint32_t)cell[a];}
 struct surface_candidates*c=&vehicle_workspace->candidates[(hash^(hash>>4))&15u];
 int32_t bounds[6];for(unsigned a=0;a<3;a++){bounds[a]=(cell[a]*2-1)*half*64;bounds[a+3]=(cell[a]*2+3)*half*64;}
 if(!c->valid||memcmp(c->bounds,bounds,sizeof(bounds))){
  BG_COUNT(BG_COUNT_WORLD_MISS,1);
  struct surface_query collect=*q;memcpy(collect.bounds,bounds,sizeof(bounds));
  c->count=0;c->valid=false;int id;
  while((id=query_next_raw(&collect))>=0){if(c->count==64){BG_COUNT(BG_COUNT_WORLD_OVERFLOW,1);return;}c->ids[c->count++]=id;}
  memcpy(c->bounds,bounds,sizeof(bounds));c->valid=true;
 }else BG_COUNT(BG_COUNT_WORLD_HIT,1);
 q->cached=c;q->first=0;q->remaining=c->count;
}
static int query_next(struct surface_query*q){
 if(!q->cached)return query_next_raw(q);
 while(q->remaining){q->remaining--;unsigned id=q->cached->ids[q->first++];if(overlaps(q->bounds,bg_vehicle_surface_bounds[id]))return id;}
 return -1;
}
/* Immutable zero-height polygon projections are shared by contacts, sweeps
 * and camera rays. The constructor retains original edge order, projection
 * helpers and feature metadata; width is supplied only when copying a contact. */
static const struct collision_prism*cached_polygon(const struct collision_bsp*b,int si){
 unsigned slot=(unsigned)si%32;
 struct collision_prism*p=&vehicle_workspace->prisms[slot].prism;
 if(vehicle_workspace->prisms[slot].valid&&vehicle_workspace->prisms[slot].surface==si){BG_COUNT(BG_COUNT_PRISM_HIT,1);return p;}
 BG_COUNT(BG_COUNT_PRISM_MISS,1);
 const struct collision_surface*s=TAG_BLOCK_GET_ELEMENT(&b->surfaces,si,struct collision_surface);
 p->object_index=NONE;p->surface_index=si;p->flags=s->flags;
 p->breakable_surface_index=s->breakable_surface_index;p->material_index=s->material_index;
 bsp3d_get_plane_from_designator(&b->bsp3d,s->plane_designator,&p->plane);
 p->height=0;p->projection_axis=projection_from_vector3d(&p->plane.n);
 p->projection_sign=projection_sign_from_vector3d(&p->plane.n,p->projection_axis);p->point_count=0;
 int edge=s->first_edge_index;
 do{
  const struct collision_edge*e=TAG_BLOCK_GET_ELEMENT(&b->edges,edge,struct collision_edge);
  bool reverse=e->surface_indices[1]==si;
  const struct collision_vertex*v=TAG_BLOCK_GET_ELEMENT(&b->vertices,e->vertex_indices[reverse],struct collision_vertex);
  assert(p->point_count<MAXIMUM_POINTS_PER_COLLISION_PRISM);
  project_point3d(&v->point,p->projection_axis,p->projection_sign,&p->points[p->point_count++]);
  edge=e->edge_indices[reverse];
 }while(edge!=s->first_edge_index);
 vehicle_workspace->prisms[slot].surface=si;vehicle_workspace->prisms[slot].valid=true;return p;
}
static bool cached_polygon_contains(const struct collision_prism*polygon,const real_point2d*point){
 for(int j=0;j<polygon->point_count;j++){
  const real_point2d*a=&polygon->points[j],*b=&polygon->points[j+1<polygon->point_count?j+1:0];
  real_vector2d v0,v1;vector_from_points2d(a,point,&v0);vector_from_points2d(a,b,&v1);
  if(cross_product2d(&v0,&v1)>0)return false;
 }return true;
}
static void cached_surface_feature(const struct collision_bsp*b,int si,float height,float width,struct collision_feature_list*out){
 if(height!=0){collision_features_from_surface(b,si,NULL,height,width,NONE,out);return;}
 unsigned count=out->count[_collision_feature_prism];if(count>=MAXIMUM_COLLISION_FEATURES_PER_TEST)return;
 out->prisms[count]=*cached_polygon(b,si);out->prisms[count].height=width;out->count[_collision_feature_prism]++;
}
/* Static edge eligibility, base/vector and material do not depend on the
 * query point. Cache the original zero-height factory output, including its
 * no-feature result; width remains the current mass-point radius. */
static void cached_edge_feature(const struct collision_bsp*b,int edge,float height,float width,struct collision_feature_list*out){
 if(height!=0){collision_features_from_edge(b,edge,NULL,height,width,NONE,out);return;}
 unsigned count=out->count[_collision_feature_cylinder];
 if(count>=MAXIMUM_COLLISION_FEATURES_PER_TEST)return;
 unsigned slot=((uint32_t)edge*2654435761u)&63u;
 if(vehicle_workspace->cylinders[slot].valid&&vehicle_workspace->cylinders[slot].edge==edge){
  BG_COUNT(BG_COUNT_EDGE_HIT,1);
  if(vehicle_workspace->cylinders[slot].produced){
   out->cylinders[count]=vehicle_workspace->cylinders[slot].cylinder;
   out->cylinders[count].width=width;out->count[_collision_feature_cylinder]++;
  }
 }else{
  BG_COUNT(BG_COUNT_EDGE_MISS,1);
  collision_features_from_edge(b,edge,NULL,height,width,NONE,out);
  bool produced=(unsigned)out->count[_collision_feature_cylinder]==count+1;
  if(produced)vehicle_workspace->cylinders[slot].cylinder=out->cylinders[count];
  vehicle_workspace->cylinders[slot].produced=produced;
  vehicle_workspace->cylinders[slot].edge=edge;vehicle_workspace->cylinders[slot].valid=true;
 }
}
static boolean collision_get_features_in_sphere(uint32_t flags,const real_point3d*p,real radius,real height,real width,int32_t ignore,struct collision_feature_list*out){
 BG_VP_BEGIN;
 (void)flags;(void)ignore;collision_features_new(out);unsigned query=next_stamp();const struct collision_bsp*b=&bg_vehicle_bsp;
 struct surface_query query_state;float lo[3],hi[3];
 for(int a=0;a<3;a++){lo[a]=p->n[a]-radius;hi[a]=p->n[a]+radius;}
 query_begin(&query_state,lo,hi);int si;
 while((si=query_next(&query_state))>=0){
   const struct collision_surface*s=TAG_BLOCK_GET_ELEMENT(&b->surfaces,si,struct collision_surface);
   /* Outside a polygon's front half-space by more than the query width:
    * neither its prism nor any boundary edge/vertex can touch this point. */
   if(height==0){real_plane3d plane;bsp3d_get_plane_from_designator(&b->bsp3d,s->plane_designator,&plane);
    if(plane3d_distance_to_point(&plane,p)>width+.0001f)continue;}
   cached_surface_feature(b,si,height,width,out);
   int first=s->first_edge_index,e=first;
   do{
    const struct collision_edge*ed=TAG_BLOCK_GET_ELEMENT(&b->edges,e,struct collision_edge);int side=ed->surface_indices[1]==(int)si;
    assert(e>=0&&e<b->edges.count);
    if(vehicle_workspace->stamps[0][e]!=query){vehicle_workspace->stamps[0][e]=query;
     /* A cylinder whose segment bounds miss this zero-height query sphere
      * cannot contain the mass point. Preserve the original edge test for
      * candidates and for nonzero-height callers. */
     bool candidate=true;
     if(height==0){
      const struct collision_vertex*a=TAG_BLOCK_GET_ELEMENT(&b->vertices,ed->vertex_indices[0],struct collision_vertex);
      const struct collision_vertex*c=TAG_BLOCK_GET_ELEMENT(&b->vertices,ed->vertex_indices[1],struct collision_vertex);
      for(unsigned axis=0;axis<3;axis++)if(MAX(a->point.n[axis],c->point.n[axis])+width+.00001f<p->n[axis]||MIN(a->point.n[axis],c->point.n[axis])-width-.00001f>p->n[axis]){candidate=false;break;}
     }
     if(candidate&&ed->surface_indices[0]>=0&&ed->surface_indices[1]>=0)cached_edge_feature(b,e,height,width,out);
    }
    int vi=ed->vertex_indices[side];assert(vi>=0&&vi<b->vertices.count);
    if(vehicle_workspace->stamps[1][vi]!=query){vehicle_workspace->stamps[1][vi]=query;
     const struct collision_vertex*v=TAG_BLOCK_GET_ELEMENT(&b->vertices,vi,struct collision_vertex);
     if(distance_squared3d(p,&v->point)<=radius*radius)collision_features_from_vertex(b,vi,NULL,height,width,NONE,out);
    }
    e=ed->edge_indices[side];
   }while(e!=first);
 }
 BG_VP_END(BG_VP_FEATURE_BUILD);
 return out->count[0]||out->count[1]||out->count[2];
}
/* Sweeps test complete original convex polygons, in original coordinates.
 * Only the broad phase and scene ownership differ from the engine BSP service. */
static boolean collision_test_vector(uint32_t flags,const real_point3d*p,const real_vector3d*d,int32_t ignore,struct collision_result*out){
 BG_VP_BEGIN;
 (void)flags;(void)ignore;const struct collision_bsp*b=&bg_vehicle_bsp;out->t=1;out->surface_index=-1;
 BG_COUNT(BG_COUNT_VECTOR_QUERY,1);
#ifdef BG_TELEMETRY
 if(d->i==0&&d->j==0&&d->k==0)BG_COUNT(BG_COUNT_VECTOR_ZERO,1);
#endif
 struct surface_query query_state;float lo[3],hi[3];
 for(int a=0;a<3;a++){lo[a]=MIN(p->n[a],p->n[a]+d->n[a]);hi[a]=MAX(p->n[a],p->n[a]+d->n[a]);}
 query_begin(&query_state,lo,hi);int si;
 while((si=query_next(&query_state))>=0){
   const struct collision_surface*s=TAG_BLOCK_GET_ELEMENT(&b->surfaces,si,struct collision_surface);
   real_plane3d plane;bsp3d_get_plane_from_designator(&b->bsp3d,s->plane_designator,&plane);
   float a=plane3d_distance_to_point(&plane,p),den=dot_product3d(&plane.n,d);
   if(fabsf(den)<1e-9f)continue;
   if((flags&1)&&den>=0)continue;
   float t=-a/den;if(t<0||t>out->t)continue;
   real_point3d hit;point_from_line3d(p,d,t,&hit);
   int axis=projection_from_vector3d(&plane.n);bool sign=projection_sign_from_vector3d(&plane.n,axis);real_point2d q;
   project_point3d(&hit,axis,sign,&q);bool inside=cached_polygon_contains(cached_polygon(b,si),&q);
   if(inside){out->t=t;out->plane=plane;out->surface_index=si;out->material_index=s->material_index;}
 }
 BG_VP_END(BG_VP_SWEEP);
 return out->surface_index>=0;
}
static bool ray_bounds(const int16_t bounds[6],const float origin[3],const float inverse[3],const bool zero[3],float maximum,float*entry){
 float near=0,far=maximum;
 for(unsigned k=0;k<3;k++){
  if(zero[k]){if(origin[k]<bounds[k]||origin[k]>bounds[k+3])return false;continue;}
  float lo=(bounds[k]-origin[k])*inverse[k],hi=(bounds[k+3]-origin[k])*inverse[k];
  if(lo>hi){float t=lo;lo=hi;hi=t;}if(lo>near)near=lo;if(hi<far)far=hi;if(near>far)return false;
 }
 *entry=near;return true;
}
float bg_world_raycast_normal(const float origin[3],const float direction[3],float distance,float normal[3]){
 if(distance<=.003f)return distance;
 world_load();
 float bias=.003f;
 real_point3d p={.n={origin[0]+direction[0]*bias+68,-origin[2]-direction[2]*bias-118,origin[1]+direction[1]*bias}};
 real_vector3d d={.n={direction[0]*(distance-bias),-direction[2]*(distance-bias),direction[1]*(distance-bias)}};
 float scaled[3],inverse[3];bool zero[3];
 for(unsigned k=0;k<3;k++){scaled[k]=p.n[k]*64;zero[k]=fabsf(d.n[k])<1e-12f;inverse[k]=zero[k]?0:1/(d.n[k]*64);}
 uint16_t stack[32];float entries[32];unsigned pending=1;stack[0]=0;entries[0]=0;float nearest=1;
 const struct collision_bsp*b=&bg_vehicle_bsp;
 while(pending){
  --pending;
  if(entries[pending]>nearest)continue;
  const struct vehicle_bvh_node*n=&bg_vehicle_bvh[stack[pending]];float entry;
  if(!n->count){
   unsigned left=(unsigned)(n-bg_vehicle_bvh)+1,right=n->first;float a,c;
   bool l=ray_bounds(bg_vehicle_bvh[left].bounds,scaled,inverse,zero,nearest,&a),r=ray_bounds(bg_vehicle_bvh[right].bounds,scaled,inverse,zero,nearest,&c);
   assert(pending+2<=32);
   if(l&&r){entries[pending]=a<c?c:a;stack[pending++]=a<c?right:left;entries[pending]=a<c?a:c;stack[pending++]=a<c?left:right;}
   else if(l){entries[pending]=a;stack[pending++]=left;}else if(r){entries[pending]=c;stack[pending++]=right;}
   continue;
  }
  for(unsigned j=0;j<n->count;j++){
   unsigned si=bg_vehicle_surface_indices[n->first+j];
   if(!ray_bounds(bg_vehicle_surface_bounds[si],scaled,inverse,zero,nearest,&entry))continue;
   const struct collision_surface*surface=TAG_BLOCK_GET_ELEMENT(&b->surfaces,si,struct collision_surface);
   real_plane3d plane;bsp3d_get_plane_from_designator(&b->bsp3d,surface->plane_designator,&plane);
   float den=dot_product3d(&plane.n,&d);if(fabsf(den)<1e-9f)continue;
   float t=-plane3d_distance_to_point(&plane,&p)/den;if(t<0||t>nearest)continue;
   real_point3d hit;point_from_line3d(&p,&d,t,&hit);int axis=projection_from_vector3d(&plane.n);
   bool sign=projection_sign_from_vector3d(&plane.n,axis);real_point2d q;project_point3d(&hit,axis,sign,&q);
   if(cached_polygon_contains(cached_polygon(b,si),&q)){nearest=t;if(normal){normal[0]=plane.n.i;normal[1]=plane.n.k;normal[2]=-plane.n.j;}}
  }
 }
 return bias+nearest*(distance-bias);
}
float bg_world_raycast(const float o[3],const float d[3],float distance){return bg_world_raycast_normal(o,d,distance,NULL);}
void bg_world_camera_rays(const float origin[3],const float rays[5][3],const float reaches[5],float hits[5]){
 BG_VP_BEGIN;
 world_load();real_point3d p[5];real_vector3d d[5];float lo[3],hi[3],nearest[5];
 float scaled[5][3],inverse[5][3];bool parallel[5][3];
 for(unsigned i=0;i<5;i++){
  p[i]=(real_point3d){.n={origin[0]+rays[i][0]*.003f+68,-origin[2]-rays[i][2]*.003f-118,origin[1]+rays[i][1]*.003f}};
  float length=MAX(0,reaches[i]-.003f);
  d[i]=(real_vector3d){.n={rays[i][0]*length,-rays[i][2]*length,rays[i][1]*length}};nearest[i]=1;
  for(unsigned a=0;a<3;a++){
   scaled[i][a]=p[i].n[a]*64;
   parallel[i][a]=fabsf(d[i].n[a])<1e-12f;
   inverse[i][a]=parallel[i][a]?0:1/(d[i].n[a]*64);
   float end=p[i].n[a]+d[i].n[a],lower=MIN(p[i].n[a],end),upper=MAX(p[i].n[a],end);
   if(i==0){lo[a]=lower;hi[a]=upper;}else{lo[a]=MIN(lo[a],lower);hi[a]=MAX(hi[a],upper);}
  }
 }
 struct surface_query query;query_begin(&query,lo,hi);int si;const struct collision_bsp*b=&bg_vehicle_bsp;
 while((si=query_next(&query))>=0){
  unsigned ray_mask=0;
  for(unsigned i=0;i<5;i++){
   float entry;
   /* Conservative endpoint slack only broadens candidate selection. The
    * original plane/edge arithmetic still decides each exact hit. */
   if(ray_bounds(bg_vehicle_surface_bounds[si],scaled[i],inverse[i],parallel[i],nearest[i]+.00001f,&entry))ray_mask|=1u<<i;
  }
  if(!ray_mask)continue;
  const struct collision_surface*s=TAG_BLOCK_GET_ELEMENT(&b->surfaces,si,struct collision_surface);
  real_plane3d plane;bsp3d_get_plane_from_designator(&b->bsp3d,s->plane_designator,&plane);
  int axis=projection_from_vector3d(&plane.n);bool sign=projection_sign_from_vector3d(&plane.n,axis);
  float fractions[5];real_point2d points[5];unsigned mask=0;
  for(unsigned i=0;i<5;i++){
   if(!(ray_mask&(1u<<i)))continue;
   float den=dot_product3d(&plane.n,&d[i]);if(fabsf(den)<1e-9f)continue;
   float t=-plane3d_distance_to_point(&plane,&p[i])/den;if(t<0||t>nearest[i])continue;
   real_point3d hit;point_from_line3d(&p[i],&d[i],t,&hit);project_point3d(&hit,axis,sign,&points[i]);
   fractions[i]=t;mask|=1u<<i;
  }
  /* Same directed-edge expression, sharing immutable projected endpoints. */
  const struct collision_prism*polygon=mask?cached_polygon(b,si):NULL;
  for(int edge=0;mask&&edge<polygon->point_count;edge++){
   const real_point2d*a=&polygon->points[edge],*c=&polygon->points[edge+1<polygon->point_count?edge+1:0];
   float dx=c->x-a->x,dy=c->y-a->y;
   for(unsigned i=0;i<5;i++)if((mask&(1u<<i))&&((points[i].x-a->x)*dy-(points[i].y-a->y)*dx)>0)mask&=~(1u<<i);
  }
  for(unsigned i=0;i<5;i++)if(mask&(1u<<i))nearest[i]=fractions[i];
 }
 for(unsigned i=0;i<5;i++)hits[i]=reaches[i]<=.003f?reaches[i]:.003f+nearest[i]*(reaches[i]-.003f);
 BG_VP_END(BG_VP_WORLD_CAMERA);
}
static void physics_compute_unit_collisions(int32_t i){
 /* Wrecks keep terrain contacts but do not block or push live vehicles. */
 if(!bg_vehicles[i].active)return;
 struct physics_instance a;physics_instance_new(&a,i);
 for(int32_t j=0;j<(int32_t)bg_vehicle_count;j++)if(j!=i&&bg_vehicles[j].active&&(j<i||TEST_FLAG(native[j].object.flags,_object_at_rest_bit))){
  /* Conservative body radii avoid the original all-contact-pairs work at distance. */
  float radius=body_radius[bg_vehicles[i].kind]+body_radius[bg_vehicles[j].kind];
  if(distance_squared3d(&native[i].object.position,&native[j].object.position)>radius*radius)continue;
  struct physics_instance b;physics_instance_new(&b,j);physics_compute_vehicle_collision(&a,&b);
 }
}

static float published[BG_MAX_VEHICLES][5];
static real_vector3d halo_vector(const float v[3]){return (real_vector3d){.n={v[0],-v[2],v[1]}};}
static void game_vector(const real_vector3d*v,float out[3]){out[0]=v->i;out[1]=v->k;out[2]=-v->j;}
static void publish(unsigned i){
 bg_vehicle*v=&bg_vehicles[i];struct vehicle_datum*n=&native[i];struct physics_instance instance;
 physics_instance_new(&instance,i);
 v->pos[0]=instance.world_matrix.position.x-68;v->pos[1]=instance.world_matrix.position.z;v->pos[2]=-instance.world_matrix.position.y-118;
 game_vector(&n->object.forward,v->forward);game_vector(&n->object.up,v->up);
 game_vector(&n->object.translational_velocity,v->velocity);game_vector(&n->object.angular_velocity,v->angular_velocity);
 for(int a=0;a<3;a++){v->velocity[a]*=30;v->angular_velocity[a]*=30;}
 v->yaw=atan2f(n->object.forward.j,n->object.forward.i);v->pitch=asinf(PIN(n->object.forward.k,-1,1));
 v->speed=dot_product3d(&n->object.forward,&n->object.translational_velocity)*30;
 v->steering=n->vehicle.turn;
 v->flipping=TEST_FLAG(n->vehicle.flags,4);
 float circumference=bg_vehicle_drive_defs[v->kind].wheel_circumference;
 v->wheel_phase=circumference>0?n->vehicle.wheel/circumference*(2*_pi):0;
 memcpy(published[i],v->pos,12);published[i][3]=v->yaw;published[i][4]=v->pitch;v->physics_valid=true;
}
void bg_vehicle_physics_prepare(void){
 world_load();
 for(unsigned i=0;i<bg_vehicle_count;i++){
  bg_vehicle*v=&bg_vehicles[i];if(!bg_vehicle_body_present(v))continue;
  if(v->physics_valid&&native[i].definition_index==v->kind&&!memcmp(v->pos,published[i],12)&&v->yaw==published[i][3]&&v->pitch==published[i][4])continue;
  struct vehicle_datum*n=&native[i];memset(n,0,sizeof(*n));n->definition_index=v->kind;
  n->object.forward=(real_vector3d){.n={cosf(v->yaw)*cosf(v->pitch),sinf(v->yaw)*cosf(v->pitch),sinf(v->pitch)}};
  n->object.up=(real_vector3d){.n={-cosf(v->yaw)*sinf(v->pitch),-sinf(v->yaw)*sinf(v->pitch),cosf(v->pitch)}};
  n->object.position=(real_point3d){.n={v->pos[0]+68,-v->pos[2]-118,v->pos[1]}};
  real_matrix4x3 frame;matrix4x3_from_point_and_vectors(&frame,&n->object.position,&n->object.forward,&n->object.up);
  matrix4x3_transform_point(&frame,&bg_vehicle_physics_defs[v->kind].center_of_mass,&n->object.position);
  n->object.translational_velocity=halo_vector(v->velocity);scale_vector3d(&n->object.translational_velocity,1.f/30,&n->object.translational_velocity);
  n->object.angular_velocity=halo_vector(v->angular_velocity);scale_vector3d(&n->object.angular_velocity,1.f/30,&n->object.angular_velocity);
  const struct physics_definition*p=&bg_vehicle_physics_defs[v->kind];float radius=0;
  for(int j=0;j<p->mass_points.count;j++){const struct mass_point_definition*m=TAG_BLOCK_GET_ELEMENT(&p->mass_points,j,struct mass_point_definition);radius=MAX(radius,sqrtf(distance_squared3d(&m->position,&p->center_of_mass))+m->radius);}
  body_radius[v->kind]=radius;publish(i);
 }
}
/* Same suspension ray, smoothing and byte channel as vehicles.c. Animation
 * graph lookup is replaced by the eight exported channel descriptors. */
static void suspension_update(unsigned i){
 BG_VP_BEGIN;
 bg_vehicle*v=&bg_vehicles[i];struct vehicle_datum*n=&native[i];const struct physics_definition*p=&bg_vehicle_physics_defs[v->kind];
 real_matrix4x3 frame;matrix4x3_from_point_and_vectors(&frame,&n->object.position,&n->object.forward,&n->object.up);
 for(int j=0;j<8;j++){
  int mi=bg_vehicle_suspension_points[v->kind][j];if(mi<0)continue;
  const struct mass_point_definition*m=TAG_BLOCK_GET_ELEMENT(&p->mass_points,mi,struct mass_point_definition);
  real_point3d point,start;real_vector3d normal,vector;struct collision_result hit;
  matrix4x3_transform_point(&frame,&m->position,&point);matrix4x3_transform_normal(&frame,&m->up,&normal);
  float extension=bg_vehicle_suspension_bounds[v->kind][j][0],compression=bg_vehicle_suspension_bounds[v->kind][j][1];
  float extent=extension-compression,offset=(compression-p->center_of_mass.z)-extent;
  point_from_line3d(&point,&normal,offset,&start);scale_vector3d(&normal,extent+extent,&vector);
  collision_test_vector(0xc0a0,&start,&vector,i,&hit);
  float shift=PIN((1-hit.t)+(1-hit.t),0,1),current=n->vehicle.suspension[j]*(1.f/255);
  n->vehicle.suspension[j]=(uint8_t)((shift+current)*.5f*255);
  v->suspension[j]=extension+(compression-extension)*n->vehicle.suspension[j]*(1.f/255);
 }
 BG_VP_END(BG_VP_SUSPENSION);
}
void bg_vehicle_physics_step(unsigned i,const bg_input*input){
 bg_vehicle*v=&bg_vehicles[i];struct vehicle_datum*n=&native[i];
 const struct vehicle_definition*d=&bg_vehicle_drive_defs[v->kind];
 n->unit.throttle=(real_vector2d){.n={input?input->forward:0,input?-input->strafe:0}};
 n->unit.control_flags=(input&&input->crouch?FLAG(_unit_control_crouch_modifier_bit):0)|(input&&input->jump?FLAG(_unit_control_jump_bit):0);
 if(input){
  const bg_player*driver=&bg_players[v->occupants[0]];
  float yaw=driver->yaw,pitch=driver->pitch;
  n->unit.desired_facing_vector=(real_vector3d){.n={cosf(yaw)*cosf(pitch),sinf(yaw)*cosf(pitch),sinf(pitch)}};
 }else n->unit.desired_facing_vector=n->object.forward;
 /* units.c powered-seat ramp, in native seconds/ticks. */
 for(int seat=0;seat<2;seat++){
  bool on=v->occupants[seat]>=0&&bg_players[v->occupants[seat]].seat_state==BG_SEAT_STABLE;float time=bg_vehicle_seat_times[v->kind][seat][on?0:1];
  float delta=time>0?1.f/(time*30):1;
  n->unit.seat_power[seat]=PIN(n->unit.seat_power[seat]+(on?delta:-delta),0,1);
 }
 /* Wide Banshee wings can remain braced against the demake terrain after
  * the source's 30-tick roll. Continue that same torque, bounded to 90 ticks;
  * the original upright threshold still ends recovery as soon as it clears. */
 if(v->flipping&&v->kind==BG_V_BANSHEE&&++v->flip_elapsed<90&&n->vehicle.upending_ticks>=30&&n->object.up.k<=.9f)
  n->vehicle.upending_ticks=0;
 vehicle_control_update(i);
 /* Give an overturned fighter a small, bounded clearance lift while its
  * wide wing has not yet cleared the ground. This changes velocity, not pose;
  * contacts and the original roll torque still perform the recovery. */
 if(v->flipping&&v->kind==BG_V_BANSHEE&&v->flip_elapsed<90&&n->object.up.k<.9f)
  n->object.translational_velocity.k=MAX(n->object.translational_velocity.k,.025f);
 if(!TEST_FLAG(n->object.flags,_object_at_rest_bit)){
  /* physics_compute_new clears the active contact records itself. */
  memset(vehicle_workspace->power,0,sizeof(vehicle_workspace->power));
  switch(v->kind){
   case BG_V_WARTHOG:update_human_jeep_physics(i,vehicle_workspace->contact,vehicle_workspace->power);break;
   case BG_V_GHOST:update_alien_scout_physics(i,vehicle_steering[i],vehicle_workspace->power,vehicle_workspace->contact);break;
   case BG_V_SCORPION:update_human_tank_physics(i,vehicle_workspace->contact,vehicle_workspace->power);break;
   case BG_V_BANSHEE:update_alien_fighter_physics_new(i,vehicle_workspace->power,vehicle_workspace->contact);break;
  }
  suspension_update(i);compute_airborne_ticks(i,vehicle_workspace->contact,vehicle_workspace->power);
  if(TEST_FLAG(n->object.flags,_object_at_rest_bit))n->vehicle.stop_time=15;
  if(d->vehicle_type==_vehicle_type_alien_fighter){
   if(bg_vehicle_floor!=0&&n->object.position.z<bg_vehicle_floor)n->object.translational_velocity.k+=((bg_vehicle_floor-n->object.position.z)*.015625f-n->object.translational_velocity.k*.0625f)*n->unit.seat_power[0];
   if(bg_vehicle_ceiling!=0&&n->object.position.z>bg_vehicle_ceiling)n->object.translational_velocity.k-=((n->object.position.z-bg_vehicle_ceiling)*.015625f+n->object.translational_velocity.k*.0625f)*n->unit.seat_power[0];
  }
 }else if(n->vehicle.stop_time>0){slowly_stop_vehicle(i);suspension_update(i);}
 else{v->steering=n->vehicle.turn;return;}
 publish(i);
}
bool bg_vehicle_airborne(unsigned i){return native[i].vehicle.airborne_ticks>0;}
void bg_vehicle_physics_wreck(unsigned i){
 /* Original rigid-body integration, contacts and gravity, with no powered
  * mass points: dead Ghosts lose antigravity and dead Banshees fall. */
 struct vehicle_datum*n=&native[i];
 if(bg_vehicles[i].wreck_time==BG_WRECK_LIFE)n->object.flags&=~FLAG(_object_at_rest_bit);
 if(TEST_FLAG(n->object.flags,_object_at_rest_bit))return;
 n->unit.seat_power[0]=n->unit.seat_power[1]=0;
 physics_update(i,NULL,vehicle_workspace->contact,global_zero_vector3d,global_zero_vector3d);
 publish(i);
}
void bg_vehicle_transform(const bg_vehicle*v,const float local[3],float out[3]){
 float f[3],u[3],r[3];
 if(v->physics_valid){memcpy(f,v->forward,sizeof(f));memcpy(u,v->up,sizeof(u));}
 else{f[0]=cosf(v->yaw)*cosf(v->pitch);f[1]=sinf(v->pitch);f[2]=-sinf(v->yaw)*cosf(v->pitch);u[0]=-cosf(v->yaw)*sinf(v->pitch);u[1]=cosf(v->pitch);u[2]=sinf(v->yaw)*sinf(v->pitch);}
 r[0]=f[1]*u[2]-f[2]*u[1];r[1]=f[2]*u[0]-f[0]*u[2];r[2]=f[0]*u[1]-f[1]*u[0];
 for(int a=0;a<3;a++)out[a]=v->pos[a]+f[a]*local[0]+u[a]*local[1]+r[a]*local[2];
}
void bg_vehicle_physics_flip(unsigned i,const float player_position[3]){
 bg_vehicle_physics_prepare();struct vehicle_datum*n=&native[i];
 /* player_examine_nearby_vehicle permits use before the stricter .2
  * vehicle_is_flipped driving-state predicate. Match the HUD/use threshold. */
 if(n->object.up.k>=BG_VEHICLE_FLIP_MAX_UP)return;
 n->vehicle.flags|=FLAG(4);/* players.c flip action selects the roll/pitch direction from approach. */
 if(fabsf(n->object.forward.k)>.70710677f)n->vehicle.upending_type=(n->object.forward.k<0)+3;
 else{
  real_vector3d delta={.n={n->object.position.x-(player_position[0]+68),n->object.position.y-(-player_position[2]-118),n->object.position.z-player_position[1]}};
  cross_product3d(global_up3d,&delta,&delta);
  n->vehicle.upending_type=(dot_product3d(&delta,&n->object.forward)>0)+1;
 }n->vehicle.upending_ticks=0;n->object.flags&=~FLAG(_object_at_rest_bit);
 bg_vehicles[i].flipping=true;
 bg_vehicles[i].flip_elapsed=0;
}

void bg_vehicle_physics_damage(unsigned i,const float origin[3],float strength,bool explosive){
 if(!bg_vehicles[i].active)return;
 float scale=bg_vehicle_acceleration_scale[bg_vehicles[i].kind];
 if(strength<=_real_epsilon||scale<=_real_epsilon)return;
 bg_vehicle_physics_prepare();
 real_vector3d direction={.n={native[i].object.position.x-(origin[0]+68),native[i].object.position.y-(-origin[2]-118),native[i].object.position.z-origin[1]}},acceleration;
 normalize3d(&direction);vehicle_damage_acceleration(&direction,strength,scale,&acceleration);
 if(explosive)scale_vector3d(&acceleration,2,&acceleration);
 vehicle_accelerate(i,&acceleration);publish(i);
}
void bg_vehicle_physics_explosion(unsigned i,const float origin[3],int kind){
 if(kind<0||kind>=7)return;
 const struct vehicle_damage_kick*k=&bg_vehicle_damage_kicks[kind];
 bg_vehicle_physics_damage(i,origin,k->acceleration,TEST_FLAG(k->flags,5));
}
