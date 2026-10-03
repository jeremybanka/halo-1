from pathlib import Path
import hashlib,json,re,subprocess
ROOT=Path(__file__).resolve().parents[2];P=ROOT/'build/n64/tests/model-index-aliases';P.mkdir(parents=True,exist_ok=True);s=(ROOT/'port/n64/main.c').read_text();a=s.index('static void prepare_model(');brace=s.index('{',a);depth=1;end=brace+1
while depth:
 depth+=(s[end]=='{')-(s[end]=='}');end+=1
function=s[a:end];assert 'converted[96]' in function and 'converted_count<96' in function
header=r'''
#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <setjmp.h>
#include <string.h>
typedef struct { char bytes[32]; } T3DVertPacked;
typedef struct { uint16_t first,count,index_first,index_count; } bg_mesh_batch;
typedef struct { T3DVertPacked *vertices; uint16_t vertex_count; float radius; const bg_mesh_batch *batches;int16_t *indices;uint16_t batch_count,triangle_count; } bg_model_asset;
static jmp_buf failure;static unsigned converts,failed;
#define assertf(c,...) do {if(!(c)){failed++;longjmp(failure,1);}}while(0)
static void data_cache_hit_writeback(const void*p,unsigned n){(void)p;(void)n;}
static void t3d_indexbuffer_convert(int16_t*p,unsigned n){converts++;for(unsigned i=0;i<n;i++)p[i]|=0x4000;}
'''
test=r'''
int main(void){
 static int16_t indices[97][4];static T3DVertPacked verts[97][2];
 static const bg_mesh_batch batch={0,4,0,3};static bg_model_asset assets[97];
 for(unsigned i=0;i<97;i++){
  indices[i][0]=0;indices[i][1]=1;indices[i][2]=2;
  assets[i]=(bg_model_asset){verts[i],4,1,&batch,indices[i],1,1};
 }
 if(setjmp(failure))return 2;
 for(unsigned i=0;i<96;i++){
  prepare_model(&assets[i]);
  for(unsigned j=0;j<=i;j++)prepare_model(&assets[j]);
 }
 assert(converts==96&&failed==0);
 for(unsigned i=0;i<96;i++)assert(indices[i][0]==0x4000&&indices[i][1]==0x4001&&indices[i][2]==0x4002);
 if(!setjmp(failure)){prepare_model(&assets[96]);return 3;}
 assert(converts==96&&failed==1&&indices[96][0]==0);
 puts("PASS: actual prepare_model96 unique arrays,4656 alias reuses,97th capacity guard before mutation");
}
'''
c=P/'test_aliases.c';c.write_text(header+function+test);out=P/'test_aliases'
cmd=['clang','-std=c11','-O2','-Wall','-Wextra','-Werror','-fsanitize=address,undefined',str(c),'-o',str(out)];subprocess.run(cmd,check=True);subprocess.run([str(out)],check=True)
counts={n:len(re.findall(r'^static int16_t [A-Za-z0-9_]+_indices', (ROOT/'build/n64/generated'/n).read_text(),re.M)) for n in ('models_data.c','firstperson_data.c')}
proof={'actual_function_sha256':hashlib.sha256(function.encode()).hexdigest(),'source_sha256':hashlib.sha256(s.encode()).hexdigest(),'actual_existing_unique_index_arrays_upper_bound':counts,'max_additional_micro_arrays':17,'full_candidate_total_upper_bound':sum(counts.values())+17,'capacity':96,'aliases_tested':4656,'guard_before_overflow':True,'sanitizers':'ASan+UBSan','command':cmd}
assert proof['full_candidate_total_upper_bound']<=96
(P/'aliases-proof.json').write_text(json.dumps(proof,indent=2)+'\n')
