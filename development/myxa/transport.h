#ifndef MYXA_TRANSPORT_H
#define MYXA_TRANSPORT_H
#include <stdint.h>
#define MYXA_CMD_EXPRESSION 0x7001
#define MYXA_CMD_COMMIT 0x7002
#define MYXA_CMD_ACK 0x7003
/* CRC32 over explicit little-endian snapshot words. */
static uint32_t myxa_checksum(uint32_t note,uint32_t expression){
    uint32_t crc=~0u;int i,j;uint32_t words[2];words[0]=note;words[1]=expression;
    for(i=0;i<8;i++){crc^=(words[i/4]>>((i%4)*8))&255;
        for(j=0;j<8;j++)crc=(crc>>1)^((0u-(crc&1))&0xedb88320u);}
    return ~crc;
}
#endif
