#include "collision.h"
#include <assert.h>
#include <math.h>
#include <stddef.h>
#include <string.h>

typedef float real;
typedef uint8_t byte,boolean;
typedef blam_point2 real_point2d;
typedef blam_point3 real_point3d;
typedef blam_vector2 real_vector2d;
typedef blam_vector3 real_vector3d;
typedef blam_plane3 real_plane3d;
enum { FALSE,TRUE };
enum { _x,_y,_z };
enum { _collision_surface_two_sided_bit,_collision_surface_invisible_bit,
       _collision_surface_climbable_bit,_collision_surface_breakable_bit };
enum { _collision_leaf_contains_two_sided_bit };
enum { _contents_unknown,_contents_empty,_contents_semi_empty,_contents_solid };
enum { _collision_test_front_facing_surfaces_bit,_collision_test_back_facing_surfaces_bit,
       _collision_test_ignore_two_sided_surfaces_bit,_collision_test_ignore_invisible_surfaces_bit,
       _collision_test_ignore_breakable_surfaces_bit };
#define NONE (-1)
#define PIN(x,a,b) ((x)<(a)?(a):(x)>(b)?(b):(x))
#define TEST_FLAG(flags,bit) ((flags)&(UINT32_C(1)<<(bit)))
#define BIT_VECTOR_TEST_FLAG(flags,bit) ((flags)[(bit)>>5]&(UINT32_C(1)<<((bit)&31)))
#define match_assert(file,line,condition) assert(condition)
#define TAG_BLOCK_GET_ELEMENT(block,index,type) ((const type*)block_element((block),(index),sizeof(type)))
static const void *block_element(const blam_tag_block *block,int32_t index,size_t size){
    assert(block&&index>=0&&index<block->count&&block->address);
    return (const uint8_t*)block->address+(size_t)index*size;
}

struct collision_bsp_test_vector_result {
    real t;const real_plane3d *plane;int32_t surface_index,plane_designator;
    byte flags,breakable_surface_index;int16_t material_index;
    int32_t leaf_count,leaf_indices[256];
};
struct collision_bsp_test_vector_context {
    uint32_t flags;const struct collision_bsp *bsp;
    int16_t breakable_surface_count,pad;const byte *breakable_surface_flags;
    const real_point3d *point;const real_vector3d *vector;
    struct collision_bsp_test_vector_result *result;int32_t last_leaf_index;
    byte last_contents,pad2[3];int32_t last_plane_index;
};
static boolean collision_bsp_test_vector_recursive(struct collision_bsp_test_vector_context *,int32_t,real,real);
#include "collision_original.c"

_Static_assert(sizeof(blam_bsp3d_node)==12,"original BSP3D node");
_Static_assert(sizeof(blam_bsp2d_node)==20,"original BSP2D node");
_Static_assert(sizeof(blam_collision_leaf)==8,"original collision leaf");
_Static_assert(sizeof(blam_bsp2d_reference)==8,"original BSP2D reference");
_Static_assert(sizeof(blam_collision_surface)==12,"original collision surface");
_Static_assert(sizeof(blam_collision_edge)==24,"original collision edge");
_Static_assert(sizeof(blam_collision_vertex)==16,"original collision vertex");
#if UINTPTR_MAX == UINT32_MAX
_Static_assert(sizeof(blam_collision_bsp)==96,"original collision BSP");
_Static_assert(sizeof(struct collision_bsp_test_vector_context)==40,"original collision context");
#endif

bool blam_collision_segment(const blam_collision_bsp *bsp,const float origin[3],
    const float displacement[3],bool back_faces,blam_collision_hit *hit){
    if(!bsp||!origin||!displacement||!hit||bsp->bsp3d.nodes.count<=0)return false;
    real_point3d point;real_vector3d vector;memcpy(point.n,origin,12);memcpy(vector.n,displacement,12);
    struct collision_bsp_test_vector_result result;
    if(!collision_bsp_test_vector(back_faces?3:1,bsp,0,NULL,&point,&vector,1.f,&result))return false;
    hit->fraction=result.t;hit->surface=result.surface_index;hit->material=result.material_index;
    float sign=result.plane_designator<0?-1.f:1.f;
    for(unsigned i=0;i<3;i++)hit->normal[i]=result.plane->n.n[i]*sign;
    return true;
}
