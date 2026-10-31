"""Read-only retail Reach cache reader. Layouts: Reclaimer HaloReach definitions."""
import mmap
import subprocess
from pathlib import Path
from halo3_cache import OdstCache

class ReachCache(OdstCache):
    STRING_NAMESPACES = ((0x4ae,0x16aa),(0,0x4ae),(0,0xb13),(0,0xbeb),(0,0xc55),
        (0,0xd2e),(0,0xd54),(0,0xd59),(0,0x1416),(0,0x1585),(0,0x1599),(0,0),
        (0,0x15fb),(0,0x1613),(0,0x1620),(0,0x1649))
    def decrypt(self, offset, size, phrase):
        key=bytes(b^0xa5 for b in phrase.encode())
        iv=bytes(b^0x3c for b in key)
        return subprocess.run(['openssl','enc','-d','-aes-128-cbc','-nopad','-K',key.hex(),'-iv',iv.hex()],
            input=self.data[offset:offset+((size+15)//16)*16],capture_output=True,check=True).stdout
    def __init__(self,path):
        self.path=Path(path); self.handle=self.path.open('rb')
        self.data=mmap.mmap(self.handle.fileno(),0,access=mmap.ACCESS_READ)
        self.build=self.string(284)
        if 'omaha' not in self.build: raise ValueError('Expected retail Reach cache')
        self.section_offsets=self.unpack('4I',1132)
        meta=(self.u32(1164)+self.section_offsets[2])&0xffffffff
        self.magic=self.u32(744)-meta
        self.index=self.pointer(self.u32(16))
        nc,cp,nt,tp=self.unpack('4I',self.index)
        classes=self.pointer(cp); tags=self.pointer(tp)
        names=self.decrypt(self.header_pointer(self.u32(696)),self.u32(700),'LetsAllPlayNice!')
        ni=self.header_pointer(self.u32(704))
        self.tags=[]; self.by_class={}
        for i in range(nt):
            cls,_,ptr=self.unpack('hhI',tags+i*8); off=self.i32(ni+i*4)
            t={'id':i,'class':self.data[classes+cls*16:classes+cls*16+4].decode('ascii') if cls>=0 else '',
                'path':names[off:names.find(b'\0',off)].decode() if off>=0 else '',
                'offset':self.pointer(ptr) if cls>=0 else 0}
            self.tags.append(t); self.by_class.setdefault(t['class'],[]).append(t)
        si=self.header_pointer(self.u32(352))
        sd=self.decrypt(self.header_pointer(self.u32(356)),self.u32(348),'ILikeSafeStrings')
        self.strings=[sd[o:sd.find(b'\0',o)].decode() if o>=0 else '' for o in self.unpack(f'{self.u32(344)}i',si)]
        self.page_cache={}
    def sid(self,value):
        i=value&0x1ffff; ns=(value>>17)&0xff
        minimum,start=self.STRING_NAMESPACES[ns]
        return self.strings[i if i<minimum else i-minimum+start]
