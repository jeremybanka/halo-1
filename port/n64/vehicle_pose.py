"""Bake an original rigid vehicle pose into the reduction input mesh."""


def globals_for(nodes):
    result=[]
    for node in nodes:
        x,y,z,w=node['q'];p=node['p']
        # Xbox/JMS rotations use the conjugate of the usual column-vector form.
        r=[[1-2*(y*y+z*z),2*(x*y+z*w),2*(x*z-y*w)],
           [2*(x*y-z*w),1-2*(x*x+z*z),2*(y*z+x*w)],
           [2*(x*z+y*w),2*(y*z-x*w),1-2*(x*x+y*y)]]
        if node['parent']>=0:
            pr,pp=result[node['parent']]
            p=[pp[i]+sum(pr[i][j]*p[j] for j in range(3)) for i in range(3)]
            r=[[sum(pr[i][k]*r[k][j] for k in range(3)) for j in range(3)] for i in range(3)]
        result.append((r,p))
    return result


def bake_pose(model,states,source_name):
    bind=globals_for(model['nodes'])
    posed_nodes=[{**node,'p':state['p'],'q':state['q']} for node,state in zip(model['nodes'],states)]
    pose=globals_for(posed_nodes);vertices=[]
    for p,(first,second,weight) in zip(model['vertices'],model['weights']):
        result=[0.,0.,0.]
        for bone,w in [(first,1-weight)]+([(second,weight)] if second>=0 and weight>0 else []):
            rotation,origin=bind[bone];target,position=pose[bone]
            local=[sum(rotation[j][i]*(p[j]-origin[j]) for j in range(3)) for i in range(3)]
            for i in range(3):result[i]+=w*(position[i]+sum(target[i][j]*local[j] for j in range(3)))
        vertices.append(result)
    model['bind_nodes']=model['nodes'];model['nodes']=posed_nodes;model['vertices']=vertices
    model['baked_vehicle_pose']=source_name
