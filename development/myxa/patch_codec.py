"""Desktop MYXA v1 patch-file converter; output files are created exclusively."""
import argparse,json,math,struct,sys,zlib
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SCHEMA=json.loads((HERE/'schema.json').read_text())
SIZE=64+6*len(SCHEMA['parameters'])+4

def f32(value):return struct.unpack('<f',struct.pack('<f',value))[0]
def validate_value(spec,value):
    if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value):raise ValueError('Invalid '+spec['key'])
    try:value=f32(value)
    except (OverflowError,struct.error):raise ValueError('Invalid '+spec['key']) from None
    if not f32(spec['minimum'])<=value<=f32(spec['maximum']) or (spec['discrete'] and value!=int(value)):raise ValueError('Out of range '+spec['key'])
def encode(record):
    ident,generation=record['id'],record['generation']
    if any(type(v)!=int or not 1<=v<=0xffffffff for v in (ident,generation)):raise ValueError('Invalid ID/generation')
    if record['engine'] not in (3,4):raise ValueError('Unsupported engine')
    name=record['name'].encode('ascii')
    if not 1<=len(name)<=32 or any(c<32 or c>126 for c in name):raise ValueError('Name must be 1–32 printable ASCII characters')
    values=record['values']
    if len(values)!=len(SCHEMA['parameters']):raise ValueError('Wrong parameter count')
    out=bytearray(SIZE);out[:4]=b'MYXA'
    struct.pack_into('<HHHHII',out,4,1,SCHEMA['version'],SIZE,record['engine'],ident,generation)
    out[20]=len(name);out[24:24+len(name)]=name;struct.pack_into('<H',out,56,len(values))
    for i,(spec,value) in enumerate(zip(SCHEMA['parameters'],values)):
        validate_value(spec,value);struct.pack_into('<Hf',out,64+i*6,spec['id'],value)
    struct.pack_into('<I',out,SIZE-4,zlib.crc32(out[:-4]))
    return bytes(out)
def decode(data):
    if len(data)<12 or data[:4]!=b'MYXA':raise ValueError('Invalid patch header')
    version,schema,size,engine,ident,generation=struct.unpack_from('<HHHHII',data+bytes(max(0,20-len(data))),4)
    if version!=1 or schema!=SCHEMA['version']:raise ValueError('Unsupported patch version')
    if len(data)!=SIZE or size!=SIZE or struct.unpack_from('<H',data,56)[0]!=len(SCHEMA['parameters']):raise ValueError('Invalid patch length/count')
    if struct.unpack_from('<I',data,SIZE-4)[0]!=zlib.crc32(data[:-4]):raise ValueError('Patch checksum mismatch')
    n=data[20]
    if not 1<=n<=32 or any(data[21:24]+data[24+n:56]+data[58:64]):raise ValueError('Invalid name/reserved bytes')
    try:name=data[24:24+n].decode('ascii')
    except UnicodeDecodeError:raise ValueError('Invalid patch name') from None
    values={}
    for i in range(len(SCHEMA['parameters'])):
        key,value=struct.unpack_from('<Hf',data,64+i*6)
        if key in values or not 1<=key<=len(SCHEMA['parameters']):raise ValueError('Duplicate/unknown parameter ID')
        validate_value(SCHEMA['parameters'][key-1],value);values[key]=value
    record={'id':ident,'generation':generation,'engine':engine,'name':name,'values':[values[s['id']] for s in SCHEMA['parameters']]}
    encode(record) # same metadata validation as writer
    return record

def from_desktop(patch,ident,generation=1):
    sys.path.insert(0,str(ROOT/'desktop/live'))
    from model import validate_patch
    raw=patch;p=validate_patch(patch)
    if p['architecture'] not in SCHEMA['engine_ids']:raise ValueError('Only Model D / 18 dB patches are supported')
    eq=p['eq']
    if eq['enabled'] and (eq['low_hz'],eq['mid_hz'],eq['mid_q'],eq['high_hz'])!=(100,700,.7,2500):raise ValueError('Custom EQ tuning cannot be represented by MYXA v1')
    gains=[eq[k] if eq['enabled'] else 0 for k in ('low_db','mid_db','high_db')]
    values={**p['parameters'],'pan':raw.get('pan',0),'output_gain_db':p['output_gain_db'],
            **dict(zip(('eq_bass_db','eq_mid_db','eq_treble_db'),gains)),
            'reverb_mix':p['reverb']['mix'],'reverb_decay_s':p['reverb']['decay']}
    return {'id':ident,'generation':generation,'name':p['name'],'engine':SCHEMA['engine_ids'][p['architecture']],
            'values':[values[s['key']] for s in SCHEMA['parameters']]}
def to_desktop(record):
    # Float32 boundary rounding must still produce desktop-valid JSON ranges.
    v={s['key']:max(s['minimum'],min(s['maximum'],value)) for s,value in zip(SCHEMA['parameters'],record['values'])}
    return {'format':'electribe-desktop-patch-v2','name':record['name'],
            'architecture':{v:k for k,v in SCHEMA['engine_ids'].items()}[record['engine']],
            'parameters':{s['key']:v[s['key']] for s in SCHEMA['parameters'][:47]},
            'pan':v['pan'],'output_gain_db':v['output_gain_db'],
            'eq':{'enabled':any(v[k] for k in ('eq_bass_db','eq_mid_db','eq_treble_db')),
                  'low_hz':100,'mid_hz':700,'mid_q':.7,'high_hz':2500,
                  'low_db':v['eq_bass_db'],'mid_db':v['eq_mid_db'],'high_db':v['eq_treble_db']},
            'reverb':{'mix':v['reverb_mix'],'decay':v['reverb_decay_s']}}
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('direction',choices=('encode','decode'));parser.add_argument('source',type=Path);parser.add_argument('output',type=Path)
    parser.add_argument('--id',type=int,default=1);parser.add_argument('--generation',type=int,default=1)
    a=parser.parse_args()
    try:
        if a.direction=='encode':payload=encode(from_desktop(json.loads(a.source.read_text()),a.id,a.generation))
        else:
            with a.source.open('rb') as handle:data=handle.read(SIZE+1)
            payload=(json.dumps(to_desktop(decode(data)),indent=2)+'\n').encode()
        with a.output.open('xb') as handle:handle.write(payload)
    except (ValueError,OSError,KeyError) as error:parser.exit(1,str(error)+'\n')
if __name__=='__main__':main()
