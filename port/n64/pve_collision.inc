/* Authored collision polygons animated with the same sampled source poses as
 * rendering. Material identity survives to damage: Jackal shield gaps and
 * Hunter skin are not approximated by a whole-body shield or head sphere. */
static int16_t pve_hit_pose[BG_PVE_MAX][1024][3];
static float pve_hit_normals[BG_PVE_MAX][3];
static uint32_t pve_hit_keys[BG_PVE_MAX];
static uint16_t pve_hit_generations[BG_PVE_MAX];
static bool pve_clip_once(unsigned clip){return clip==PVE_DEATH||clip==PVE_MELEE||clip==PVE_THROW||clip==PVE_EXIT||clip==PVE_EVADE_LEFT||clip==PVE_EVADE_RIGHT;}
static void pve_clip_frame(const bg_pve_animation*c,unsigned clip,float time,unsigned*first,unsigned*second,int*weight){
    float phase=time/fmaxf(c->duration,.001f);if(pve_clip_once(clip))phase=fminf(phase,.99999f);else phase-=floorf(phase);
    float frame=phase*(c->frames-1);*first=(unsigned)frame;*second=*first+1<c->frames?*first+1:*first;*weight=(frame-*first)*256;
}
static float pve_triangle_ray(const float*o,const float*d,const float*a,const float*b,const float*c,float nearest){
    float ab[3],ac[3],h[3],s[3],q[3];sub(ab,b,a);sub(ac,c,a);
    h[0]=d[1]*ac[2]-d[2]*ac[1];h[1]=d[2]*ac[0]-d[0]*ac[2];h[2]=d[0]*ac[1]-d[1]*ac[0];
    float det=dot(ab,h);if(fabsf(det)<1e-8f)return nearest;float inv=1/det;sub(s,o,a);float u=dot(s,h)*inv;if(u<0||u>1)return nearest;
    q[0]=s[1]*ab[2]-s[2]*ab[1];q[1]=s[2]*ab[0]-s[0]*ab[2];q[2]=s[0]*ab[1]-s[1]*ab[0];
    float v=dot(d,q)*inv;if(v<0||u+v>1)return nearest;float hit=dot(ac,q)*inv;return hit>=0&&hit<nearest?hit:nearest;
}
float bg_pve_hit_ray(unsigned unit,const float o[3],const float dir[3],float nearest,int*region){
    if(unit<BG_PLAYERS||unit>=BG_PLAYERS+bg_pve_count)return nearest;
    unsigned i=unit-BG_PLAYERS;bg_player*p=&bg_players[unit];bg_pve_actor*a=&bg_pve_actors[i];
    if(!a->occupied||a->arrival==1)return nearest;
    float delta[3];sub(delta,o,p->pos);float along=-dot(delta,dir);if(along< -2||along>nearest+2)return nearest;
    float perpendicular=dot(delta,delta)-along*along;if(perpendicular>4)return nearest;
    const bg_pve_hit_mesh*m=&bg_pve_hits[a->kind];const bg_pve_animation*c=&m->clips[a->clip];
    unsigned f0,f1;int mix;pve_clip_frame(c,a->clip,a->time,&f0,&f1,&mix);
    uint32_t key=1u+(a->kind<<28)+(a->clip<<24)+(f0<<16)+(f1<<8)+mix;
    assert(c->vertices<=1024);
    if(pve_hit_keys[i]!=key||pve_hit_generations[i]!=a->generation){
        for(unsigned v=0;v<c->vertices;v++)for(unsigned axis=0;axis<3;axis++){
            unsigned track=c->indices[v];int x=c->positions[(f0*c->tracks+track)*3+axis],y=c->positions[(f1*c->tracks+track)*3+axis];
            pve_hit_pose[i][v][axis]=c->origin[axis]+x+((y-x)*mix>>8);
        }
        pve_hit_keys[i]=key;pve_hit_generations[i]=a->generation;
    }
    float co=cosf(p->yaw),si=sinf(p->yaw),origin[3]={co*delta[0]-si*delta[2],delta[1],si*delta[0]+co*delta[2]},direction[3]={co*dir[0]-si*dir[2],dir[1],si*dir[0]+co*dir[2]};
    for(unsigned t=0;t<m->triangles_count;t++){
        unsigned material=m->materials[t];const bg_pve_hit_material*r=&m->rules[material];
        if(a->kind==BG_PVE_JACKAL&&p->shield<=0&&r->shield_scale>0&&r->body_scale==0)continue;
        float corners[3][3];for(unsigned v=0;v<3;v++)for(unsigned axis=0;axis<3;axis++)corners[v][axis]=pve_hit_pose[i][m->triangles[t][v]][axis]/128.f;
        float hit=pve_triangle_ray(origin,direction,corners[0],corners[1],corners[2],nearest);
        if(hit<nearest){
            nearest=hit;*region=((material+1)<<8)|(r->head?2:1);
            float ab[3],ac[3],normal[3];sub(ab,corners[1],corners[0]);sub(ac,corners[2],corners[0]);normal[0]=ab[1]*ac[2]-ab[2]*ac[1];normal[1]=ab[2]*ac[0]-ab[0]*ac[2];normal[2]=ab[0]*ac[1]-ab[1]*ac[0];normalize(normal);
            if(dot(normal,direction)>0)for(unsigned k=0;k<3;k++)normal[k]=-normal[k];
            pve_hit_normals[i][0]=co*normal[0]+si*normal[2];pve_hit_normals[i][1]=normal[1];pve_hit_normals[i][2]=-si*normal[0]+co*normal[2];
        }
    }
    return nearest;
}

static bool pve_needle_impact(bg_projectile*q,int target,int region){
    unsigned i=target-BG_PLAYERS;bg_pve_actor*a=&bg_pve_actors[i];const bg_pve_hit_mesh*m=&bg_pve_hits[a->kind];int material=(region>>8)-1;
    if(material<0||(unsigned)material>=m->material_count)return false;
    unsigned type=m->rules[material].material;
    if(a->kind==BG_PVE_ELITE&&bg_players[target].shield>0)type=bg_pve_definitions[a->kind].shield_material;
    if(!bg_pve_needle_reflect[type])return false;
    float normal[3];memcpy(normal,pve_hit_normals[i],12);float along=dot(q->velocity,normal),direction[3];
    for(unsigned k=0;k<3;k++)direction[k]=q->velocity[k]-2*along*normal[k];
    float speed=sqrtf(dot(direction,direction))*(1-bg_pve_needle_friction[type]);normalize(direction);
    bg_combat_cone(direction,0,bg_pve_needle_noise[type],pve_random01(),pve_random01(),q->velocity);
    for(unsigned k=0;k<3;k++){q->velocity[k]*=speed;q->pos[k]+=normal[k]*.02f;}
    q->tracked=-1;return true;
}
