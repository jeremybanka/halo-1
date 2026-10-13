"""Prove PVS sphere unions retain every sampled valid source-camera row."""
import argparse
import json
from pathlib import Path
import subprocess
import struct
from export_chiron_visibility import ROOT,emit_c
from asset_ids import map_ids

TEST=r'''
#include "render_pvs.h"
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>
extern const bg_pvs_data bg_world_pvs;
static uint32_t seed=0xc41064;
static float random_float(void){seed=seed*1664525u+1013904223u;return (seed>>8)*(1.f/16777216.f);}
/* Independent original bsp3d_test_point decision path, with no sphere or PVS
 * traversal logic shared with the candidate. Invalid points have no row. */
static int cluster_at(const bg_pvs_data*d,const float p[3]){
 int32_t index=0;
 for(unsigned step=0;step<d->node_count+1;step++){
  if(index<0){if(index==-1)return -1;unsigned leaf=(uint32_t)index&0x7fffffff;assert(leaf<d->leaf_count);return d->leaf_clusters[leaf];}
  assert((unsigned)index<d->node_count);const bg_pvs_node*n=&d->nodes[index];const float*q=d->planes[n->plane].v;
  float distance=q[0]*p[0]+q[1]*p[1]+q[2]*p[2]-q[3];index=distance>=0?n->front:n->back;
 }
 assert(!"Cyclic original BSP");return -1;
}
int main(void){
 const bg_pvs_node nodes[]={{0,(int32_t)0x80000000u,(int32_t)0x80000001u}};
 const bg_pvs_plane planes[]={{{1,0,0,0}}};const int16_t leaves[]={0,1};
 const uint64_t rows[]={1,2},chunks[]={1,2,3,0};
 bg_pvs_data synthetic={nodes,planes,leaves,rows,chunks,1,1,2,2,4,1};
 assert(bg_pvs_camera_mask(&synthetic,(float[]){-2,0,0},.25f)==1);
 assert(bg_pvs_camera_mask(&synthetic,(float[]){2,0,0},.25f)==2);
 assert(bg_pvs_camera_mask(&synthetic,(float[]){0,0,0},.25f)==3);
 assert(bg_pvs_camera_mask(&synthetic,(float[]){NAN,0,0},.25f)==3);
 assert(bg_pvs_camera_mask(&synthetic,(float[]){0,0,0},-1)==3);
 assert(bg_pvs_keep_chunk(&synthetic,1,0)&&!bg_pvs_keep_chunk(&synthetic,1,1));
 assert(bg_pvs_keep_chunk(&synthetic,1,2)&&bg_pvs_keep_chunk(&synthetic,1,3)&&bg_pvs_keep_chunk(&synthetic,1,100));
 bg_pvs_node solid={0,-1,(int32_t)0x80000001u};synthetic.nodes=&solid;
 assert(bg_pvs_camera_mask(&synthetic,(float[]){-.01f,0,0},.25f)==3);
 bg_pvs_node cycle={0,0,0};synthetic.nodes=&cycle;
 assert(bg_pvs_camera_mask(&synthetic,(float[]){0,0,0},.25f)==3);
 const int16_t wide_leaves[]={0,34};uint64_t wide_rows[64]={0},wide_chunks[]={UINT64_C(1)<<34};
 for(unsigned i=0;i<64;i++)wide_rows[i]=UINT64_C(1)<<i;
 synthetic.nodes=nodes;synthetic.leaf_clusters=wide_leaves;synthetic.rows=wide_rows;synthetic.chunk_masks=wide_chunks;synthetic.cluster_count=35;synthetic.chunk_count=1;
 assert(bg_pvs_camera_mask(&synthetic,(float[]){2,0,0},.25f)==(UINT64_C(1)<<34));
 assert(bg_pvs_keep_chunk(&synthetic,UINT64_C(1)<<34,0));
 const int16_t top_leaves[]={0,63};synthetic.leaf_clusters=top_leaves;synthetic.cluster_count=64;
 assert(bg_pvs_all_mask(&synthetic)==UINT64_MAX);
 assert(bg_pvs_camera_mask(&synthetic,(float[]){2,0,0},.25f)==(UINT64_C(1)<<63));
 const bg_pvs_data*d=&bg_world_pvs;unsigned useful=0,valid=0,nearby=0;uint64_t clusters_seen=0;
 PROBES
 for(unsigned i=0;i<probe_count;i++){
  int c=cluster_at(d,probes[i]);assert(c==(int)i);clusters_seen|=UINT64_C(1)<<c;
  for(unsigned r=0;r<3;r++)assert((d->rows[c]&~bg_pvs_camera_mask(d,probes[i],(float[]){.005f,.25f,1.25f}[r]))==0);
 }
 /* Source map bounds plus outside probes. Camera uncertainty radii include
  * ordinary and scope near-plane spheres. Every valid sampled point inside
  * a sphere must have all of its original PVS rows retained. */
 for(unsigned trial=0;trial<30000;trial++){
  const float bounds[6]={BOUNDS};
  float p[3];for(unsigned a=0;a<3;a++)p[a]=bounds[a]+random_float()*(bounds[a+3]-bounds[a]);
  float radius=trial%3==0?1.25f:trial%3==1?.25f:.005f;
  uint64_t mask=bg_pvs_camera_mask(d,p,radius),all=bg_pvs_all_mask(d);
  useful+=mask!=all;int center=cluster_at(d,p);
  if(center>=0){valid++;clusters_seen|=UINT64_C(1)<<center;assert((d->rows[center]&~mask)==0);}
  else assert(mask==all);
  for(unsigned sample=0;sample<64;sample++){
   float delta[3]={random_float()*2-1,random_float()*2-1,random_float()*2-1};
   if(delta[0]*delta[0]+delta[1]*delta[1]+delta[2]*delta[2]>1)continue;
   float q[3]={p[0]+delta[0]*radius,p[1]+delta[1]*radius,p[2]+delta[2]*radius};int c=cluster_at(d,q);
   if(c>=0){assert((d->rows[c]&~mask)==0);nearby++;}
  }
 }
 assert(useful>100&&valid>100&&nearby>1000);
 assert(clusters_seen==bg_pvs_all_mask(d));
 printf("PASS: 30000 source camera spheres, %u valid centers, %u valid nearby points, %u selective masks; all %u clusters covered; boundaries/outside/NaN/cycle fail open\n",valid,nearby,useful,d->cluster_count);
}
'''


def run(out,sidecar):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    data=json.loads(sidecar.read_text());emit_c(data,out/'data.c')
    name=next(n for n,id in map_ids().items() if id==data['map_id'])
    report=json.loads((ROOT/'halo64-assets/generated/maps/maps-report.json').read_text())['maps'][name]
    off,count,stride=report['sections'][8];bank=(ROOT/'halo64-assets/generated/maps'/(name+'.map64')).read_bytes()
    vertices=[(x,-z,y) for x,y,z in struct.iter_unpack('>3f',bank[off:off+count*stride])]
    bounds=[min(p[a] for p in vertices)-2 for a in range(3)]+[max(p[a] for p in vertices)+2 for a in range(3)]
    probes=data.get('cluster_probes',[])
    probe_source='const unsigned probe_count='+str(len(probes))+';const float probes[][3]={'+(','.join('{'+','.join(float(x).hex()+'f' for x in p)+'}' for p in probes) or '{0,0,0}')+'};'
    (out/'test.c').write_text(TEST.replace('BOUNDS',','.join(float(x).hex()+'f' for x in bounds)).replace('PROBES',probe_source))
    for label,flags in [('strict',['-fno-fast-math']),('target',['-ffast-math','-ftrapping-math','-fno-associative-math','-fno-finite-math-only'])]:
        binary=out/label
        subprocess.run(['clang','-std=c17','-O2','-g','-fsanitize=address,undefined','-ffp-contract=off',*flags,
                        '-Iport/n64',str(out/'test.c'),str(out/'data.c'),'port/n64/render_pvs.c','-lm','-o',str(binary)],cwd=ROOT,check=True)
        subprocess.run([str(binary)],cwd=ROOT,check=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'build/n64-chiron-visibility/pvs-contract')
    parser.add_argument('--sidecar',type=Path,default=ROOT/'build/n64-chiron-visibility/data/visibility.json')
    args=parser.parse_args();run(args.output_dir,args.sidecar.resolve())
