#include <math.h>
#include <stdint.h>

static double soft(double value) {
    if (value > 3.0) return 1.0;
    if (value < -3.0) return -1.0;
    return value * (27.0 + value * value) / (27.0 + 9.0 * value * value);
}

static double blep(double phase, double step) {
    if (phase < step) {
        double position = phase / step;
        return position + position - position * position - 1.0;
    }
    if (phase > 1.0-step) {
        double position = (phase-1.0)/step;
        return position*position + position + position + 1.0;
    }
    return 0.0;
}

static double oscillator(double phase, double step, double blend, double width) {
    double saw = 2.0*phase - 1.0 - blep(phase, step);
    double offset = phase-width;
    if (offset < 0) offset += 1.0;
    double pulse = (phase < width ? 1.0 : -1.0) + blep(phase, step) - blep(offset, step);
    return saw*(1.0-blend) + pulse*blend;
}

void render_rubber_voice(float *output, const float *pitch, const float *gate,
                  const float *trigger, const float *cutoff_scale, const float *resonance,
                  int frames, int rate, const double *settings,
                  int architecture) {
    double phase_a=0.0, phase_b=0.21, phase_sub=0.0;
    double amp=0.0, envelope=0.0, frequency=49.0;
    double poles[4]={0}, state_one=0.0, state_two=0.0, sub_filter=0.0;
    double dc_input=0.0, dc_output=0.0;
    int attack_amp=0, attack_filter=0;
    const int oversample=2;
    double internal_rate=rate*oversample;
    double attack=1.0-exp(-1.0/(settings[7]*internal_rate));
    double filter_attack=1.0-exp(-1.0/(settings[17]*internal_rate));
    double decay=1.0-exp(-1.0/(settings[8]*internal_rate));
    double release=1.0-exp(-1.0/(settings[10]*internal_rate));
    double filter_decay=exp(-1.0/(settings[6]*internal_rate));
    double detune=pow(2.0,settings[2]/1200.0);
    double tuning=pow(2.0,settings[16]/1200.0);
    double glide=1.0-exp(-1.0/(fmax(0.0001,settings[14])*internal_rate));
    double sub_coeff=1.0-exp(-6.283185307179586*settings[13]/internal_rate);
    for (int frame=0; frame<frames; frame++) {
        if (trigger[frame] > 0) { attack_amp=1; attack_filter=1; }
        double accumulated=0.0;
        for (int sample=0; sample<oversample; sample++) {
            frequency += glide*(pitch[frame]*tuning-frequency);
            if (gate[frame] > 0) {
                if (attack_amp) {
                    amp += attack*(1.01-amp);
                    if (amp>=1.0) { amp=1.0; attack_amp=0; }
                } else amp += decay*(settings[9]-amp);
            } else { amp += release*(-amp); attack_amp=0; }
            if (attack_filter) {
                envelope += filter_attack*(1.01-envelope);
                if (envelope>=1.0) { envelope=1.0; attack_filter=0; }
            } else {
                double sustain=gate[frame]>0 ? settings[18] : 0.0;
                envelope=sustain+(envelope-sustain)*filter_decay;
            }
            double step=frequency/internal_rate;
            double width=fmax(.08,fmin(.92,settings[1]+settings[20]*envelope));
#ifdef PULSE_A
            double main=oscillator(phase_a,step,1.0,width);
#else
            double main=oscillator(phase_a,step,settings[0],width);
#endif
            main += 0.55*oscillator(phase_b,step*detune,settings[0],width);
            phase_a += step; phase_a -= floor(phase_a);
            phase_b += step*detune; phase_b -= floor(phase_b);
            phase_sub += step*0.5; phase_sub -= floor(phase_sub);
            double sub=sin(6.283185307179586*phase_sub);
            sub_filter += sub_coeff*(sub-sub_filter);
            double shaped=settings[19]==1.0 ? envelope : pow(fmax(0,envelope),settings[19]);
            double tracking=settings[21]==0.0 ? 1.0 : pow(frequency/49.0,settings[21]);
            double cutoff=fmin(internal_rate*0.15,settings[4]*cutoff_scale[frame]*tracking*pow(2.0,settings[5]*shaped));
            double feedback=fmax(0,fmin(.97,resonance[frame]+settings[22]*envelope));
            double filtered;
            if (architecture==0) {
                double coefficient=tan(3.141592653589793*cutoff/internal_rate);
                double damping=2.0-feedback*1.85;
                double alpha=1.0/(1.0+coefficient*(coefficient+damping));
                double difference=soft(main*settings[12])-state_two;
                double band=alpha*state_one+alpha*coefficient*difference;
                double low=state_two+alpha*coefficient*state_one+alpha*coefficient*coefficient*difference;
                state_one=2.0*band-state_one;
                state_two=2.0*low-state_two;
                filtered=low;
            } else {
                int stages=architecture==1 ? 2 : 4;
                double coefficient=1.0-exp(-6.283185307179586*cutoff/internal_rate);
                double value=soft(main*settings[12]-feedback*3.5*poles[stages-1]);
                for (int stage=0; stage<stages; stage++) {
                    poles[stage] += coefficient*(soft(value)-soft(poles[stage]));
                    value=poles[stage];
                }
                filtered=value;
            }
#ifdef CLEAN_SUB
            double main_value=filtered*amp*settings[15];
#ifdef MAIN_SOFT_DRIVE
            main_value=soft(main_value*1.5);
#elif defined(MAIN_CLIP)
            main_value=fmax(-.55,fmin(.55,main_value*1.5));
#else
            main_value=soft(main_value);
#endif
            double value=main_value+settings[3]*sub_filter*amp*settings[15];
#else
            double value=soft((filtered+settings[3]*sub_filter)*amp*settings[15]);
#endif
            double dc=value-dc_input+0.9995*dc_output;
            dc_input=value; dc_output=dc;
            accumulated += dc;
        }
        output[frame]=(float)(accumulated/oversample);
    }
}

void render_voice(float *output, const float *pitch, const float *gate,
                  const float *trigger, const float *cutoff_scale, const float *resonance,
                  int frames, int rate, const double *settings, int architecture) {
    double extended[23];
    for (int parameter=0; parameter<16; parameter++) extended[parameter]=settings[parameter];
    extended[16]=0.0;
    extended[17]=settings[7];
    extended[18]=0.0;
    extended[19]=1.0;
    extended[20]=0.0;
    extended[21]=0.0;
    extended[22]=0.0;
    render_rubber_voice(output,pitch,gate,trigger,cutoff_scale,resonance,
                        frames,rate,extended,architecture);
}
