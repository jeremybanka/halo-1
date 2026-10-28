/* Two walkable height layers retain base interiors as well as their roofs.
 * Edges are baked with the production capsule clearance, never with render
 * geometry. All enemy species fit the largest source capsule used here. */
#define PVE_GRID 129
#define PVE_CELLS (PVE_GRID*PVE_GRID)
#define PVE_NODES (PVE_CELLS*2)
#define PVE_ORIGIN 64
static float pve_nav_height[PVE_NODES];
static uint8_t pve_nav_edges[PVE_NODES],pve_nav_layers[PVE_NODES];
static void pve_routes_reset(bool initialize);
static const int pve_dx[8]={1,-1,0,0,1,1,-1,-1},pve_dz[8]={0,0,1,-1,1,-1,1,-1};
#ifndef BG_PVE_NAV_BUILD
extern const float bg_pve_nav_heights[PVE_NODES];
extern const uint8_t bg_pve_nav_links[PVE_NODES],bg_pve_nav_layers[PVE_NODES];
#endif
static void pve_node_pos(int node,float out[3]){
    int cell=node%PVE_CELLS;out[0]=cell%PVE_GRID-PVE_ORIGIN;out[1]=pve_nav_height[node];out[2]=cell/PVE_GRID-PVE_ORIGIN;
}
static int pve_node(const float pos[3]){
    int x=(int)floorf(pos[0]+PVE_ORIGIN+.5f),z=(int)floorf(pos[2]+PVE_ORIGIN+.5f),best=-1;float distance=1e9f;
    for(int dz=-1;dz<=1;dz++)for(int dx=-1;dx<=1;dx++){
        int nx=x+dx,nz=z+dz;if(nx<0||nx>=PVE_GRID||nz<0||nz>=PVE_GRID)continue;
        for(int layer=0;layer<2;layer++){
            int node=layer*PVE_CELLS+nz*PVE_GRID+nx;if(pve_nav_height[node]<-999||!pve_nav_edges[node])continue;
            float dy=pos[1]-pve_nav_height[node];if(fabsf(dy)>1.2f)continue;
            float a=pos[0]-(nx-PVE_ORIGIN),b=pos[2]-(nz-PVE_ORIGIN),cost=a*a+b*b+4*dy*dy;
            if(cost<distance){best=node;distance=cost;}
        }
    }
    return best;
}
static int pve_neighbor(int node,unsigned direction){
    int cell=node%PVE_CELLS+pve_dx[direction]+PVE_GRID*pve_dz[direction];
    return cell+((pve_nav_layers[node]>>direction)&1)*PVE_CELLS;
}
static void pve_nav_init(void){
    static bool loaded;
    if(!loaded){
#ifdef BG_PVE_NAV_BUILD
        for(int cell=0;cell<PVE_CELLS;cell++){
            float ceiling=12;
            for(int layer=0;layer<2;layer++){
                int node=layer*PVE_CELLS+cell;bg_player p={0};p.vehicle=-1;p.pve_radius=.24f;p.pve_height=.8f;
                p.pos[0]=cell%PVE_GRID-PVE_ORIGIN;p.pos[2]=cell/PVE_GRID-PVE_ORIGIN;
                p.pos[1]=bg_floor(p.pos[0],p.pos[2],ceiling)+.015f;ceiling=p.pos[1]-.35f;
                pve_nav_height[node]=p.pos[1]>-999&&p.pos[1]<10&&bg_terrain_clearance(&p)?p.pos[1]:-1000;
            }
        }
        for(int node=0;node<PVE_NODES;node++)if(pve_nav_height[node]>-999)for(unsigned k=0;k<8;k++){
            int cell=node%PVE_CELLS,x=cell%PVE_GRID+pve_dx[k],z=cell/PVE_GRID+pve_dz[k];
            if(x<0||x>=PVE_GRID||z<0||z>=PVE_GRID)continue;
            for(unsigned layer=0;layer<2;layer++){
                int next=layer*PVE_CELLS+z*PVE_GRID+x;
                if(pve_nav_height[next]<-999||fabsf(pve_nav_height[node]-pve_nav_height[next])>.65f)continue;
                bool clear=true;
                for(unsigned step=0;step<=8;step++){
                    bg_player p={0};p.vehicle=-1;p.pve_radius=.24f;p.pve_height=.8f;
                    p.pos[0]=cell%PVE_GRID-PVE_ORIGIN+pve_dx[k]*(step/8.f);p.pos[2]=cell/PVE_GRID-PVE_ORIGIN+pve_dz[k]*(step/8.f);
                    p.pos[1]=bg_floor(p.pos[0],p.pos[2],fmaxf(pve_nav_height[node],pve_nav_height[next])+.25f)+.015f;
                    float expected=pve_nav_height[node]+(pve_nav_height[next]-pve_nav_height[node])*step/8.f;
                    if(!bg_terrain_clearance(&p)||fabsf(p.pos[1]-expected)>.35f){clear=false;break;}
                }
                if(clear){pve_nav_edges[node]|=1u<<k;if(layer)pve_nav_layers[node]|=1u<<k;break;}
            }
        }
        /* Symmetric edges keep reverse flood-fill paths valid. */
        static const unsigned reverse[8]={1,0,3,2,7,6,5,4};
        for(int n=0;n<PVE_NODES;n++)for(unsigned k=0;k<8;k++)if(pve_nav_edges[n]&(1u<<k)){
            int next=pve_neighbor(n,k);unsigned r=reverse[k];
            if(!(pve_nav_edges[next]&(1u<<r))||pve_neighbor(next,r)!=n)pve_nav_edges[n]&=~(1u<<k);
        }
#else
        memcpy(pve_nav_height,bg_pve_nav_heights,sizeof(pve_nav_height));memcpy(pve_nav_edges,bg_pve_nav_links,sizeof(pve_nav_edges));memcpy(pve_nav_layers,bg_pve_nav_layers,sizeof(pve_nav_layers));
#endif
        pve_routes_reset(true);loaded=true;
    }
    pve_routes_reset(false);
}
#include "pve_routes.inc"
