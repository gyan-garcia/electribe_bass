"""Render the actual firmware screen through uGUI into a host pixel buffer."""
import subprocess,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];HERE=Path(__file__).parent
ugui=ROOT/'development/freetribe/cpu/lib/UGUI'
with tempfile.TemporaryDirectory() as folder:
 p=Path(folder)
 (p/'freetribe.h').write_text('void ft_put_pixel(int x,int y,int c);\n')
 (p/'main.c').write_text('''#include <stdio.h>
static unsigned char pixels[64][128];
void ft_put_pixel(int x,int y,int c){if(x>=0&&x<128&&y>=0&&y<64)pixels[y][x]=c!=0;}
void myxa_screen_init(void);
void myxa_screen_draw(const char*,const char*,const char*,const char*);
int main(void){myxa_screen_init();myxa_screen_draw("UK Res Bass *","BOSS 03","Resonance 0.42","MUTED / FX pending");
puts("P1\\n128 64");for(int y=0;y<64;y++){for(int x=0;x<128;x++)printf("%d ",!pixels[y][x]);puts("");}return 0;}
''')
 sources=[str(f) for f in ugui.rglob('*.c')]
 includes=['-I'+str(d) for d in [ugui]+[d for d in ugui.rglob('*') if d.is_dir()]]
 subprocess.run(['gcc','-O2','-w','-ffunction-sections','-fdata-sections','-I'+folder,*includes,str(p/'main.c'),str(HERE/'screen.c'),*sources,'-Wl,--gc-sections','-lm','-o',str(p/'preview')],check=True)
 target=HERE/'build/screen.pbm'
 target.write_bytes(subprocess.check_output([str(p/'preview')]))
 from PIL import Image
 Image.open(target).resize((768,384),Image.Resampling.NEAREST).save(HERE/'build/screen.png')
 print(target)
