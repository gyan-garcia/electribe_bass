import argparse
import json
from pathlib import Path
import time

from model import ROOT,read_patch
from engine import Synth
from audio_io import Audio,Midi,midi_backend,outputs


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--smoke-audio',action='store_true')
    parser.add_argument('--bluetooth',action='store_true')
    args=parser.parse_args()
    report={'midi_inputs':midi_backend().get_input_names(),'outputs':outputs()}
    synth=Synth(read_patch(ROOT/'baselines/bassline-v1/preset.json'))
    midi=Midi(synth)
    audio=Audio(synth)
    try:
        mpk=next((name for name in report['midi_inputs'] if 'MPK' in name.upper()),None)
        if mpk:
            midi.connect(mpk)
            report['mpk_opened']=mpk
        if args.smoke_audio:
            if args.bluetooth:
                selected=next((item for item in report['outputs'] if item.get('bluetooth')),None)
                if selected is None: raise RuntimeError('No connected Bluetooth audio output')
            else:
                selected=next((item for item in report['outputs'] if item.get('sink') and 'analog' in item['sink']),report['outputs'][0])
            synth.send('master',0)
            audio.start(selected,256)
            time.sleep(2)
            report['silent_stream']={'output':selected,'active':audio.stream.active,
                                    'reported_latency_ms':float(audio.stream.latency)*1000,
                                    'underruns':None if selected.get('backend')=='pulse-simple' else audio.underruns,
                                    'error':audio.error,'peak':synth.peak}
            if audio.error or not audio.stream.active or synth.peak!=0:
                raise RuntimeError('Silent audio smoke test failed')
    finally:
        midi.close()
        audio.stop()
        synth.close()
    destination=Path(__file__).resolve().parent/'outputs'/('bluetooth-check.json' if args.bluetooth else 'device-check.json')
    destination.parent.mkdir(exist_ok=True)
    destination.write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
