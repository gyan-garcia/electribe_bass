#include "patch_file.h"
#include <math.h>
#include <string.h>
static uint16_t rd16(const uint8_t *p){return p[0]|((uint16_t)p[1]<<8);}
static uint32_t rd32(const uint8_t *p){return rd16(p)|((uint32_t)rd16(p+2)<<16);}
static void wr16(uint8_t *p,uint16_t v){p[0]=v;p[1]=v>>8;}
static void wr32(uint8_t *p,uint32_t v){wr16(p,(uint16_t)v);wr16(p+2,(uint16_t)(v>>16));}
static uint32_t crc32(const uint8_t *p,size_t n){
    uint32_t c=~0u;size_t i;int j;
    for(i=0;i<n;i++){c^=p[i];for(j=0;j<8;j++)c=(c>>1)^((0u-(c&1))&0xedb88320u);}
    return ~c;
}
static int valid_value(int i,float v){return isfinite(v)&&v>=myxa_minimum[i]&&v<=myxa_maximum[i]&&(!myxa_discrete[i]||v==(int)v);}
static int name_length(const char *name){int i;for(i=0;i<33;i++){if(!name[i])return i; if((unsigned char)name[i]<32||(unsigned char)name[i]>126)return -1;}return -1;}
int myxa_file_encode(const MyxaPatchRecord *r,uint8_t *b,size_t cap){
    int i,n;if(!r||!b||cap<MYXA_FILE_SIZE)return MYXA_FILE_INVALID;
    n=name_length(r->name);
    if(n<1||n>32||!r->id||!r->generation||(r->engine!=3&&r->engine!=4))return MYXA_FILE_INVALID;
    for(i=0;i<MYXA_PARAMETER_COUNT;i++)if(!valid_value(i,r->values[i]))return MYXA_FILE_INVALID;
    memset(b,0,MYXA_FILE_SIZE);memcpy(b,"MYXA",4);
    wr16(b+4,1);wr16(b+6,MYXA_SCHEMA_VERSION);wr16(b+8,MYXA_FILE_SIZE);wr16(b+10,r->engine);
    wr32(b+12,r->id);wr32(b+16,r->generation);b[20]=(uint8_t)n;memcpy(b+24,r->name,n);wr16(b+56,MYXA_PARAMETER_COUNT);
    for(i=0;i<MYXA_PARAMETER_COUNT;i++){uint32_t bits;memcpy(&bits,&r->values[i],4);wr16(b+64+i*6,i+1);wr32(b+66+i*6,bits);}
    wr32(b+MYXA_FILE_SIZE-4,crc32(b,MYXA_FILE_SIZE-4));return MYXA_FILE_OK;
}
int myxa_file_decode(const uint8_t *b,size_t length,MyxaPatchRecord *r){
    int i,n;uint8_t seen[MYXA_PARAMETER_COUNT]={0};
    if(!b||!r||length<12||memcmp(b,"MYXA",4))return MYXA_FILE_INVALID;
    if(rd16(b+4)!=1||rd16(b+6)!=MYXA_SCHEMA_VERSION)return MYXA_FILE_UNSUPPORTED;
    if(length!=MYXA_FILE_SIZE||rd16(b+8)!=length||rd16(b+56)!=MYXA_PARAMETER_COUNT)return MYXA_FILE_INVALID;
    if(rd32(b+length-4)!=crc32(b,length-4))return MYXA_FILE_INVALID;
    n=b[20];if(n<1||n>32||!rd32(b+12)||!rd32(b+16)||(rd16(b+10)!=3&&rd16(b+10)!=4))return MYXA_FILE_INVALID;
    for(i=21;i<24;i++)if(b[i])return MYXA_FILE_INVALID;
    for(i=58;i<64;i++)if(b[i])return MYXA_FILE_INVALID;
    for(i=0;i<32;i++)if(i<n ? (b[24+i]<32||b[24+i]>126) : b[24+i]!=0)return MYXA_FILE_INVALID;
    for(i=0;i<MYXA_PARAMETER_COUNT;i++){
        int id=rd16(b+64+i*6)-1;float value;uint32_t bits=rd32(b+66+i*6);
        memcpy(&value,&bits,4);
        if(id<0||id>=MYXA_PARAMETER_COUNT||seen[id]||!valid_value(id,value))return MYXA_FILE_INVALID;
        seen[id]=1;
    }
    /* Do not change the destination until the complete record validates. */
    r->id=rd32(b+12);r->generation=rd32(b+16);r->engine=rd16(b+10);
    memset(r->name,0,sizeof(r->name));memcpy(r->name,b+24,n);
    for(i=0;i<MYXA_PARAMETER_COUNT;i++){uint32_t bits=rd32(b+66+i*6);memcpy(&r->values[rd16(b+64+i*6)-1],&bits,4);}
    return MYXA_FILE_OK;
}
/* state 0 unloaded/error, 1 ready, 2 begin, 3 write, 4 finish, 5 verify */
int myxa_store_load(MyxaStore *s,const MyxaStoreIO *io,uint32_t id){
    int slot,have=0,invalid=0;MyxaPatchRecord candidate;
    if(!s||!io||!io->read||!id)return MYXA_FILE_INVALID;
    memset(s,0,sizeof(*s));s->active_slot=-1;s->active.id=id;
    for(slot=0;slot<2;slot++){
        int n=io->read(io->user,slot,s->bytes,sizeof(s->bytes));int result;
        if(n<0)return MYXA_STORE_IO;
        if(n==0)continue;
        result=myxa_file_decode(s->bytes,(size_t)n,&candidate);
        if(result==MYXA_FILE_UNSUPPORTED)return result;
        if(result!=MYXA_FILE_OK){invalid=1;continue;}
        if(candidate.id!=id)return MYXA_STORE_CONFLICT;
        if(have && candidate.generation==s->active.generation){
            /* Normalize by semantic data: input entries may be reordered. */
            if(candidate.engine!=s->active.engine||strcmp(candidate.name,s->active.name)||memcmp(candidate.values,s->active.values,sizeof(candidate.values)))return MYXA_STORE_CONFLICT;
        }
        if(!have||candidate.generation>s->active.generation){s->active=candidate;s->active_slot=slot;have=1;}
    }
    if(!have&&invalid)return MYXA_FILE_INVALID;
    s->state=1;return have?MYXA_FILE_OK:MYXA_STORE_EMPTY;
}
int myxa_store_start(MyxaStore *s,const MyxaPatchRecord *edited){
    if(!s||!edited||s->state!=1||edited->id!=s->active.id||s->active.generation==UINT32_MAX)return MYXA_FILE_INVALID;
    s->pending=*edited;s->pending.generation=s->active.generation+1;
    if(myxa_file_encode(&s->pending,s->bytes,sizeof(s->bytes)))return MYXA_FILE_INVALID;
    s->target=s->active_slot==0?1:0;s->offset=0;s->state=2;return MYXA_STORE_BUSY;
}
int myxa_store_step(MyxaStore *s,const MyxaStoreIO *io){
    int result;size_t count;
    if(!s||!io||!io->read||!io->begin||!io->write||!io->finish)return MYXA_FILE_INVALID;
    switch(s->state){
    case 2:if(io->begin(io->user,s->target))break;s->state=3;return MYXA_STORE_BUSY;
    case 3:
        count=MYXA_FILE_SIZE-s->offset;if(count>64)count=64;
        result=io->write(io->user,s->target,s->offset,s->bytes+s->offset,count);
        if(result!=(int)count)break;
        s->offset+=count;if(s->offset==MYXA_FILE_SIZE)s->state=4;return MYXA_STORE_BUSY;
    case 4:if(io->finish(io->user,s->target))break;s->state=5;return MYXA_STORE_BUSY;
    case 5:{
        MyxaPatchRecord verified;
        result=io->read(io->user,s->target,s->bytes,sizeof(s->bytes));
        if(result!=MYXA_FILE_SIZE||myxa_file_decode(s->bytes,result,&verified)||verified.id!=s->pending.id||verified.generation!=s->pending.generation||verified.engine!=s->pending.engine||strcmp(verified.name,s->pending.name)||memcmp(verified.values,s->pending.values,sizeof(verified.values)))break;
        s->active=verified;s->active_slot=s->target;s->state=1;return MYXA_STORE_DONE;
    }
    default:return MYXA_FILE_INVALID;
    }
    s->state=0;return MYXA_STORE_IO; /* Reload both slots before any retry. */
}
