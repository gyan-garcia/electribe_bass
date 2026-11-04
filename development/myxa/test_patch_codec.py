import ctypes,json,struct,subprocess,tempfile,unittest,zlib
from pathlib import Path
from patch_codec import ROOT,HERE,SCHEMA,SIZE,encode,decode,from_desktop,to_desktop
N=len(SCHEMA['parameters'])
class Record(ctypes.Structure):
    _fields_=[('id',ctypes.c_uint32),('generation',ctypes.c_uint32),('engine',ctypes.c_uint16),('name',ctypes.c_char*33),('values',ctypes.c_float*N)]
class CodecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory();lib=Path(cls.temp.name)/'codec.so'
        subprocess.run(['gcc','-std=c99','-Wall','-Wextra','-Werror','-shared','-fPIC',str(HERE/'patch_file.c'),'-lm','-o',str(lib)],check=True)
        cls.lib=ctypes.CDLL(str(lib));cls.lib.myxa_file_encode.argtypes=[ctypes.POINTER(Record),ctypes.c_void_p,ctypes.c_size_t]
        cls.lib.myxa_file_decode.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.POINTER(Record)]
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    def data(self,name='Moog-Res'):
        return encode(from_desktop(json.loads((ROOT/f'presets/user/{name}.json').read_text()),7))
    def test_three_factory_files_cross_language(self):
        for name in ('UK-Res-Bass','BOSS-03','Moog-Res'):
            data=self.data(name);r=Record();self.assertEqual(self.lib.myxa_file_decode(data,len(data),ctypes.byref(r)),0)
            out=ctypes.create_string_buffer(SIZE);self.assertEqual(self.lib.myxa_file_encode(ctypes.byref(r),out,SIZE),0)
            self.assertEqual(out.raw,data)
            record=decode(data);rebuilt=encode(from_desktop(to_desktop(record),7))
            self.assertEqual(rebuilt,data)
    def test_reject_valid_crc_malformed_fields(self):
        original=self.data()
        for offset,value in [(4,2),(6,2),(10,99),(20,0),(21,1),(58,1),(64,0),(70,1)]:
            data=bytearray(original);data[offset]=value;struct.pack_into('<I',data,SIZE-4,zlib.crc32(data[:-4]))
            with self.assertRaises(ValueError):decode(bytes(data))
            self.assertLess(self.lib.myxa_file_decode(bytes(data),SIZE,ctypes.byref(Record())),0)
        for value in (float('nan'),float('inf'),1.5,-1):
            data=bytearray(original);struct.pack_into('<f',data,66,value);struct.pack_into('<I',data,SIZE-4,zlib.crc32(data[:-4]))
            with self.assertRaises(ValueError):decode(bytes(data))
            self.assertLess(self.lib.myxa_file_decode(bytes(data),SIZE,ctypes.byref(Record())),0)
    def test_reordered_parameters_are_accepted(self):
        data=bytearray(self.data());a=data[64:70];data[64:70]=data[70:76];data[70:76]=a;struct.pack_into('<I',data,SIZE-4,zlib.crc32(data[:-4]))
        self.assertEqual(decode(bytes(data)),decode(self.data()))
        self.assertEqual(self.lib.myxa_file_decode(bytes(data),SIZE,ctypes.byref(Record())),0)
    def test_float32_range_boundaries_roundtrip(self):
        for edge in ('minimum','maximum'):
            record=decode(self.data());record['values']=[0 if s['key']=='filter_mode' else s[edge] for s in SCHEMA['parameters']]
            data=encode(record)
            self.assertEqual(encode(from_desktop(to_desktop(decode(data)),7)),data)
    def test_pan_and_effects_are_preserved(self):
        p=json.loads((ROOT/'presets/user/UK-Res-Bass.json').read_text());p['pan']=-.5
        result=to_desktop(decode(encode(from_desktop(p,8))))
        self.assertEqual(result['pan'],-.5);self.assertAlmostEqual(result['reverb']['mix'],.19,places=6)
        p['eq']['low_hz']=200
        with self.assertRaises(ValueError):from_desktop(p,8)
if __name__=='__main__':unittest.main(verbosity=2)
