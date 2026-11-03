#include <assert.h>
#include <limits.h>
#include <stdio.h>
#include <string.h>
#include "text.h"
int main(void){
    int values[]={0,1,-1,42,-42,100,-100,1800000,INT_MAX,INT_MIN};
    const char *labels[]={"Cutoff Hz","Resonance","Filter EG oct","Mixer drive"};
    unsigned i,j;size_t cap;
    for(i=0;i<sizeof(values)/sizeof(values[0]);i++)for(j=0;j<4;j++)for(cap=1;cap<=22;cap++){
        char actual[24],expected[24];unsigned mag=values[i]<0?(unsigned)(-(long long)values[i]):(unsigned)values[i];
        memset(actual,0x55,sizeof(actual));memset(expected,0x55,sizeof(expected));
        snprintf(expected,cap,"%s %s%u.%02u",labels[j],values[i]<0?"-":"",mag/100,mag%100);
        myxa_value_text(actual,cap,labels[j],values[i]);
        assert(memcmp(actual,expected,sizeof(actual))==0);
    }
    {char guarded[2]={'x','y'};myxa_value_text(guarded,0,"x",1);assert(guarded[0]=='x'&&guarded[1]=='y');}
    return 0;
}
