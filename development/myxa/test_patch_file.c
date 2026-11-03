#include <assert.h>
#include <stdio.h>
#include "patch_file.h"
#include <string.h>
#include <math.h>
typedef struct {uint8_t data[2][MYXA_FILE_SIZE];int length[2],cut,used,finish_fail,read_fail;} Media;
static int read_slot(void *u,int slot,uint8_t *b,size_t cap){Media*m=u;if(m->read_fail)return -1;assert(cap>=MYXA_FILE_SIZE);memcpy(b,m->data[slot],m->length[slot]);return m->length[slot];}
static int begin_slot(void *u,int slot){Media*m=u;m->length[slot]=0;return 0;}
static int write_slot(void *u,int slot,size_t off,const uint8_t *b,size_t n){
 Media*m=u;int count=(int)n;if(count>m->cut-m->used)count=m->cut-m->used;if(count<0)count=0;
 memcpy(m->data[slot]+off,b,count);m->length[slot]=(int)off+count;m->used+=count;return count;
}
static int finish_slot(void*u,int slot){Media*m=u;(void)slot;return m->finish_fail?-1:0;}
static MyxaPatchRecord factory(int i){MyxaPatchRecord r;memset(&r,0,sizeof(r));r.id=7;r.generation=1;r.engine=myxa_factory_patches[i].engine;strcpy(r.name,myxa_factory_patches[i].name);memcpy(r.values,myxa_factory_patches[i].values,sizeof(r.values));return r;}
int main(void){
 uint8_t bytes[MYXA_FILE_SIZE],saved[MYXA_FILE_SIZE];MyxaPatchRecord r=factory(0),decoded,guard;
 Media original={0};MyxaStore s;MyxaStoreIO io={&original,read_slot,begin_slot,write_slot,finish_slot};int cut,result,i;
 assert(MYXA_FILE_SIZE==392);
 for(i=0;i<3;i++){
  r=factory(i);assert(myxa_file_encode(&r,bytes,sizeof(bytes))==0);
  assert(myxa_file_decode(bytes,sizeof(bytes),&decoded)==0);
  assert(decoded.id==r.id&&decoded.generation==r.generation&&decoded.engine==r.engine&&!strcmp(decoded.name,r.name)&&!memcmp(decoded.values,r.values,sizeof(r.values)));
 }
 r=factory(0);assert(myxa_file_encode(&r,bytes,sizeof(bytes))==0);memcpy(saved,bytes,sizeof(bytes));
 memset(&guard,0x55,sizeof(guard));
 for(i=0;i<MYXA_FILE_SIZE;i++){decoded=guard;assert(myxa_file_decode(bytes,i,&decoded)!=0);assert(!memcmp(&decoded,&guard,sizeof(guard)));}
 for(i=0;i<MYXA_FILE_SIZE;i++){bytes[i]^=1;decoded=guard;assert(myxa_file_decode(bytes,sizeof(bytes),&decoded)!=0);assert(!memcmp(&decoded,&guard,sizeof(guard)));bytes[i]^=1;}
 r.values[0]=NAN;assert(myxa_file_encode(&r,bytes,sizeof(bytes))<0);r=factory(0);r.values[0]=1.5f;assert(myxa_file_encode(&r,bytes,sizeof(bytes))<0);
 r=factory(0);strcpy(r.name,"bad\nname");assert(myxa_file_encode(&r,bytes,sizeof(bytes))<0);
 r=factory(0);assert(myxa_store_load(&s,&io,7)==MYXA_STORE_EMPTY);
 assert(myxa_store_start(&s,&r)==MYXA_STORE_BUSY);original.cut=MYXA_FILE_SIZE;
 while((result=myxa_store_step(&s,&io))==MYXA_STORE_BUSY){}assert(result==MYXA_STORE_DONE);
 assert(s.active.generation==1&&s.active_slot==0);memcpy(saved,original.data[0],sizeof(saved));
 /* Power loss/short write at every byte boundary of the alternate slot. */
 for(cut=0;cut<=MYXA_FILE_SIZE;cut++){
  Media m=original;MyxaStore reboot;io.user=&m;m.used=0;m.cut=cut;
  assert(myxa_store_load(&s,&io,7)==0);r=factory(1);assert(myxa_store_start(&s,&r)==MYXA_STORE_BUSY);
  do{result=myxa_store_step(&s,&io);}while(result==MYXA_STORE_BUSY);
  assert(!memcmp(saved,m.data[0],sizeof(saved))); /* active file never touched */
  assert(myxa_store_load(&reboot,&io,7)==0);
  assert(reboot.active.generation==1||reboot.active.generation==2);
  if(reboot.active.generation==2)assert(!strcmp(reboot.active.name,r.name));
  assert(result==MYXA_STORE_DONE ? reboot.active.generation==2 : s.state==0);
 }
 /* Crashes after each whole state-machine step, including begin/flush/readback. */
 for(cut=0;cut<12;cut++){
  Media m=original;MyxaStore reboot;io.user=&m;m.used=0;m.cut=MYXA_FILE_SIZE;
  assert(myxa_store_load(&s,&io,7)==0);r=factory(2);assert(myxa_store_start(&s,&r)==MYXA_STORE_BUSY);
  for(i=0;i<cut;i++){result=myxa_store_step(&s,&io);if(result!=MYXA_STORE_BUSY)break;}
  assert(myxa_store_load(&reboot,&io,7)==0);assert(reboot.active.generation==1||reboot.active.generation==2);
 }
 {Media m=original;io.user=&m;m.cut=MYXA_FILE_SIZE;m.used=0;m.finish_fail=1;
  assert(myxa_store_load(&s,&io,7)==0);r=factory(2);assert(myxa_store_start(&s,&r)==MYXA_STORE_BUSY);
  while((result=myxa_store_step(&s,&io))==MYXA_STORE_BUSY){}assert(result==MYXA_STORE_IO);assert(!memcmp(saved,m.data[0],sizeof(saved)));
  m.read_fail=1;assert(myxa_store_load(&s,&io,7)==MYXA_STORE_IO);assert(myxa_store_start(&s,&r)<0);
 }
 /* Verification read failure or a valid but wrong readback cannot report DONE. */
 {Media m=original;io.user=&m;m.cut=MYXA_FILE_SIZE;m.used=0;
  assert(myxa_store_load(&s,&io,7)==0);r=factory(2);assert(myxa_store_start(&s,&r)==MYXA_STORE_BUSY);
  while(s.state!=5)assert(myxa_store_step(&s,&io)==MYXA_STORE_BUSY);
  m.read_fail=1;assert(myxa_store_step(&s,&io)==MYXA_STORE_IO);assert(s.active.generation==1);
 }
 {Media m=original;io.user=&m;m.cut=MYXA_FILE_SIZE;m.used=0;
  assert(myxa_store_load(&s,&io,7)==0);r=factory(2);assert(myxa_store_start(&s,&r)==MYXA_STORE_BUSY);
  while(s.state!=5)assert(myxa_store_step(&s,&io)==MYXA_STORE_BUSY);
  r=factory(1);r.generation=2;myxa_file_encode(&r,m.data[1],MYXA_FILE_SIZE);
  assert(myxa_store_step(&s,&io)==MYXA_STORE_IO);assert(s.active.generation==1);
 }
 /* A newer corrupt copy falls back; damaged-only media blocks overwrite. */
 {Media m=original;io.user=&m;r=factory(1);r.generation=2;myxa_file_encode(&r,m.data[1],MYXA_FILE_SIZE);m.length[1]=MYXA_FILE_SIZE;
  assert(myxa_store_load(&s,&io,7)==0&&s.active.generation==2);
  m.data[1][90]^=1;assert(myxa_store_load(&s,&io,7)==0&&s.active.generation==1);
  m.data[0][90]^=1;assert(myxa_store_load(&s,&io,7)==MYXA_FILE_INVALID);assert(myxa_store_start(&s,&r)<0);
 }
 /* Equal-generation conflicting records and foreign versions block saving. */
 {Media m=original;io.user=&m;r=factory(1);assert(myxa_file_encode(&r,m.data[1],MYXA_FILE_SIZE)==0);m.length[1]=MYXA_FILE_SIZE;
  assert(myxa_store_load(&s,&io,7)==MYXA_STORE_CONFLICT);assert(myxa_store_start(&s,&r)<0);
  m.data[1][4]=2;assert(myxa_store_load(&s,&io,7)==MYXA_FILE_UNSUPPORTED);
 }
 {Media m=original;io.user=&m;r=factory(0);r.generation=UINT32_MAX;myxa_file_encode(&r,m.data[0],MYXA_FILE_SIZE);
  assert(myxa_store_load(&s,&io,7)==0);assert(myxa_store_start(&s,&r)<0);}
 printf("Patch format and recovery checks passed: 393 byte-boundary failures, state interruptions, corrupt records and I/O failures.\n");return 0;
}
