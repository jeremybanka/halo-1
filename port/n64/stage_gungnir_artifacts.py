"""Stage the private development library inside a fresh guarded output.

Promotion is a separate metadata rename. Inputs, including failed candidates,
remain in their original owning checkout and are never moved or overwritten.
"""
import argparse,hashlib,json,shutil
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]

def run(output):
    output.mkdir(parents=True,exist_ok=True);library=output/'demake-20261102';generated=output/'generated';library.mkdir();generated.mkdir();copied=[]
    def copy(source,target):
        source=ROOT/source
        if source.is_dir():
            target.mkdir(parents=True,exist_ok=True)
            for item in source.iterdir():
                if item.is_file() and item.suffix not in ('.dylib','.so'):copy(item.relative_to(ROOT),target/item.name)
                elif item.is_dir():copy(item.relative_to(ROOT),target/item.name)
        else:
            assert source.is_file(),source;target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target);copied.append(dict(input=str(source.relative_to(ROOT)),output=str(target.relative_to(output)),sha256=hashlib.sha256(source.read_bytes()).hexdigest()))
    for name,src in [('source','gungnir-source-v2'),('reference','gungnir-reference-v2'),('motion','gungnir-motion-v3'),('pilot','gungnir-pilot-review-v4'),('lods','gungnir-contact-returns-v2'),('library','gungnir-library-candidate-v1'),('firstperson','gungnir-firstperson-candidate-v1')]:copy(Path('build')/src,library/name)
    copy(Path('build/gungnir-shoulder-pilot-v1/shoulder-pilot.json'),library/'pilot/shoulder-pilot.json')
    for name in ('gungnir-source-joints-v4','gungnir-plate-fit-v1','gungnir-local-cloth-v2','gungnir-local-cloth-v3'):copy(Path('build')/name,library/'stages'/name)
    for src,name in [
        ('gungnir-export-candidate-v1/export-validation.json','export-validation.json'),
        ('gungnir-shape-candidate-v2/shape-validation.json','shape-validation.json'),
        ('gungnir-review-candidate-v1/coverage.json','coverage.json'),
        ('gungnir-packed-review-candidate-v1/coverage.json','packed-coverage.json'),
        ('gungnir-contact-facing-clearance-v1/clearance.json','clearance.json'),
        ('gungnir-runtime-test-candidate-v1/runtime-validation.json','runtime-validation.json'),
        ('gungnir-firstperson-test-candidate-v1/firstperson-validation.json','firstperson-validation.json'),
        ('gungnir-gameplay-test-v13/gameplay-validation.json','gameplay-validation.json'),
        ('gungnir-gameplay-test-v13/gameplay.log','gameplay.log'),
        ('gungnir-navigation-proof-v2/navigation-validation.json','navigation-validation.json'),
        ('gungnir-source-control-review-v3/coverage.json','source-control-coverage.json'),
        ('gungnir-source-facing-clearance-v1/clearance.json','source-control-clearance.json')]:copy(Path('build')/src,library/'review'/name)
    for name in ('gungnir-review-candidate-v1','gungnir-packed-review-candidate-v1','gungnir-contact-facing-clearance-v1','gungnir-comparison-candidate-v1'):
        for file in (ROOT/'build'/name).glob('*.png'):copy(file.relative_to(ROOT),library/'review'/name/file.name)
    copy(Path('build/gungnir-comparison-candidate-v1/comparison.json'),library/'review/comparison.json')
    copy(Path('build/gungnir-bank-candidate-v1'),generated)
    for file in (ROOT/'build/gungnir-autonav-v7').glob('autonav-*.bin'):copy(file.relative_to(ROOT),generated/file.name)
    copy(Path('build/gungnir-bank-candidate-v1/gungnir.bin'),output/'gungnir.bin')
    (library/'README.md').write_text('''# GUNGNIR development snapshot

Owned Halo: Reach source, intact reference, semantic shoulder pilot, independent
82-bone native rig, editable BLEND, near/far body GLBs, N64 bank and evidence.
The source checkpoints and all original extraction hashes are preserved.

This is a **development candidate**, not an accepted demake. The current body is
868/598 packed vertices and 1117/727 triangles, body only. The production rifle
is separate. Runtime, GLB and first-person tests pass; appearance observations
still contain coverage deviations and a small ankle/plate overlap. Native Ares
visual, memory and RDP inspection is pending because the Mac was locked.

`review/coverage.json` and `packed-coverage.json` retain every probe, including
failures. `review/clearance.json` retains isolated and front-face depth results.
Do not relabel these observations as zero-gap or native acceptance.

Source texture references preserve the original extraction file verbatim.
The public `gungnir_assets.texture_path` resolver finds this snapshot's sibling
`source/textures` after restoration; BLEND images are packed. `stages` preserves
the immutable reduction checkpoint and subsequent fitting inputs. Rebuilding a
new reduction with the evolving generator requires its own review; downstream
refinements can start from the preserved checkpoints.

See public `port/n64/GUNGNIR.md`, `CHARACTER_DEMAKE.md` and `JORGE_LODS.md`.
''')
    (output/'staging-provenance.json').write_text(json.dumps(copied,indent=2)+'\n');print('STAGED',len(copied),'private payloads')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);a=p.parse_args();run(a.output)
