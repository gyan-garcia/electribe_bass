/* Read-only diagnostic access to MYXA's current native DSP. */
#include "../../../desktop/live/native/modeld.c"

void research_oscillator(float *out,int frames,float frequency,int shape) {
    uint32_t phase=0;
    for (int n=0;n<frames;n++) {
        float sum=0;
        for(int k=0;k<2;k++)sum+=waveform(&phase,frequency,96000,shape,0);
        out[n]=sum*.5f;
    }
}
void research_filter(const float *input,float *output,int frames,float cutoff,float resonance) {
    ModelDState state={0};
    float tangent=tanf(3.141592654f*cutoff/96000.f);
    float coefficient=tangent/(1+tangent);
    for(int n=0;n<frames;n++) {
        float sum=0;
        for(int k=0;k<2;k++)sum+=ladder(&state,input[n],coefficient,resonance,0,3);
        output[n]=sum*.5f;
    }
}
