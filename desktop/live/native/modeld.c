#include <math.h>
#include <stdint.h>
#include <stdlib.h>

enum {
    OSC1_WAVE, OSC1_OCTAVE, OSC1_TUNE, OSC1_LOW,
    OSC2_WAVE, OSC2_OCTAVE, OSC2_TUNE, OSC2_LOW,
    OSC3_WAVE, OSC3_OCTAVE, OSC3_TUNE, OSC3_LOW,
    OSC3_KEYBOARD, OSC3_FIXED,
    OSC1_LEVEL, OSC2_LEVEL, OSC3_LEVEL, NOISE_LEVEL, NOISE_COLOR,
    MIXER_DRIVE, FEEDBACK, OUTPUT_DRIVE,
    CUTOFF, RESONANCE, CONTOUR, FILTER_MODE, KEYTRACK1, KEYTRACK2,
    FILTER_ATTACK, FILTER_DECAY, FILTER_SUSTAIN,
    AMP_ATTACK, AMP_DECAY, AMP_SUSTAIN, RELEASE_ENABLED,
    GLIDE, TUNE, LFO_RATE, LFO_WAVE, SOURCE1, SOURCE2, MOD_MIX, MOD_AMOUNT,
    PITCH_MOD_ON, PITCH_MOD_DEPTH, FILTER_MOD_ON, FILTER_MOD_DEPTH, PARAM_COUNT
};

typedef struct {
    int rate, ready, coefficient_counter;
    uint32_t phase[3], lfo_phase, random;
    float amp, contour, base_frequency, osc3_previous;
    int amp_stage, filter_stage;
    float poles[4], pink[3], smooth[10], coefficient;
    float dc_input, dc_output, previous_output;
    float tracking_pitch, tracking_depth, tracking_factor;
    double gain;
} ModelDState;

int synth_parameter_count(void) { return PARAM_COUNT; }
int synth_state_size(void) { return (int)sizeof(ModelDState); }

void synth_reset(ModelDState *state) {
    int rate=state->rate;
    *state=(ModelDState){.rate=rate,.phase={0,901943132u,1846835937u},
                        .random=0x51f2d3a9u,.base_frequency=49.0f};
    state->poles[0]=1e-8f;
}

void synth_init_inplace(ModelDState *state,int rate) {
    state->rate=rate;
    synth_reset(state);
}

#ifndef MODEL_D_EMBEDDED
ModelDState *synth_create(int rate) {
    if (rate<16000 || rate>192000) return NULL;
    ModelDState *state=calloc(1,sizeof(ModelDState));
    if (state) synth_init_inplace(state,rate);
    return state;
}
void synth_destroy(ModelDState *state) { free(state); }
#endif

void synth_gain(ModelDState *state,float *audio,int frames,double target) {
    double coefficient=1.0-exp(-1.0/(.005*state->rate));
    for (int frame=0;frame<frames;frame++) {
        state->gain+=coefficient*(target-state->gain);
        audio[frame]*=state->gain;
    }
}

static float limit(float value,float low,float high) {
    return value<low ? low : value>high ? high : value;
}

static float saturate(float value) {
    value=limit(value,-3.0f,3.0f);
    float squared=value*value;
    return value*(27.0f+squared)/(27.0f+9.0f*squared);
}

static float slope(float value) {
    if (fabsf(value)>=3.0f) return 0;
    float squared=value*value;
    float numerator=squared-9.0f;
    float denominator=27.0f+9.0f*squared;
    return 9.0f*numerator*numerator/(denominator*denominator);
}

static float noise(ModelDState *state) {
    uint32_t value=state->random;
    value^=value<<13; value^=value>>17; value^=value<<5;
    state->random=value;
    return (float)(value>>8)*(2.0f/16777216.0f)-1.0f;
}

static float blep(float phase,float step) {
    if (phase<step) {
        float position=phase/step;
        return position+position-position*position-1.0f;
    }
    if (phase>1.0f-step) {
        float position=(phase-1.0f)/step;
        return position*position+position+position+1.0f;
    }
    return 0;
}

static float waveform(uint32_t *accumulator,float frequency,float rate,int shape,int oscillator) {
    float step=limit(frequency/rate,1e-8f,.22f);
    float phase=(float)(*accumulator)*(1.0f/4294967296.0f);
    float saw=2.0f*phase-1.0f-blep(phase,step);
    float triangle=1.0f-4.0f*fabsf(phase-.5f);
    *accumulator+=(uint32_t)(step*4294967296.0f);
    if (shape==0) return triangle;
    if (shape==1) return oscillator==2 ? -saw : .5f*(triangle+saw);
    if (shape==2) return saw;
    float width=shape==3 ? .5f : shape==4 ? .25f : .1f;
    float offset=phase-width;
    if (offset<0) offset+=1;
    return (phase<width ? 1.0f : -1.0f)+blep(phase,step)-blep(offset,step);
}

static float envelope(float value,int *stage,int gate,int trigger,float attack,
                      float decay,float sustain,float release) {
    if (trigger && gate) *stage=1;
    if (!gate && *stage) *stage=3;
    if (*stage==1) {
        value+=attack*(1.0f-value);
        if (value>=.999f) { value=1; *stage=2; }
    } else if (*stage==2) {
        value=sustain+(value-sustain)*decay;
    } else if (*stage==3) {
        value*=release;
        if (value<1e-7f) { value=0; *stage=0; }
    }
    return value;
}

static float ladder(ModelDState *state,float input,float coefficient,float resonance,int highpass,int output_stage) {
    float gain=coefficient;
    float squared=gain*gain;
    float fourth=squared*squared;
    float memory=(1.0f-gain)*(gain*squared*state->poles[0]+squared*state->poles[1]
                            +gain*state->poles[2]+state->poles[3]);
    float feedback=4.0f*resonance;
    float source=input-feedback*memory;
    float value=source/(1.0f+feedback*fourth);
    for (int iteration=0;iteration<3;iteration++) {
        float argument=source-feedback*fourth*value;
        value-=(value-saturate(argument))/(1.0f+feedback*fourth*slope(argument));
    }
    float original=value;
    float taps[4];
    for (int stage=0;stage<4;stage++) {
        float difference=(value-state->poles[stage])*gain;
        value=difference+state->poles[stage];
        state->poles[stage]=value+difference;
        taps[stage]=value;
    }
    return highpass ? original-4.0f*taps[0]+6.0f*taps[1]-4.0f*taps[2]+taps[3] : taps[output_stage];
}

typedef struct {
    float settings[PARAM_COUNT];
    float attack_amp,attack_filter,decay_amp,decay_filter,release_amp,release_filter;
    float glide,smoothing,dc,tracking,ratio[3],pink_coefficients[3];
} ModelDPrepared;

/* Call on initialization, sample-rate changes or parameter updates. */
void synth_prepare(ModelDPrepared *prepared,const double *parameters,int sample_rate) {
    float rate=(float)sample_rate*2;
    float *settings=prepared->settings;
    for(int index=0;index<PARAM_COUNT;index++)settings[index]=(float)parameters[index];
    prepared->attack_amp=settings[AMP_ATTACK]<=0 ? 1 : 1-expf(-6.907755f/(settings[AMP_ATTACK]*rate));
    prepared->attack_filter=settings[FILTER_ATTACK]<=0 ? 1 : 1-expf(-6.907755f/(settings[FILTER_ATTACK]*rate));
    prepared->decay_amp=expf(-4.60517f/(settings[AMP_DECAY]*rate));
    prepared->decay_filter=expf(-4.60517f/(settings[FILTER_DECAY]*rate));
    prepared->release_amp=expf(-6.907755f/((settings[RELEASE_ENABLED]>.5f ? settings[AMP_DECAY] : .005f)*rate));
    prepared->release_filter=expf(-6.907755f/((settings[RELEASE_ENABLED]>.5f ? settings[FILTER_DECAY] : .005f)*rate));
    prepared->glide=1-expf(-1.0f/(fmaxf(.0001f,settings[GLIDE])*rate));
    prepared->smoothing=1-expf(-1.0f/(.008f*rate));
    prepared->dc=expf(-6.283185307f*4.0f/rate);
    float master=exp2f(settings[TUNE]/1200.0f);
    for (int oscillator=0;oscillator<3;oscillator++)
        prepared->ratio[oscillator]=exp2f(settings[oscillator*4+1]+settings[oscillator*4+2]/12.0f)*master;
    const float pink_frequencies[3]={70,500,3000};
    for (int index=0;index<3;index++) prepared->pink_coefficients[index]=1-expf(-6.283185307f*pink_frequencies[index]/rate);
    prepared->tracking=(settings[KEYTRACK1]+2.0f*settings[KEYTRACK2])/3.0f;
}

void synth_process_prepared(ModelDState *state,float *output,const float *pitch,const float *gate,
                   const float *trigger,const float *cutoff_scale,const float *resonance,
                   int frames,const ModelDPrepared *prepared,int architecture) {
    const int oversample=2;
    float rate=(float)state->rate*oversample;
    const float *settings=prepared->settings;
    const float *ratio=prepared->ratio,*pink_coefficients=prepared->pink_coefficients;
    float attack_amp=prepared->attack_amp;
    float attack_filter=prepared->attack_filter;
    float decay_amp=prepared->decay_amp;
    float decay_filter=prepared->decay_filter;
    float release_amp=prepared->release_amp;
    float release_filter=prepared->release_filter;
    float glide=prepared->glide;
    float smoothing=prepared->smoothing;
    float dc=prepared->dc;
    float tracking=prepared->tracking;
    for (int frame=0;frame<frames;frame++) {
        if (state->tracking_pitch!=pitch[frame] || state->tracking_depth!=tracking) {
            state->tracking_pitch=pitch[frame]; state->tracking_depth=tracking;
            state->tracking_factor=powf(fmaxf(1e-6f,pitch[frame]/49.0f),tracking);
        }
        float targets[10]={settings[OSC1_LEVEL],settings[OSC2_LEVEL],settings[OSC3_LEVEL],settings[NOISE_LEVEL],
            settings[MIXER_DRIVE],settings[FEEDBACK],settings[CUTOFF],resonance[frame],settings[OUTPUT_DRIVE],settings[MOD_AMOUNT]};
        if (!state->ready) {
            for (int index=0;index<10;index++) state->smooth[index]=targets[index];
            state->ready=1;
        }
        float accumulated=0;
        for (int sample=0;sample<oversample;sample++) {
            for (int index=0;index<10;index++) state->smooth[index]+=smoothing*(targets[index]-state->smooth[index]);
            state->base_frequency+=glide*(pitch[frame]-state->base_frequency);
            int retrigger=sample==0 && trigger[frame]>0;
            int held=gate[frame]>0;
            state->amp=envelope(state->amp,&state->amp_stage,held,retrigger,attack_amp,decay_amp,settings[AMP_SUSTAIN],release_amp);
            state->contour=envelope(state->contour,&state->filter_stage,held,retrigger,attack_filter,decay_filter,settings[FILTER_SUSTAIN],release_filter);
            float white=noise(state);
            for (int index=0;index<3;index++) state->pink[index]+=pink_coefficients[index]*(white-state->pink[index]);
            float coloured=settings[NOISE_COLOR]>.5f ? .6f*state->pink[0]+.3f*state->pink[1]+.15f*state->pink[2] : white;
            float lfo_phase=(float)state->lfo_phase*(1.0f/4294967296.0f);
            float lfo=settings[LFO_WAVE]>.5f ? (lfo_phase<.5f ? 1.0f : -1.0f) : 1.0f-4.0f*fabsf(lfo_phase-.5f);
            state->lfo_phase+=(uint32_t)(settings[LFO_RATE]/rate*4294967296.0f);
            float source_one=settings[SOURCE1]>.5f ? state->contour : state->osc3_previous;
            float source_two=settings[SOURCE2]>.5f ? lfo : coloured;
            float modulation=((1-settings[MOD_MIX])*source_one+settings[MOD_MIX]*source_two)*state->smooth[9];
            float pitch_factor=settings[PITCH_MOD_ON]>.5f ? exp2f(modulation*settings[PITCH_MOD_DEPTH]/12.0f) : 1;
            float mixed=coloured*state->smooth[3];
            for (int oscillator=0;oscillator<3;oscillator++) {
                float base=oscillator==2 && settings[OSC3_KEYBOARD]<.5f ? settings[OSC3_FIXED] : state->base_frequency;
                if (settings[oscillator*4+3]>.5f) base=2;
                float frequency=base*ratio[oscillator]*pitch_factor;
                float wave=waveform(&state->phase[oscillator],frequency,rate,(int)settings[oscillator*4],oscillator);
                if (oscillator==2) state->osc3_previous=wave;
                mixed+=wave*state->smooth[oscillator];
            }
            if (state->coefficient_counter==0 || settings[FILTER_MOD_ON]>.5f) {
                float mod=settings[FILTER_MOD_ON]>.5f ? modulation*settings[FILTER_MOD_DEPTH] : 0;
                float cutoff=state->smooth[6]*cutoff_scale[frame]*state->tracking_factor*exp2f(settings[CONTOUR]*state->contour+mod);
                cutoff=limit(cutoff,5.0f,rate*.15f);
                float tangent=tanf(3.141592654f*cutoff/rate);
                state->coefficient=tangent/(1+tangent);
            }
            state->coefficient_counter=(state->coefficient_counter+1)%8;
            float input=mixed*state->smooth[4]+state->previous_output*state->smooth[5];
            float filtered=ladder(state,input,state->coefficient,state->smooth[7],settings[FILTER_MODE]>.5f,architecture==4 ? 2 : 3);
            float value=saturate(filtered*state->amp*state->smooth[8]);
            state->previous_output=value;
            float blocked=value-state->dc_input+dc*state->dc_output;
            state->dc_input=value; state->dc_output=blocked;
            accumulated+=blocked;
        }
        output[frame]=accumulated/oversample;
    }
}

/* Desktop block API retained for callers that edit their parameter array. */
void synth_process(ModelDState *state,float *output,const float *pitch,const float *gate,
                   const float *trigger,const float *cutoff_scale,const float *resonance,
                   int frames,const double *parameters,int architecture) {
    ModelDPrepared prepared;
    synth_prepare(&prepared,parameters,state->rate);
    synth_process_prepared(state,output,pitch,gate,trigger,cutoff_scale,resonance,frames,&prepared,architecture);
}
