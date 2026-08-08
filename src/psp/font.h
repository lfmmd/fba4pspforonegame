#ifndef _FONT_H_
#define _FONT_H_

#define R8G8B8_to_B5G6R5(c) ((c & 0xf80000) >> 19) | ((c & 0x00fc00) >> 5) | ((c & 0x0000f8) <<8)
//#define R8G8B8_to_B5G6R5(c) ((c & 0xf80000) >> 8) | ((c & 0x00fc00) >> 5) | ((c & 0x0000f8) >>3)

#define SCI_COLOR_WHITE   R8G8B8_to_B5G6R5(0xffffff)
#define SCI_COLOR_CYAN    R8G8B8_to_B5G6R5(0x00f0ff)
#define SCI_COLOR_ICE     R8G8B8_to_B5G6R5(0x8be9fd)
#define SCI_COLOR_BLUE    R8G8B8_to_B5G6R5(0x6272a4)
#define SCI_COLOR_DARK    R8G8B8_to_B5G6R5(0x384456)
#define SCI_COLOR_ACCENT  R8G8B8_to_B5G6R5(0x00e5ff)
#define SCI_COLOR_WARN    R8G8B8_to_B5G6R5(0xff5555)
#define SCI_COLOR_SHADOW  R8G8B8_to_B5G6R5(0x080e18)

void drawString(const char *s, unsigned short *screenbuf, int x, int y, unsigned short c, int w = 0);
void drawStringSciFi(const char *s, unsigned short *screenbuf, int x, int y, unsigned short c, int scale = 1, bool shadow = false, int w = 0);
int getDrawStringLength(const char *s);
int getDrawStringLengthScaled(const char *s, int scale = 1);

void drawRect(unsigned short *screenbuf, int x, int y, int w, int h, unsigned short c, unsigned char alpha = 0xFF);
void drawSciFiCard(unsigned short *screenbuf, int x, int y, int w, int h, unsigned short border_color, unsigned short fill_color, unsigned char fill_alpha = 0x40, int chamfer = 6);
void drawGlowHLine(unsigned short *screenbuf, int x, int y, int w, unsigned short color);
void drawCornerBracket(unsigned short *screenbuf, int x, int y, int w, int h, unsigned short color, int corner_len = 8);
void drawImage(unsigned short *screenbuf, int x, int y, int w,int h, unsigned short *imgBuf, int imgW, int imgH);

#endif	// _FONT_H_
