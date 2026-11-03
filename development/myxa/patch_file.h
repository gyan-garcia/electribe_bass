#ifndef MYXA_PATCH_FILE_H
#define MYXA_PATCH_FILE_H
#include <stddef.h>
#include <stdint.h>
#include "parameters.h"
#define MYXA_FILE_SIZE (64+6*MYXA_PARAMETER_COUNT+4)
#define MYXA_FILE_OK 0
#define MYXA_FILE_INVALID -1
#define MYXA_FILE_UNSUPPORTED -2
#define MYXA_STORE_IO -3
#define MYXA_STORE_CONFLICT -4
#define MYXA_STORE_EMPTY 1
#define MYXA_STORE_BUSY 2
#define MYXA_STORE_DONE 3
typedef struct {
    uint32_t id,generation;
    uint16_t engine;
    char name[33];
    float values[MYXA_PARAMETER_COUNT];
} MyxaPatchRecord;
int myxa_file_encode(const MyxaPatchRecord *record,uint8_t *bytes,size_t capacity);
int myxa_file_decode(const uint8_t *bytes,size_t length,MyxaPatchRecord *record);
/* Return read byte count, zero for absent slot, negative for I/O error.
 * begin truncates only the inactive slot. finish must flush/close successfully.
 * All callbacks must be bounded; no concurrent storage operations are allowed. */
typedef struct {
    void *user;
    int (*read)(void *user,int slot,uint8_t *bytes,size_t capacity);
    int (*begin)(void *user,int slot);
    int (*write)(void *user,int slot,size_t offset,const uint8_t *bytes,size_t count);
    int (*finish)(void *user,int slot);
} MyxaStoreIO;
typedef struct {
    MyxaPatchRecord active,pending;
    uint8_t bytes[MYXA_FILE_SIZE];
    int active_slot,target,state;
    size_t offset;
} MyxaStore;
/* Recover both slots. Unsupported versions or I/O errors block writes. */
int myxa_store_load(MyxaStore *store,const MyxaStoreIO *io,uint32_t id);
/* Caller must first load successfully (OK or EMPTY). No generation wrap. */
int myxa_store_start(MyxaStore *store,const MyxaPatchRecord *edited);
/* One bounded I/O operation per step; DONE only after readback verification. */
int myxa_store_step(MyxaStore *store,const MyxaStoreIO *io);
#endif
