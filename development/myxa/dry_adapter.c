/* Integration probe, not installed into Freetribe. No effects or output gain.
 * Static storage; sample-by-sample bridge for the existing module callback.
 * Desktop source is included to prevent an independently diverging engine copy.
 */
#define MODEL_D_EMBEDDED
#include "../../desktop/live/native/modeld.c"
#include "parameters.h"
static ModelDState voice;
static ModelDPrepared prepared;
static double settings[PARAM_COUNT];
static int architecture;
int myxa_dry_init(int factory_index) {
    int i;
    if(factory_index<0 || factory_index>=3)return -1;
    architecture=myxa_factory_patches[factory_index].engine;
    for(i=0;i<PARAM_COUNT;i++)settings[i]=myxa_factory_patches[factory_index].values[i];
    synth_init_inplace(&voice,48000);
    synth_prepare(&prepared,settings,48000);
    return 0;
}
void myxa_dry_process(const float *pitch,const float *gate,const float *trigger,float *out,int count) {
    int i;float cutoff=1,res=(float)settings[RESONANCE];
    for(i=0;i<count;i++)synth_process_prepared(&voice,out+i,pitch+i,gate+i,trigger+i,&cutoff,&res,1,&prepared,architecture);
}

/* Probe API; caller validates parameter ranges using the shared schema. */
int myxa_dry_set_parameter(int index,double value) {
    if(index<0 || index>=PARAM_COUNT || !isfinite(value))return -1;
    settings[index]=value;
    synth_prepare(&prepared,settings,48000);
    return 0;
}
