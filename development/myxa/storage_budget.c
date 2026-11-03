/* Link-size probe only. No SD driver: every disk operation reports NOT READY. */
#include "ff.h"
#include "diskio.h"
static FATFS filesystem;
static FIL file;
static DIR directory;
static FILINFO entry;
static unsigned char recovery_sector[512];
static unsigned char browser_page[1024];
static void (*volatile keep_api[12])(void);
static void *volatile keep_data[6];
void myxa_storage_budget_keep(void){
    keep_api[0]=(void(*)(void))f_mount;keep_api[1]=(void(*)(void))f_open;
    keep_api[2]=(void(*)(void))f_close;keep_api[3]=(void(*)(void))f_read;
    keep_api[4]=(void(*)(void))f_write;keep_api[5]=(void(*)(void))f_sync;
    keep_api[6]=(void(*)(void))f_opendir;keep_api[7]=(void(*)(void))f_readdir;
    keep_api[8]=(void(*)(void))f_closedir;keep_api[9]=(void(*)(void))f_rename;
    keep_api[10]=(void(*)(void))f_unlink;keep_api[11]=(void(*)(void))f_mkdir;
    keep_data[0]=&filesystem;keep_data[1]=&file;keep_data[2]=&directory;
    keep_data[3]=&entry;keep_data[4]=recovery_sector;keep_data[5]=browser_page;
}
DSTATUS disk_initialize(BYTE p){(void)p;return STA_NOINIT;}
DSTATUS disk_status(BYTE p){(void)p;return STA_NOINIT;}
DRESULT disk_read(BYTE p,BYTE *b,LBA_t s,UINT n){(void)p;(void)b;(void)s;(void)n;return RES_NOTRDY;}
DRESULT disk_write(BYTE p,const BYTE *b,LBA_t s,UINT n){(void)p;(void)b;(void)s;(void)n;return RES_NOTRDY;}
DRESULT disk_ioctl(BYTE p,BYTE c,void *b){(void)p;(void)c;(void)b;return RES_NOTRDY;}

#ifdef MYXA_RECORD_BUDGET
#include "patch_file.h"
static MyxaStore patch_store;
static void (*volatile keep_patch_api[5])(void);
static void *volatile keep_patch_state;
void myxa_record_budget_keep(void){
    keep_patch_api[0]=(void(*)(void))myxa_file_encode;
    keep_patch_api[1]=(void(*)(void))myxa_file_decode;
    keep_patch_api[2]=(void(*)(void))myxa_store_load;
    keep_patch_api[3]=(void(*)(void))myxa_store_start;
    keep_patch_api[4]=(void(*)(void))myxa_store_step;
    keep_patch_state=&patch_store;
}
#endif
