import ctypes
import ctypes.util
import threading

import numpy as np


class SampleSpec(ctypes.Structure):
    _fields_=[('format',ctypes.c_int),('rate',ctypes.c_uint32),('channels',ctypes.c_uint8)]


class BufferAttributes(ctypes.Structure):
    _fields_=[(name,ctypes.c_uint32) for name in ('maxlength','tlength','prebuf','minreq','fragsize')]


class PulseStream:
    def __init__(self,sink,rate,frames,callback,on_error):
        self.sink=sink
        self.rate=rate
        self.frames=frames
        self.callback=callback
        self.on_error=on_error
        self.latency=frames*3/rate
        self.latency_measured=False
        self.active=False
        self.ready=threading.Event()
        self.stopping=threading.Event()
        self.error=None
        self.thread=None

    def start(self):
        self.thread=threading.Thread(target=self._run,name='PipeWire audio',daemon=True)
        self.thread.start()
        if not self.ready.wait(5):
            self.stopping.set()
            raise RuntimeError('Timed out connecting to the system audio output')
        if self.error:
            raise RuntimeError(self.error)

    def _run(self):
        handle=None
        library=None
        try:
            path=ctypes.util.find_library('pulse-simple')
            if not path:
                raise RuntimeError('PulseAudio compatibility library is unavailable')
            library=ctypes.CDLL(path)
            pulse=ctypes.CDLL(ctypes.util.find_library('pulse'))
            pulse.pa_strerror.argtypes=[ctypes.c_int]
            pulse.pa_strerror.restype=ctypes.c_char_p
            library.pa_simple_new.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int,
                 ctypes.c_char_p,ctypes.c_char_p,ctypes.POINTER(SampleSpec),ctypes.c_void_p,
                 ctypes.POINTER(BufferAttributes),ctypes.POINTER(ctypes.c_int)]
            library.pa_simple_new.restype=ctypes.c_void_p
            library.pa_simple_write.argtypes=[ctypes.c_void_p,ctypes.c_void_p,ctypes.c_size_t,
                                              ctypes.POINTER(ctypes.c_int)]
            library.pa_simple_write.restype=ctypes.c_int
            library.pa_simple_get_latency.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_int)]
            library.pa_simple_get_latency.restype=ctypes.c_uint64
            library.pa_simple_flush.argtypes=[ctypes.c_void_p,ctypes.POINTER(ctypes.c_int)]
            library.pa_simple_flush.restype=ctypes.c_int
            library.pa_simple_free.argtypes=[ctypes.c_void_p]
            library.pa_simple_free.restype=None
            spec=SampleSpec(5,self.rate,2)
            attributes=BufferAttributes(0xffffffff,self.frames*8*3,0,self.frames*8,0xffffffff)
            error=ctypes.c_int()
            handle=library.pa_simple_new(None,b'Electribe Bass Lab',1,self.sink.encode(),
                    b'Live bass synth',ctypes.byref(spec),None,ctypes.byref(attributes),ctypes.byref(error))
            if not handle:
                raise RuntimeError(pulse.pa_strerror(error.value).decode())
            self.active=True
            audio=np.zeros((self.frames,2),dtype=np.float32)
            self.ready.set()
            counter=0
            while not self.stopping.is_set():
                self.callback(audio,self.frames,None,False)
                if library.pa_simple_write(handle,audio.ctypes.data,audio.nbytes,ctypes.byref(error))<0:
                    raise RuntimeError(pulse.pa_strerror(error.value).decode())
                counter+=1
                if counter%32==0:
                    latency=library.pa_simple_get_latency(handle,ctypes.byref(error))
                    if latency!=0xffffffffffffffff:
                        self.latency=latency/1_000_000
                        self.latency_measured=True
        except Exception as error:
            self.error=str(error)
            self.on_error(self.error)
            self.ready.set()
        finally:
            self.active=False
            if handle and library:
                error=ctypes.c_int()
                library.pa_simple_flush(handle,ctypes.byref(error))
                library.pa_simple_free(handle)

    def stop(self):
        self.stopping.set()
        if self.thread and self.thread is not threading.current_thread():
            self.thread.join(timeout=3)

    def close(self):
        self.stop()
