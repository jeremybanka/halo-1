"""Extract the owned retail Reach SWAT / Slayer recordings for match starts.

Reach snd!/ugh!/zone/play layouts follow the local Reclaimer HaloReach source.
Sound resources interleave localized blocks across primary/secondary pages;
read their size groups and select the named permutation's block ranges, even
when it is the only permutation. Never decode the other languages as its tail.
"""
import argparse,hashlib,json,struct,subprocess,wave
from pathlib import Path
from reach_cache import ReachCache


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def sound_resource(cache,ident):
    zone=cache.by_class['zone'][0]['offset'];play=cache.by_class['play'][0]['offset']
    entries=cache.block(zone+88,64);entry=entries[ident&65535];segment_id=cache.unpack('h',entry+34)[0]
    if segment_id<0:raise ValueError('This cache omits the sound resource; use a resident retail campaign cache such as m05.map')
    segment=cache.block(play+48,16)[segment_id]
    primary,secondary,first,second,first_size,second_size=cache.unpack('2h2i2h',segment)
    groups=[];length=0
    for page_id,offset,size_id in ((primary,first,first_size),(secondary,second,second_size)):
        if page_id<0 or size_id<0:continue
        page=cache.block(play+24,88)[page_id];group=cache.block(play+36,16)[size_id]
        compressed,raw=cache.unpack('2I',page+12);assert compressed==raw,'Compressed sound pages are unsupported'
        total=cache.u32(group);length+=total
        ranges=[cache.unpack('2I',p) for p in cache.block(group+4,8)]
        shared=cache.unpack('h',page+4)[0];path=cache.path
        if shared>=0:path=path.with_name(cache.string(cache.block(play+12,264)[shared]).replace('\\','/').split('/')[-1])
        groups.append((path,page,offset,total,ranges))
    result=bytearray(length);sources=set()
    for path,page,offset,total,ranges in groups:
        if not total:continue
        sources.add(path)
        with path.open('rb') as f:
            f.seek(1136);base=struct.unpack('>I',f.read(4))[0];f.seek(base+cache.u32(page+8)+offset)
            for target,size in ranges:
                assert target+size<=len(result)
                data=f.read(size);assert len(data)==size;result[target:target+size]=data
    return result,sources


def extract(cache,suffix,output,ffmpeg):
    tag=next(t for t in cache.by_class['snd!'] if t['path'].endswith(suffix));s=tag['offset'];g=cache.by_class['ugh!'][0]['offset']
    pitch_count=cache.data[s+3];pitch_index=cache.unpack('h',s+6)[0];codec_index=cache.data[s+5]
    codec=cache.unpack('3B',cache.block(g,3)[codec_index]);rate=(22050,44100,32000)[codec[0]]
    assert codec[1] in (0,1),'Only mono/stereo announcements are supported';channels=codec[1]+1
    assert pitch_count==1
    pitch=cache.block(g+72,12)[pitch_index];encoded,first=cache.unpack('hH',pitch+8);assert ((encoded>>4)&63)==1
    permutation=cache.block(g+84,20)[first];name=cache.sid(cache.u32(cache.block(g+36,4)[cache.unpack('h',permutation)[0]]))
    block_index,count=cache.unpack('ih',permutation+8);blocks=[cache.unpack('iI',p) for p in cache.block(g+172,20)[block_index:block_index+count]]
    ident=cache.u32(s+28);resource,sources=sound_resource(cache,ident);payload=bytearray()
    for offset,size_flags in blocks:
        size=size_flags&0xffffff;assert offset>=0 and offset+size<=len(resource)
        payload.extend(resource[offset:offset+size])
    fmt=struct.pack('<5H2B',0x165,16,0,0,1,0,3)+struct.pack('<4IBBH',0,rate,0,0,0,channels,2)
    riff=b'RIFF'+struct.pack('<I',len(payload)+len(fmt)+20)+b'WAVEfmt '+struct.pack('<I',len(fmt))+fmt+b'data'+struct.pack('<I',len(payload))+payload
    xma=output/(name+'.xma');wav=output/(name+'.wav');xma.write_bytes(riff)
    subprocess.run([str(ffmpeg),'-v','error','-y','-i',str(xma),'-ac','1','-ar','44100','-c:a','pcm_s16le',str(wav)],check=True)
    return dict(tag=tag['path'],tag_id=tag['id'],resource_id=ident,permutation=name,codec=list(codec),source_rate=rate,source_channels=channels,permutation_blocks=[dict(offset=o,bytes=n&0xffffff) for o,n in blocks],xma_payload_bytes=len(payload),decoded_wav=wav.name),sources


def run(cache_path,asset_root,ffmpeg):
    root=Path(asset_root);output=root/'assets/swat-announcer';output.mkdir(parents=True,exist_ok=True);cache=ReachCache(cache_path)
    details=[];sources={cache.path}
    for suffix in (r'multiplayer_game_types\swat',r'slayer\slayer'):
        detail,paths=extract(cache,suffix,output,ffmpeg);details.append(detail);sources.update(paths)
    pcm=[]
    for name in ('swat','slayer'):
        with wave.open(str(output/(name+'.wav')),'rb') as f:
            assert (f.getnchannels(),f.getsampwidth(),f.getframerate())==(1,2,44100)
            pcm.append(f.readframes(f.getnframes()))
    gap=.12;combined=output/'swat-slayer.wav'
    with wave.open(str(combined),'wb') as f:
        f.setnchannels(1);f.setsampwidth(2);f.setframerate(44100);f.writeframes(pcm[0]+b'\0\0'*round(gap*44100)+pcm[1])
    target=root/'frontend-files/mode_swat.s8';target.parent.mkdir(parents=True,exist_ok=True)
    subprocess.run([str(ffmpeg),'-v','error','-y','-i',str(combined),'-ar','11025','-ac','1','-f','s8',str(target)],check=True)
    outputs=[*sorted(output.glob('*.xma')),*sorted(output.glob('*.wav')),target]
    report=dict(game='Halo: Reach retail',build=cache.build,line='SWAT. Slayer.',method='Original named English permutation blocks from the owned cache; preserve each recording and concatenate with 120 ms silence. No synthesis.',source_caches={str(p):sha(p) for p in sorted(sources)},recordings=details,gap_seconds=gap,format=dict(rate=11025,channels=1,encoding='signed 8-bit PCM'),samples=target.stat().st_size,duration=target.stat().st_size/11025,extractor_sha256=sha(Path(__file__)),files={str(p.relative_to(root)):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in outputs})
    (output/'provenance.json').write_text(json.dumps(report,indent=2)+'\n');cache.close();print(json.dumps(report,indent=2))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--cache',type=Path,required=True);p.add_argument('--asset-root',type=Path,default=Path('halo64-assets'));p.add_argument('--ffmpeg',type=Path,required=True);a=p.parse_args();run(a.cache,a.asset_root,a.ffmpeg)
