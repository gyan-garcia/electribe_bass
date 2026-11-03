"""Run pinned upstream client with fake MIDI only; no device backend is imported.
This tests file/chunk/execute flow, not the real loader's RAM map or CPU handoff.
"""
import argparse,contextlib,hashlib,io,json,logging,runpy,sys,types
from pathlib import Path
from unittest.mock import patch
HERE=Path(__file__).resolve().parent

def run_client(repo,binary,bad_chunk=None,bad_magic=False):
    codec=runpy.run_path(str(repo/'scripts/e2_syx_codec.py'))
    uploaded=bytearray();executed=[];pivots=[];chunks=[]
    class E2:
        sysex_head=[0x42,0x30,0,1,0x24]
        inport=[]
        def __init__(self,*ports):self.outport=types.SimpleNamespace(send=lambda message:pivots.append(message))
        def test_sysex_message(self,data):
            assert data==[0x64,1,0x23,0x45,0x67]
            return [0]*5+([0]*4 if bad_magic else [0x76,0x54,0x32,0x10])
        def load_cpu_ram(self,data):
            assert len(data)==256
            encoded=codec['syx_enc'](data)
            assert all(0<=v<=127 for v in encoded)
            assert bytes(codec['syx_dec'](encoded))==data
            i=len(chunks);chunks.append(len(encoded));uploaded.extend(data)
            return [0]*5+[0 if bad_chunk==i else 0x21]
        def execute_cpu_ram(self,address):executed.append(address);return b'\xf0OK\xf7'
    fake_mido=types.ModuleType('mido');fake_mido.Message=lambda kind,data:types.SimpleNamespace(type=kind,data=data)
    fake_e2=types.ModuleType('e2sysex');fake_e2.E2Sysex=E2;fake_e2.syx_enc=codec['syx_enc']
    before=logging.root.manager.disable
    try:
        logging.disable(logging.CRITICAL)
        with patch.dict(sys.modules,{'mido':fake_mido,'e2sysex':fake_e2}),patch.object(sys,'argv',['execute_freetribe.py',str(binary),'FAKE_IN','FAKE_OUT']),patch('time.sleep'),contextlib.redirect_stdout(io.StringIO()):
            try:runpy.run_path(str(repo/'scripts/execute_freetribe.py'),run_name='__main__')
            except SystemExit:pass
    finally:logging.disable(before)
    return uploaded,executed,pivots,chunks

def main():
    parser=argparse.ArgumentParser();parser.add_argument('binary',type=Path);parser.add_argument('--repo',type=Path,default=HERE/'build/research-hacktribe');a=parser.parse_args()
    code=a.binary.read_bytes();padded=code+bytes((-len(code))%256)
    data,execute,pivots,chunks=run_client(a.repo,a.binary)
    assert data==padded and execute==[0x80000000] and len(pivots)==1
    assert pivots[0].data[5]==0x58
    for bad in (0,len(chunks)-1):
        _,execute,_,_=run_client(a.repo,a.binary,bad_chunk=bad);assert not execute
    _,execute,_,sent=run_client(a.repo,a.binary,bad_magic=True);assert not execute and not sent
    # 31250 bit/s serial MIDI, 10 bits per byte. Includes chunk SysEx frames,
    # excludes replies, pivot/magic/execute messages, delays and processing.
    minimum=sum(n+7 for n in chunks)*10/31250
    report={'binary_sha256':hashlib.sha256(code).hexdigest(),'binary_bytes':len(code),'padded_bytes':len(padded),
            'blocks':len(chunks),'execute_address':'0x80000000','chunk_serial_lower_bound_seconds':minimum,
            'tests':['exact padded transfer','7-bit codec roundtrip','bad first/final ACK prevents execution','bad magic prevents upload'],
            'scope':'Fake MIDI/client control flow only. No real receiver, flash, loader placement or target startup validation.'}
    (HERE/'build/ram-loader-client-test.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
if __name__=='__main__':main()
