#include <math.h>
#include <stdlib.h>
/* Normalized biquad coefficients supplied by eq.py; 20 ms interpolation. */
typedef struct { double c[15],z[6],wet; int ready; } EQ;
void *eq_create(void){return calloc(1,sizeof(EQ));}
void eq_destroy(void *p){free(p);}
void eq_reset(EQ *p){*p=(EQ){0};}
void eq_process(EQ *p,float *audio,int n,const double *target,double enabled,int rate){
    double step=1-exp(-1.0/(.02*rate));
    if(!p->ready){for(int j=0;j<15;j++)p->c[j]=target[j];p->wet=enabled;p->ready=1;}
    for(int i=0;i<n;i++){
        p->wet+=step*(enabled-p->wet);
        if(fabs(p->wet-enabled)<1e-9)p->wet=enabled;
        double dry=audio[i],x=dry;
        for(int b=0;b<3;b++){
            double *c=p->c+b*5,*z=p->z+b*2;
            for(int j=0;j<5;j++)c[j]+=step*(target[b*5+j]-c[j]);
            double y=c[0]*x+z[0];
            z[0]=c[1]*x-c[3]*y+z[1];z[1]=c[2]*x-c[4]*y;x=y;
        }
        audio[i]=(float)(dry+p->wet*(x-dry));
    }
}
