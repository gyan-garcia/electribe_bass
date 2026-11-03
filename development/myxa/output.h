#ifndef MYXA_OUTPUT_H
#define MYXA_OUTPUT_H
#include <stdint.h>
#include <math.h>
typedef struct {
    float pan,master,target_left,target_right,left,right,coefficient;
    uint32_t clipped,invalid;
} MyxaOutput;
static inline int myxa_output_pan(MyxaOutput *o,float pan){
    if(!isfinite(pan)||pan< -1||pan>1)return -1;
    o->pan=pan;
    o->target_left=pan==1?0:cosf((pan+1)*.7853981633974483f);
    o->target_right=pan== -1?0:sinf((pan+1)*.7853981633974483f);
    return 0;
}
static inline int myxa_output_master(MyxaOutput *o,float gain){
    if(!isfinite(gain)||gain<0||gain>1)return -1;
    o->master=gain;return 0;
}
static inline void myxa_output_init(MyxaOutput *o,int rate){
    *o=(MyxaOutput){0};o->coefficient=1-expf(-1.0f/(.005f*rate));
    myxa_output_pan(o,0);myxa_output_master(o,.125892541f); /* -18 dB startup */
}
static inline int32_t myxa_q31(MyxaOutput *o,float v){
    if(!isfinite(v)){o->invalid++;return 0;}
    if(v>.98f){v=.98f;o->clipped++;}
    if(v< -.98f){v= -.98f;o->clipped++;}
    return (int32_t)((double)v*2147483648.0);
}
static inline void myxa_output_sample(MyxaOutput *o,float mono,int32_t lr[2]){
    if(!isfinite(mono)){o->invalid++;o->left=o->right=0;lr[0]=lr[1]=0;return;}
    o->left+=o->coefficient*(o->master*o->target_left-o->left);
    o->right+=o->coefficient*(o->master*o->target_right-o->right);
    lr[0]=myxa_q31(o,mono*o->left);lr[1]=myxa_q31(o,mono*o->right);
}
#endif
