import json
import os
from pathlib import Path
import queue
import subprocess
import threading
import time
import wave

import numpy as np


def midi_backend():
    import mido
    return mido.Backend('mido.backends.rtmidi/LINUX_ALSA')


def outputs():
    import sounddevice as sd
    devices=sd.query_devices()
    results=[]
    pulse=next((index for index,item in enumerate(devices)
                if item['name']=='pulse' and item['max_output_channels']>=2),None)
    try:
        response=subprocess.run(['pactl','--format=json','list','sinks'],
                                 check=True,capture_output=True,text=True,timeout=3)
        for sink in json.loads(response.stdout):
            bluetooth=sink['name'].startswith('bluez_')
            results.append({'label':sink.get('description',sink['name'])+
                            (' · Bluetooth' if bluetooth else ' · PipeWire'),
                            'device':pulse,'sink':sink['name'],
                            'backend':'portaudio' if pulse is not None else 'pulse-simple',
                            'bluetooth':bluetooth})
    except (OSError,ValueError,subprocess.SubprocessError):
        pass
    for index,item in enumerate(devices):
        if item['max_output_channels']>=2:
            results.append({'label':item['name']+' · PortAudio','device':index,
                            'sink':None,'bluetooth':False})
    return results


def route_own_stream(sink):
    if not sink:
        return
    response=subprocess.run(['pactl','--format=json','list','sink-inputs'],
                             check=True,capture_output=True,text=True,timeout=3)
    for stream in json.loads(response.stdout):
        properties=stream.get('properties',{})
        if str(properties.get('application.process.id'))==str(os.getpid()):
            subprocess.run(['pactl','move-sink-input',str(stream['index']),sink],
                           check=True,capture_output=True,timeout=3)


class Recorder:
    def __init__(self,path,rate):
        self.path=Path(path)
        self.rate=rate
        self.queue=queue.Queue(maxsize=256)
        self.lock=threading.Lock()
        self.accepting=True
        self.stopping=threading.Event()
        self.error=None
        self.frames=0
        self.handle=self.path.open('xb')
        self.file=wave.open(self.handle,'wb')
        self.file.setparams((2,2,rate,0,'NONE','not compressed'))
        self.thread=threading.Thread(target=self._write,name='WAV writer',daemon=True)
        self.thread.start()

    def add(self,block):
        if not self.lock.acquire(blocking=False):
            self.error='Recording stopped: writer could not keep up.'
            self.stopping.set()
            return
        try:
            if self.accepting:
                try:
                    self.queue.put_nowait(block.copy())
                except queue.Full:
                    self.error='Recording stopped: disk queue overflow.'
                    self.accepting=False
                    self.stopping.set()
        finally:
            self.lock.release()

    def _write(self):
        try:
            while not self.stopping.is_set() or not self.queue.empty():
                try:
                    block=self.queue.get(timeout=.05)
                except queue.Empty:
                    continue
                integer=np.round(np.clip(block,-1,1)*32767).astype('<i2')
                self.file.writeframesraw(integer.tobytes())
                self.frames+=len(block)
        except (OSError,ValueError) as error:
            self.error=str(error)
        finally:
            self.file.close()
            self.handle.close()

    def stop(self):
        with self.lock:
            self.accepting=False
            self.stopping.set()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            self.error='Recording writer is still finishing.'


class Audio:
    def __init__(self,synth):
        self.synth=synth
        self.stream=None
        self.recorder=None
        self.underruns=0
        self.error=None
        self.last_callback=0
        self.callback_seconds=0

    def callback(self,outdata,frames,timing,status):
        started=time.perf_counter()
        outdata.fill(0)
        if status:
            self.underruns+=1
        try:
            mono=self.synth.render(frames)
            outdata[:,0]=mono
            outdata[:,1]=mono
            recorder=self.recorder
            if recorder:
                recorder.add(outdata)
        except Exception as error:
            outdata.fill(0)
            self.error=str(error)
        self.callback_seconds=time.perf_counter()-started
        self.last_callback=time.monotonic()

    def start(self,output,blocksize):
        self.stop()
        self.error=None
        self.underruns=0
        self.synth.send('panic')
        self.synth.drain()
        if output.get('backend')=='pulse-simple':
            from pulse_output import PulseStream
            self.stream=PulseStream(output['sink'],self.synth.rate,blocksize,self.callback,
                                    lambda message:setattr(self,'error',message))
            try:
                self.stream.start()
            except Exception:
                self.stop()
                raise
            return
        import sounddevice as sd
        previous=os.environ.get('PULSE_SINK')
        try:
            if output.get('sink'):
                os.environ['PULSE_SINK']=output['sink']
            self.stream=sd.OutputStream(device=output['device'],samplerate=self.synth.rate,
                    channels=2,dtype='float32',blocksize=blocksize,latency='low',callback=self.callback)
            self.stream.start()
            if output.get('sink'):
                try:
                    route_own_stream(output['sink'])
                except (OSError,ValueError,subprocess.SubprocessError):
                    self.synth.notifications.put(('error','Could not confirm PipeWire routing; check the output selector.'))
        except Exception:
            self.stop()
            raise
        finally:
            if previous is None:
                os.environ.pop('PULSE_SINK',None)
            else:
                os.environ['PULSE_SINK']=previous

    def stop_recording(self):
        recorder=self.recorder
        self.recorder=None
        if recorder:
            recorder.stop()
        return recorder

    def stop(self):
        self.stop_recording()
        if self.stream:
            try:
                self.stream.stop()
            except Exception as error:
                self.error=str(error)
            finally:
                try:
                    self.stream.close()
                except Exception as error:
                    self.error=str(error)
                self.stream=None


class Midi:
    def __init__(self,synth):
        self.synth=synth
        self.port=None
        self.last_message='No MIDI yet'

    def receive(self,message):
        kind=message.type
        if kind in ('note_on','note_off'):
            event=(kind,message.channel,message.note,message.velocity)
        elif kind=='pitchwheel':
            event=(kind,message.channel,message.pitch,0)
        elif kind=='control_change':
            event=(kind,message.channel,message.control,message.value)
        else:
            return
        self.last_message=str(message)
        self.synth.send('midi',event)

    def connect(self,name):
        self.close()
        self.port=midi_backend().open_input(name,callback=self.receive)

    def close(self):
        if self.port:
            self.port.close()
            self.port=None
        self.synth.send('panic')
