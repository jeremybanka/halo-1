"""Read the owned CE animation cache for Jorge's additional gameplay clips."""
import contextlib,json
from pathlib import Path
from reclaimer.meta.wrappers.halo1_map import Halo1Map
from reclaimer.animation.animation_decompilation import extract_animation
ROOT=Path(__file__).resolve().parents[2];A=ROOT/'halo64-assets';OUT=A/'assets/jorge/playable-half'
def run():
    report=json.loads((A/'generated/interaction-report.json').read_text())
    names=['stand rifle ready']+[r['name'] for r in report['locomotion']]+[r['name'] for group in report['body_clips'] for r in group]
    with (OUT/'motion-extraction.log').open('w') as log,contextlib.redirect_stdout(log):
        h=Halo1Map();h.load_map(A/'assets/bloodgulch-decompressed.map')
        ix=next(i for i,t in enumerate(h.tag_index.tag_index) if t.class_1.enum_name=='model_animations' and t.path==r'characters\cyborg\cyborg')
        graph=h.get_meta(ix);h.meta_to_tag_data(graph,'antr',h.tag_index.tag_index[ix]);clips={}
        for name in names:
            i=next(i for i,a in enumerate(graph.animations.STEPTREE) if a.name==name)
            a=extract_animation(i,graph,write_jma=False);count=graph.animations.STEPTREE[i].frame_count
            clips[name]={'name':name,'type':'base','duration':count/30,'rot_flags':0,'trans_flags':0,'frames':[[{'p':[n.pos_x/100,n.pos_y/100,n.pos_z/100],'q':[n.rot_i,n.rot_j,n.rot_k,n.rot_w]} for n in f] for f in a.frames[:count]]}
    (OUT/'ce-motion-source.json').write_text(json.dumps(clips,separators=(',',':'))+'\n')
    print('Extracted',len(clips),'gameplay clips')
if __name__=='__main__':run()
