#include <math.h>
#include <stdlib.h>
#include <string.h>
/* Four damped combs and two allpass diffusers. Allocations only at creation. */
typedef struct {
    float *buf[6], damp[4], hp;
    int len[6], pos[6], rate, ready;
    float mix, feedback[4];
} Room;
void room_destroy(Room *r){if(r){for(int i=0;i<6;i++)free(r->buf[i]);free(r);}}
void *room_create(int rate){
    if(rate<8000 || rate>192000)return NULL;
    Room *r=calloc(1,sizeof(Room));if(!r)return NULL;r->rate=rate;
    const float seconds[6]={.0297f,.0371f,.0411f,.0437f,.005f,.0017f};
    for(int i=0;i<6;i++){
        r->len[i]=(int)(seconds[i]*rate)|1;
        r->buf[i]=calloc(r->len[i],sizeof(float));
        if(!r->buf[i]){room_destroy(r);return NULL;}
    }
    return r;
}
void room_reset(Room *r){
    for(int i=0;i<6;i++){memset(r->buf[i],0,r->len[i]*sizeof(float));r->pos[i]=0;}
    memset(r->damp,0,sizeof(r->damp));r->hp=0;r->ready=0;
}
void room_process(Room *r,float *audio,int n,double mix,double decay){
    float target[4];
    for(int j=0;j<4;j++)target[j]=pow(10.,-3.*r->len[j]/(r->rate*decay));
    const float smooth=1-exp(-1./(.02*r->rate));
    const float hp=1-exp(-2*3.141592653589793*180/r->rate);
    const float damp=1-exp(-2*3.141592653589793*2800/r->rate);
    if(!r->ready){r->mix=mix;memcpy(r->feedback,target,sizeof(target));r->ready=1;}
    for(int i=0;i<n;i++){
        float dry=audio[i];r->hp+=hp*(dry-r->hp);float input=dry-r->hp;
        float wet=0;
        for(int j=0;j<4;j++){
            float delayed=r->buf[j][r->pos[j]];
            r->damp[j]+=damp*(delayed-r->damp[j]);
            if(fabsf(r->damp[j])<1e-20f)r->damp[j]=0;
            r->feedback[j]+=smooth*(target[j]-r->feedback[j]);
            r->buf[j][r->pos[j]]=input+r->feedback[j]*r->damp[j];
            wet+=delayed*.25f;
            if(++r->pos[j]==r->len[j])r->pos[j]=0;
        }
        for(int j=4;j<6;j++){
            float delayed=r->buf[j][r->pos[j]];
            float y=delayed-.5f*wet;
            r->buf[j][r->pos[j]]=wet+.5f*y;wet=y;
            if(++r->pos[j]==r->len[j])r->pos[j]=0;
        }
        r->mix+=smooth*((float)mix-r->mix);
        if(fabsf(r->mix-(float)mix)<1e-7f)r->mix=mix;
        audio[i]=r->mix==0 ? dry : dry*(1-r->mix)+wet*r->mix;
    }
}
