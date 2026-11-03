#ifndef MYXA_TEXT_H
#define MYXA_TEXT_H
#include <stddef.h>
/* Fixed-size LCD strings; no printf, floating-point formatting or allocation. */
static inline void myxa_append(char *dst,size_t cap,const char *src){
    size_t n=0;if(!cap)return;
    while(n<cap && dst[n])n++;
    if(n==cap){dst[cap-1]=0;return;}
    while(*src && n+1<cap)dst[n++]=*src++;
    dst[n]=0;
}
static inline void myxa_unsigned(char *dst,size_t cap,unsigned value){
    char tmp[11];unsigned n=0;
    do{tmp[n++]=(char)('0'+value%10);value/=10;}while(value);
    while(n){char digit[2]={tmp[--n],0};myxa_append(dst,cap,digit);}
}
static inline void myxa_value_text(char *dst,size_t cap,const char *label,int cents){
    unsigned magnitude=(unsigned)(cents<0?-(long long)cents:cents);
    if(!cap)return;
    dst[0]=0;
    myxa_append(dst,cap,label);myxa_append(dst,cap,cents<0?" -":" ");
    myxa_unsigned(dst,cap,magnitude/100);myxa_append(dst,cap,".");
    {char fraction[3]={(char)('0'+magnitude/10%10),(char)('0'+magnitude%10),0};myxa_append(dst,cap,fraction);}
}
#endif
