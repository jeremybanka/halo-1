"""Build a private zero-directional-light / FX-none Tiny3D experiment.

The installed library is never changed. This patches the pinned generated
assembly, keeps DMEM and triangle/clipping code intact, and regenerates the
overlay metadata. Ambient color multiplication, fog, UV, MVP and clipping
arithmetic are retained. The public C setters reject unsupported modes.
"""
import argparse, hashlib, json, shutil, subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DEFAULT=ROOT.parent/'n64-3d-splitscreen/.build/tiny3d'
SDK=ROOT.parent/'n64-2048/.build/libdragon'

def build(out, source=DEFAULT):
    out.mkdir(parents=True,exist_ok=True)
    for name in ('src','Makefile','LICENSE'):
        if (source/name).is_dir():shutil.copytree(source/name,out/name,dirs_exist_ok=True)
        else:shutil.copy2(source/name,out/name)
    path=out/'src/t3d/rsp/rsp_tiny3d.S';s=path.read_text();original=s
    def replace(a,b):
        nonlocal s
        assert s.count(a)==1,(a,s.count(a))
        s=s.replace(a,b)
    start=s.index('  ori $s6, $zero, %lo(MATRIX_NORMAL)\n')
    end=s.index('  lbu $s1, %lo(FOG_STORE_OFFSET + 0)',start)
    s=s[:start]+'''  jal loadCurrentMVPMat ## unchanged position matrix
  nop
'''+s[end:]
    replace('  vand $v07, $v17, $v08.h3\n  vmudn $v07, $v07, $v16.v\n','')
    replace('  vmulf $v06, $v20, $v07.h0\n','')
    replace('  vmacf $v06, $v19, $v07.h1\n  vmacf $v07, $v18, $v07.h2\n','')
    replace('  lhu $k1, %lo(VERTEX_FX_FUNC + 0)\n','')
    # Zero-light branch executes only the delay-slot MVP multiply before
    # loading source RGBA. Remove the unreachable directional/point loop.
    start=s.index('  beq $s3, $s2, LABEL_0002\n')
    end=s.index('  LABEL_0006:\n',start)
    s=s[:start]+'''  vmadh $v05, $v21, $v08.h3
  luv $v04, 0, 16, $s4
'''+s[end:]
    replace('  vor $v02, $v00, $v07\n','')
    replace('  vand $v07, $v17, $v08.h3\n','')
    replace('  vmudn $v07, $v07, $v16.v\n','')
    replace('  jal $k1\n','')
    start=s.index('  jal normalizeMatrixVector ## Args: $s4, $t1\n')
    end=s.index('  jal mulMat4Mat4 ## Args: $s2, $s3, $s4\n',start)
    s=s[:start]+'''  ori $s2, $zero, %lo(MATRIX_MVP)
  ori $s3, $zero, %lo(MATRIX_PROJ)
'''+s[end:]
    # Unused light loads are scalar/vector setup without position dependencies.
    for line in ('  lbu $s2, %lo(ACTIVE_LIGHT_SIZE + 0)\n',
                 '  addiu $s2, $s2, %lo(LIGHT_DIR_COLOR)\n',
                 '  ori $s3, $zero, %lo(LIGHT_DIR_COLOR)\n',
                 '  lpv $v02, 0, 8, $s3\n','  lbu $t9, 15($s3)\n',
                 '  or $t8, $zero, $zero\n'):
        replace(line,'')
    path.write_text(s)
    cpath=out/'src/t3d/t3d.c';c=cpath.read_text()
    c=c.replace('void t3d_light_set_count(int count)\n{','void t3d_light_set_count(int count)\n{\n  assertf(count==0,"Private unlit microcode: nonzero light count");')
    anchor='void t3d_state_set_vertex_fx(enum T3DVertexFX func, int16_t arg0, int16_t arg1)\n{'
    assert anchor in c
    c=c.replace(anchor,anchor+'\n  assertf(func==T3D_VERTEX_FX_NONE,"Private unlit microcode: vertex FX unsupported");')
    cpath.write_text(c)
    subprocess.run(['make','-j4','N64_INST='+str(SDK)],cwd=out,check=True)
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    manifest=dict(source=str(source),original_assembly_sha256=hashlib.sha256(original.encode()).hexdigest(),
        assembly_sha256=sha(path),library_sha256=sha(out/'build/libt3d.a'),
        clipping_unchanged=sha(out/'src/t3d/rsp/rsp_tiny3d_clipping.S')==sha(source/'src/t3d/rsp/rsp_tiny3d_clipping.S'),
        removed_source_lines=len(original.splitlines())-len(s.splitlines()),
        preconditions=['zero active directional/point lights','vertex FX none'],
        limits=['Experimental assembly scheduling requires native pixel and command validation before adoption'])
    (out/'unlit-manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps(manifest))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);args=p.parse_args();build(args.output.resolve())
