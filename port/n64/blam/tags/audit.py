#!/usr/bin/env python3
"""Audit the native gameplay tag graph in the user's extracted Xbox caches.

Unlike the rendering pipeline, this never calls meta_to_tag_data: runtime
tick-based values, flags and original IDs must not be converted to HEK units.
"""
import argparse, collections, contextlib, hashlib, json
from pathlib import Path

WEAPONS=('assault rifle','pistol','plasma pistol','plasma rifle','needler',
         'shotgun','sniper rifle','rocket launcher')
EXPORT_CLASSES={'bipd','vehi','weap','proj','jpt!','phys'}


def nodes(block,path=''):
    """Visit fixed metadata blocks and reflexive elements, never raw payloads."""
    if not hasattr(block,'desc') or not isinstance(block,(list,tuple)):
        return
    yield path,block
    for i,child in enumerate(block):
        name=block.desc.get(i,block.desc.get('SUB_STRUCT',{})).get('NAME',str(i))
        yield from nodes(child,f'{path}.{name}' if path else name)
    if block.desc['TYPE'].name=='Reflexive':
        for i,child in enumerate(block.STEPTREE if isinstance(block.STEPTREE,(list,tuple)) else ()):
            yield from nodes(child,f'{path}[{i}]')


def metadata_size(meta):
    size=meta.desc['SIZE'];raw=0
    for _,block in nodes(meta):
        kind=block.desc['TYPE'].name
        if kind=='Reflexive':
            step=block.STEPTREE
            if isinstance(step,(list,tuple)):
                size+=sum(item.desc['SIZE'] for item in step)
            elif isinstance(step,(bytes,bytearray,memoryview)):raw+=len(step)
            elif hasattr(step,'data'):raw+=len(step.data)
        elif kind=='RawdataRef':raw+=block.size
    return size,raw


class CacheGraph:
    def __init__(self,maps):
        from reclaimer.meta.wrappers.halo1_map import Halo1Map
        self.caches={};self.metas={};self.sources={}
        for name in ('bloodgulch','a30'):
            path=maps/f'{name}-decompressed.map'
            cache=Halo1Map();cache.load_map(path);self.caches[name]=cache
            self.sources[name]={'path':str(path.resolve()),'sha256':hashlib.sha256(path.read_bytes()).hexdigest()}

    def root_ids(self):
        wanted=[('bloodgulch','weap',fr'weapons\{w}\{w}') for w in WEAPONS]
        wanted.extend(('bloodgulch',cls,path) for cls,path in (
            ('bipd',r'characters\cyborg_mp\cyborg_mp'),
            ('vehi',r'vehicles\warthog\warthog'),
            ('vehi',r'vehicles\ghost\ghost_mp'),
            ('vehi',r'vehicles\scorpion\scorpion_mp')))
        wanted.append(('a30','vehi',r'vehicles\banshee\banshee'))
        result=[]
        for cache,cls,path in wanted:
            entries=self.caches[cache].tag_index.tag_index
            i=next(i for i,e in enumerate(entries) if e.class_1.data==int.from_bytes(cls.encode(),'big') and e.path==path)
            result.append((cache,i))
        return result

    def entry(self,key):return self.caches[key[0]].tag_index.tag_index[key[1]]
    def meta(self,key):
        if key not in self.metas:
            self.metas[key]=self.caches[key[0]].get_meta(key[1],ignore_rawdata=True,disable_tag_cleaning=True)
        return self.metas[key]

    def audit(self):
        from reclaimer.util import int_to_fourcc
        roots=self.root_ids();queue=collections.deque(roots);seen=set();tags=[];errors=[]
        while queue:
            key=queue.popleft()
            if key in seen:continue
            seen.add(key);entry=self.entry(key);meta=self.meta(key);refs=[]
            cls=int_to_fourcc(entry.class_1.data)
            if meta is None:
                errors.append({'cache':key[0],'index':key[1],'class':cls,'path':entry.path});continue
            size,raw=metadata_size(meta)
            for path,block in nodes(meta):
                if block.desc['TYPE'].name!='TagRef' or block.id==0xffffffff:continue
                target=(key[0],block.id&65535)
                if target[1]>=len(self.caches[key[0]].tag_index.tag_index):
                    errors.append({'cache':key[0],'index':key[1],'field':path,'invalid_reference':block.id});continue
                target_entry=self.entry(target)
                if target_entry.id != block.id:
                    errors.append({'cache':key[0],'index':key[1],'field':path,
                                   'reference_salt':block.id,'target_salt':target_entry.id})
                    continue
                refs.append({'field':path,'target':f'{target[0]}:{target[1]}','source_id':block.id,
                             'class':int_to_fourcc(target_entry.class_1.data),'path':target_entry.path})
                queue.append(target)
            tags.append({'key':f'{key[0]}:{key[1]}','cache':key[0],'index':key[1],'source_id':entry.id,
                         'class':cls,'parents':[int_to_fourcc(entry.class_2.data),int_to_fourcc(entry.class_3.data)],
                         'path':entry.path,'fixed_and_reflexive_bytes':size,'raw_payload_bytes':raw,
                         'export_candidate':cls in EXPORT_CLASSES,'references':refs})
        tags.sort(key=lambda t:(t['cache'],t['index']))
        classes={}
        for tag in tags:
            value=classes.setdefault(tag['class'],{'tags':0,'metadata_bytes':0,'raw_payload_bytes':0})
            value['tags']+=1;value['metadata_bytes']+=tag['fixed_and_reflexive_bytes'];value['raw_payload_bytes']+=tag['raw_payload_bytes']
        return {'sources':self.sources,'roots':[f'{a}:{b}' for a,b in roots],'classes':classes,
                'metadata_bytes':sum(t['fixed_and_reflexive_bytes'] for t in tags),
                'tag_count':len(tags),'tags':tags,'errors':errors,
                'scope':'Fixed tag structures and parsed reflexive metadata only; no name strings, raw data, bitmap pixels, audio samples, compressed animation frames or model vertex/index payloads.'}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--maps',type=Path,default=Path('build/n64/assets'))
    p.add_argument('--output',type=Path,default=Path('build/n64/blam-tags'));a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True)
    with (a.output/'audit.log').open('w') as log,contextlib.redirect_stdout(log):
        graph=CacheGraph(a.maps);report=graph.audit()
    (a.output/'graph.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('tag_count','metadata_bytes','classes','errors')},indent=2))

if __name__=='__main__':main()
