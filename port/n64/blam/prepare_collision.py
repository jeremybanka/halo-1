#!/usr/bin/env python3
"""Extract complete original BSP collision functions with explicit Xbox widths."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[3]


def function(text,name):
    # Mask comments/strings while preserving offsets for balanced C braces.
    clean=re.sub(r'/\*.*?\*/|//[^\n]*|"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'',
                 lambda m:' '*len(m.group()),text,flags=re.S)
    for match in re.finditer(r'(?m)^[\w *]+\b'+re.escape(name)+r'\s*\(',clean):
        start=match.start();at=clean.index('(',match.start());depth=1;at+=1
        while depth:
            depth+=(clean[at]=='(')-(clean[at]==')');at+=1
        while clean[at].isspace():at+=1
        if clean[at]!='{':continue
        depth=1;at+=1
        while depth:
            depth+=(clean[at]=='{')-(clean[at]=='}');at+=1
        return text[start:at]+'\n'
    raise RuntimeError('No complete function: '+name)


def prepare(output):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    sources={
        'source/math/real_math.h':['set_real_point2d','vector_from_points2d','cross_product2d',
            'projection_sign_from_vector3d','project_point3d','dot_product3d','plane3d_distance_to_point'],
        'source/physics/bsp2d.c':['bsp2d_test_point'],
        'source/physics/collision_bsp.c':['collision_surface_test_point','collision_leaf_test_vector',
            'collision_bsp_test_vector_recursive','collision_bsp_test_vector'],
    }
    math_path='source/math/real_math.c';math_text=(ROOT/math_path).read_text()
    start=math_text.index('short const global_projection3d_mappings[3][2][2] =')
    table=math_text[start:math_text.index(';',start)+1]
    chunks=['/* '+math_path+': original projection-axis table */\n'+table]
    manifest=[{'source':math_path,'sha256':hashlib.sha256(math_text.encode()).hexdigest(),
               'retained_data':['global_projection3d_mappings'],'adaptations':[]}]
    for path,names in sources.items():
        original=(ROOT/path).read_text()
        record={'source':path,'sha256':hashlib.sha256(original.encode()).hexdigest(),'functions':[]}
        for name in names:
            text=function(original,name);changes=[]
            if '__inline ' in text:
                text=text.replace('__inline ','static inline ');changes.append('MSVC inline spelling/linkage')
            # On N64 int32_t is the same width and sign as original long.
            text=re.sub(r'\bunsigned long\b','uint32_t',text)
            text=re.sub(r'\blong\b','int32_t',text)
            text=text.replace('LONG_MIN','INT32_MIN').replace('LONG_MAX','INT32_MAX')
            changes.append('Explicit Xbox 32-bit long and bit masks for host/N64 agreement')
            if name=='collision_bsp_test_vector':
                text=text.replace('\tshort collision_function = 4 + (bsp == global_collision_bsp);\n','')
                text=text.replace('\tcollision_log_usage(collision_function);\n','')
                text=text.replace('\tcollision_log_start_time(&collision_bsp_usage_times.vector);\n','')
                text=text.replace('\tcollision_log_end_time(\n\t\tcollision_function,\n\t\tcollision_bsp_usage_times.vector.QuadPart);\n','')
                if 'collision_log_' in text:raise RuntimeError('Collision timing boundary changed')
                changes.append('Xbox profiling timers omitted; collision arithmetic unchanged')
            chunks.append('/* '+path+': '+name+' */\n'+text)
            record['functions'].append({'name':name,'adaptations':changes})
        manifest.append(record)
    (output/'collision_original.c').write_text('\n'.join(chunks))
    (output/'collision-source-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    return output


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/n64/blam-core')
    print(prepare(parser.parse_args().output))
