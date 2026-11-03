#include <assert.h>
#include <limits.h>
#include <stdlib.h>
#include "output.h"
int main(void){
    MyxaOutput o;int32_t lr[2];int i;
    myxa_output_init(&o,48000);assert(myxa_output_master(&o,1)==0);
    for(i=0;i<48000;i++)myxa_output_sample(&o,.5f,lr);
    assert(llabs((long long)lr[0]-lr[1])<256);
    assert(fabs((double)lr[0]/2147483648.-.35355339)<.0001);
    for(i=0;i<=20;i++){
        float pan=-1+i*.1f;assert(myxa_output_pan(&o,pan)==0);
        assert(fabs(o.target_left*o.target_left+o.target_right*o.target_right-1)<1e-6);
    }
    assert(myxa_output_pan(&o,-1)==0);
    for(i=0;i<24000;i++)myxa_output_sample(&o,.5f,lr);
    assert(lr[0]>1000000000&&lr[1]==0);
    assert(myxa_output_pan(&o,1)==0);
    for(i=0;i<24000;i++)myxa_output_sample(&o,.5f,lr);
    assert(lr[0]==0&&lr[1]>1000000000);
    assert(myxa_output_pan(&o,NAN)<0&&myxa_output_master(&o,INFINITY)<0);
    assert(myxa_output_pan(&o,2)<0&&myxa_output_master(&o,-1)<0);
    myxa_output_sample(&o,NAN,lr);assert(lr[0]==0&&lr[1]==0&&o.invalid==1);
    myxa_output_sample(&o,INFINITY,lr);assert(lr[0]==0&&lr[1]==0&&o.invalid==2);
    for(i=0;i<24000;i++)myxa_output_sample(&o,100,lr);
    assert(o.clipped>0&&lr[1]>0&&lr[1]<INT32_MAX);
    assert(myxa_output_master(&o,0)==0);
    for(i=0;i<24000;i++)myxa_output_sample(&o,.5f,lr);
    assert(lr[0]==0&&lr[1]==0);
    return 0;
}
