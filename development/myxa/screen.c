/* Minimal 128x64 patch screen. No framebuffer animations or audio work here. */
#include "freetribe.h"
#include "ugui.h"
static UG_GUI gui;
static UG_DEVICE display;
static void pixel(UG_S16 x,UG_S16 y,UG_COLOR c){ft_put_pixel(x,y,c!=0);}
void myxa_screen_init(void){
    display.x_dim=128;display.y_dim=64;display.pset=pixel;
    UG_Init(&gui,&display);UG_FontSelect(FONT_6X8);
    UG_SetBackcolor(C_BLACK);UG_SetForecolor(C_WHITE);UG_FillScreen(C_BLACK);
}
void myxa_screen_draw(const char *a,const char *b,const char *c,const char *d){
    UG_FillScreen(C_BLACK);
    UG_PutString(0,0,(char *)a);UG_PutString(0,16,(char *)b);
    UG_PutString(0,32,(char *)c);UG_PutString(0,48,(char *)d);/* Text drawing is immediate; no window manager update needed. */
}
