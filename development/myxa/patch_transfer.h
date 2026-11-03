#ifndef MYXA_PATCH_TRANSFER_H
#define MYXA_PATCH_TRANSFER_H
#include <math.h>
#include <string.h>
#include "parameters.h"
#include "transport.h"
#define MYXA_PATCH_BEGIN 0x7100
#define MYXA_PATCH_COMMIT 0x7101
#define MYXA_PATCH_ACK 0x7102
#define MYXA_PATCH_DATA 0x7200
static inline uint32_t myxa_bits(float f){uint32_t w;memcpy(&w,&f,4);return w;}
static inline float myxa_float(uint32_t w){float f;memcpy(&f,&w,4);return f;}
static inline int myxa_valid(int i,float v){return i>=0&&i<MYXA_PARAMETER_COUNT&&isfinite(v)&&v>=myxa_minimum[i]&&v<=myxa_maximum[i]&&(!myxa_discrete[i]||v==(int)v);}
static inline uint32_t myxa_patch_crc(uint32_t header,const float *values){
    int i;uint32_t crc=header;
    for(i=0;i<MYXA_PARAMETER_COUNT;i++)crc=myxa_checksum(crc,myxa_bits(values[i]));
    return crc;
}
typedef struct {
    float values[MYXA_PARAMETER_COUNT];
    uint8_t seen[MYXA_PARAMETER_COUNT],open;
    uint32_t header,ack,committed_header,committed_crc;
} MyxaPatchRx;
/* 1 means complete patch ready, 0 accepted but incomplete, -1 rejected. */
static inline int myxa_patch_receive(MyxaPatchRx *r,uint16_t id,uint32_t word){
    int i;
    if(id==MYXA_PATCH_BEGIN){
        if((word>>24)!=0xb1 || (((word>>16)&255)!=3 && ((word>>16)&255)!=4))return -1;
        r->header=word;r->open=1;memset(r->seen,0,sizeof(r->seen));
    }else if(id>=MYXA_PATCH_DATA && id<MYXA_PATCH_DATA+MYXA_PARAMETER_COUNT){
        i=id-MYXA_PATCH_DATA;
        if(!r->open||!myxa_valid(i,myxa_float(word)))return -1;
        r->values[i]=myxa_float(word);r->seen[i]=1;
    }else if(id==MYXA_PATCH_COMMIT){
        if(!r->open){
            if(r->committed_header && word==r->committed_crc){r->ack=myxa_checksum(id,word);return 0;}
            return -1;
        }
        for(i=0;i<MYXA_PARAMETER_COUNT;i++)if(!r->seen[i])return -1;
        if(word!=myxa_patch_crc(r->header,r->values))return -1;
        r->open=0;r->committed_header=r->header;r->committed_crc=word;
        r->ack=myxa_checksum(id,word);return 1;
    }else return -1;
    r->ack=myxa_checksum(id,word);return 0;
}
#endif
