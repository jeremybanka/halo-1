#!/usr/bin/env python3
"""Export bounded native gameplay metadata with big-endian scalar/pointer fixups.

The package deliberately leaves renderer/animation/collision/effect tags as
unbound registry entries. It is an inspectable loader input, not a runnable
replacement for the complete original cache or the demake's asset bank.
"""
import argparse,contextlib,json,re,struct
from pathlib import Path
from audit import CacheGraph,EXPORT_CLASSES

MAGIC=0x42475447
HANDLE_BASE=0x4e640000


class Writer:
    def __init__(self,graph,report,layouts):
        self.graph=graph;self.report=report;self.layouts=layouts
        self.data=bytearray(4);self.coverage=bytearray(4);self.relocations=[];self.fields=[];self.omitted=[]
        self.records=[];self.by_key={t['key']:t for t in report['tags']};self.strings={}
        self.handles={t['key']:HANDLE_BASE+i for i,t in enumerate(report['tags'])}
        if len(self.handles)>65535:raise ValueError('Tag handle capacity exceeded')

    def alloc(self,size):
        offset=(len(self.data)+3)&~3;self.data.extend(bytes(offset+size-len(self.data)))
        self.coverage.extend(bytes(len(self.data)-len(self.coverage)));return offset

    def string(self,text):
        if text not in self.strings:
            encoded=text.encode('latin1')+b'\0';offset=self.alloc(len(encoded))
            self.data[offset:offset+len(encoded)]=encoded;self.coverage[offset:offset+len(encoded)]=b'\1'*len(encoded)
            self.strings[text]=offset
        return self.strings[text]

    def write32(self,offset,value):
        struct.pack_into('>I',self.data,offset,value&0xffffffff);self.coverage[offset:offset+4]=b'\1'*4

    def pointer(self,offset,target):
        self.write32(offset,target)
        if target:self.relocations.append([offset,target])

    def swap(self,cache,file_offset,output,width,path,runtime=False):
        source=bytes(cache.map_data[file_offset:file_offset+width])
        if len(source)!=width:raise ValueError('Scalar outside source cache')
        self.data[output:output+width]=source[::-1];self.coverage[output:output+width]=b'\1'*width
        self.fields.append({'tag':self.current,'path':path,'offset':output,'bytes':width,
                            'source_file_offset':file_offset,'runtime':runtime})

    def visit(self,cache,block,file_offset,output,path):
        desc=block.desc;kind=desc['TYPE'].name;size=desc['SIZE']
        self.data[output:output+size]=cache.map_data[file_offset:file_offset+size]
        if kind=='TagRef':
            self.swap(cache,file_offset,output,4,path+'.class')
            source_id=block.id
            if source_id==0xffffffff:
                self.pointer(output+4,0);self.write32(output+8,0);self.write32(output+12,0xffffffff)
            else:
                target=f'{self.cache_name}:{source_id&65535}'
                if target not in self.handles:raise ValueError('Unresolved tag reference '+target)
                name=self.by_key[target]['path'];self.pointer(output+4,self.string(name))
                self.write32(output+8,len(name));self.write32(output+12,self.handles[target])
            return
        if kind=='Reflexive':
            step=block.STEPTREE
            if not isinstance(step,(list,tuple)):
                self.omitted.append({'tag':self.current,'path':path,'kind':'raw_reflexive','count':block.size})
                self.write32(output,0);self.pointer(output+4,0);self.write32(output+8,0);return
            count=len(step);self.write32(output,count);self.write32(output+8,0)
            if not count:self.pointer(output+4,0);return
            stride=step[0].desc['SIZE'];target=self.alloc(stride*count);self.pointer(output+4,target)
            source=cache.map_pointer_converter.v_ptr_to_f_ptr(block.pointer)
            for i,child in enumerate(step):self.visit(cache,child,source+i*stride,target+i*stride,f'{path}[{i}]')
            return
        if kind=='RawdataRef':
            self.omitted.append({'tag':self.current,'path':path,'kind':'raw_data','bytes':block.size})
            self.data[output:output+size]=bytes(size);self.coverage[output:output+size]=b'\1'*size;return
        for i,value in enumerate(block):
            child=desc[i];offset=desc['ATTR_OFFS'][i];dtype=child['TYPE'];name=child['NAME'];field=f'{path}.{name}'
            if isinstance(value,(list,tuple)) and hasattr(value,'desc'):
                self.visit(cache,value,file_offset+offset,output+offset,field)
            elif dtype.size in (1,2,4,8) and re.fullmatch(r'[<>!=@]?[bBhHiIlLqQfd]',dtype.enc or ''):
                self.swap(cache,file_offset+offset,output+offset,dtype.size,field)
            elif isinstance(value,(str,bytes,bytearray)):
                width=child.get('SIZE',dtype.size)
                if not isinstance(width,int):raise ValueError('Unsupported variable field '+field)
                self.coverage[output+offset:output+offset+width]=b'\1'*width
            else:raise ValueError(f'Unsupported fixed field {field}: {dtype.name}')
        extra=self.layouts['runtime_fields'].get(desc['NAME'],{}).get('fields',{})
        for name,info in extra.items():
            offset=info['offset'];width=info['bytes']
            if offset+width>size:raise ValueError('Native layout exceeds descriptor '+path)
            self.swap(cache,file_offset+offset,output+offset,width,path+'.'+name,True)

    def build(self):
        for tag in self.report['tags']:
            self.current=tag['key'];self.cache_name=tag['cache'];cache=self.graph.caches[tag['cache']]
            name=self.string(tag['path']);offset=0xffffffff;fixed=0
            if tag['class'] in EXPORT_CLASSES:
                key=(tag['cache'],tag['index']);meta=self.graph.meta(key);fixed=meta.desc['SIZE']
                offset=self.alloc(fixed);source=cache.map_pointer_converter.v_ptr_to_f_ptr(self.graph.entry(key).meta_offset)
                self.visit(cache,meta,source,offset,'tag')
            self.records.append({'key':tag['key'],'id':self.handles[tag['key']],'class':tag['class'],
                                 'parents':tag['parents'],'offset':offset,'size':fixed,'name_offset':name})
        unknown=[]
        for i,(value,known) in enumerate(zip(self.data,self.coverage)):
            if value and not known:
                if unknown and unknown[-1]['offset']+unknown[-1]['bytes']==i:unknown[-1]['bytes']+=1
                else:unknown.append({'offset':i,'bytes':1})
        records=b''.join(struct.pack('>7I',r['id'],int.from_bytes(r['class'].encode('latin1'),'big'),
            *(int.from_bytes(p.encode('latin1'),'big') for p in r['parents']),r['offset'],r['size'],r['name_offset']) for r in self.records)
        self.relocations.sort()
        if len({r[0] for r in self.relocations}) != len(self.relocations):
            raise ValueError('Duplicate pointer relocation')
        if unknown:raise ValueError('Unclassified nonzero metadata; refusing an incomplete endian conversion')
        relocs=b''.join(struct.pack('>2I',*r) for r in self.relocations)
        relocation_offset=32+len(records);payload_offset=relocation_offset+len(relocs)
        header=struct.pack('>8I',MAGIC,1,len(self.records),32,len(self.relocations),relocation_offset,payload_offset,len(self.data))
        manifest={'format':'BGTG/1','target_endian':'big','records':self.records,'relocations':self.relocations,
                  'sources':self.graph.sources,
                  'scalar_fields':self.fields,'omitted_payloads':self.omitted,'unknown_nonzero_ranges':unknown,
                  'payload_bytes':len(self.data),'file_bytes':payload_offset+len(self.data),
                  'exported_tags':sum(r['size']>0 for r in self.records),'unbound_tags':sum(r['size']==0 for r in self.records),
                  'scope':'Native gameplay metadata prototype; no original simulation or original model/animation/collision backend is bound.'}
        return header+records+relocs+self.data,manifest


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--maps',type=Path,default=Path('build/n64/assets'))
    p.add_argument('--output',type=Path,default=Path('build/n64/blam-tags'));a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True);layouts=json.loads((a.output/'layouts.json').read_text())
    with (a.output/'export.log').open('w') as log,contextlib.redirect_stdout(log):
        graph=CacheGraph(a.maps);report=graph.audit()
        if report['errors']:raise ValueError('Tag graph contains invalid references')
        bank,manifest=Writer(graph,report,layouts).build()
    (a.output/'gameplay-tags.bgtg').write_bytes(bank)
    (a.output/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print(json.dumps({k:manifest[k] for k in ('payload_bytes','file_bytes','exported_tags','unbound_tags','omitted_payloads','unknown_nonzero_ranges')},indent=2))

if __name__=='__main__':main()
