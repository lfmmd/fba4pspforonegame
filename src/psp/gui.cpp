
#include <pspkernel.h>
#include <pspgu.h>
#include <pspgum.h>
#include <pspdisplay.h>

#include <stdarg.h>

#include "burnint.h"
#include "psp.h"
#include "font.h"


void * show_frame = (void *)(PSP_LINE_SIZE * SCREEN_HEIGHT * 2 * 0);
void * draw_frame = (void *)(PSP_LINE_SIZE * SCREEN_HEIGHT * 2 * 1);
void * work_frame = (void *)(PSP_LINE_SIZE * SCREEN_HEIGHT * 2 * 2);
void * tex_frame  = (void *)(PSP_LINE_SIZE * SCREEN_HEIGHT * 2 * 3);
unsigned short g_cachedBurnDrawBuf[PSP_LINE_SIZE * SCREEN_HEIGHT] __attribute__((aligned(64)));

static unsigned char* list=(unsigned char*)((PSP_LINE_SIZE * SCREEN_HEIGHT * 2 * 4)|0x4000000);
unsigned char* bgBuf=(unsigned char*)((PSP_LINE_SIZE * SCREEN_HEIGHT * 2 * 5)|0x4000000);
unsigned char* previewBuf=(unsigned char*)((PSP_LINE_SIZE * SCREEN_HEIGHT * 2 * 6)|0x4000000);
unsigned char* tmpBuf=(unsigned char*)((PSP_LINE_SIZE * SCREEN_HEIGHT * 2 * 7)|0x4000000);


struct Vertex* vertices=0;
static int nPrevStage;

static int VideoBufferWidth, VideoBufferHeight;

static int myProgressRangeCallback(double dProgressRange)
{
	
	return 0;
}

static int myProgressUpdateCallback(double dProgress, const char* pszText, bool bAbs)
{
	bprintf(PRINT_IMPORTANT, "%s %f %d", pszText, dProgress, bAbs);
	return 0;
}

int AppDebugPrintf(int nStatus, char* pszFormat, ...)
{
	va_list vaFormat;
	va_start(vaFormat, pszFormat);
	char buf[256];
	
	sprintf(buf, pszFormat, vaFormat);
	
	unsigned short fc;
	switch (nStatus) {
	case PRINT_UI:			fc = R8G8B8_to_B5G6R5(0x404040); break;
	case PRINT_IMPORTANT:	fc = R8G8B8_to_B5G6R5(0x600000); break;
	case PRINT_ERROR:		fc = R8G8B8_to_B5G6R5(0x606000); break;
	default:				fc = R8G8B8_to_B5G6R5(0x404040); break;
	}
	
	drawRect(GU_FRAME_ADDR(work_frame), 0, 0, 480, 20, fc);
	drawString(buf, GU_FRAME_ADDR(work_frame), 4, 4, R8G8B8_to_B5G6R5(0xffffff));

	drawRect(GU_FRAME_ADDR(tex_frame), 0, 0, 480, 20, fc);
	drawString(buf, GU_FRAME_ADDR(tex_frame), 4, 4, R8G8B8_to_B5G6R5(0xffffff));
	
	va_end(vaFormat);
	
	update_gui();
	
	return 0;
}


void init_gui()
{
	sceGuInit();
	sceGuStart(GU_DIRECT, list);
	sceGuDispBuffer(SCREEN_WIDTH, SCREEN_HEIGHT, show_frame, PSP_LINE_SIZE);
	sceGuClutMode(GU_PSM_5650, 0, 0xff, 0);
	sceGuDrawBuffer(GU_PSM_5650, draw_frame, PSP_LINE_SIZE);
	sceGuClear(GU_COLOR_BUFFER_BIT | GU_DEPTH_BUFFER_BIT);
	
	sceGuOffset(2048 - (SCREEN_WIDTH / 2), 2048 - (SCREEN_HEIGHT / 2));
	sceGuViewport(2048, 2048, SCREEN_WIDTH, SCREEN_HEIGHT);

	sceGuScissor(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT);
	sceGuEnable(GU_SCISSOR_TEST);
	
//	sceGuFrontFace(GU_CW);

	sceGuDisable(GU_ALPHA_TEST);
//	sceGuAlphaFunc(GU_LEQUAL, 0, 0x01);

	sceGuDisable(GU_BLEND);
//	sceGuBlendFunc(GU_ADD, GU_SRC_ALPHA, GU_ONE_MINUS_SRC_ALPHA, 0, 0);

	sceGuDisable(GU_DEPTH_TEST);
//	sceGuDepthRange(65535, 0);	//sceGuDepthRange(0xc350, 0x2710);
//	sceGuDepthFunc(GU_GEQUAL);
//	sceGuDepthMask(GU_TRUE);

	sceGuEnable(GU_TEXTURE_2D);
	sceGuTexMode(GU_PSM_5650, 0, 0, GU_FALSE);
	sceGuTexScale(1.0f / PSP_LINE_SIZE, 1.0f / PSP_LINE_SIZE);
	sceGuTexOffset(0.0f, 0.0f);
	sceGuTexFunc(GU_TFX_REPLACE, GU_TCC_RGBA);

	sceGuTexImage(0, 512, 512, 512, GU_FRAME_ADDR(work_frame));
//	sceGuTexFilter(GU_LINEAR, GU_LINEAR);
	sceGuTexFilter(GU_NEAREST, GU_NEAREST);

	sceGuDisable(GU_DITHER);
	
//	sceGuClearDepth(0);
	sceGuClearColor(0);

	sceGuFinish();
	sceGuSync(0, GU_SYNC_FINISH);
	sceGuDisplay(GU_TRUE);	
	
	nPrevStage = nGameStage;
	//bprintf = AppDebugPrintf;
	
	
	BurnExtProgressRangeCallback = myProgressRangeCallback;
	BurnExtProgressUpdateCallback = myProgressUpdateCallback;
	
	vertices = (struct Vertex*)((int)sceGuGetMemory(6 * sizeof(struct Vertex))+2*sizeof(struct Vertex));
	configureVertices();
}

void exit_gui()
{
	sceGuDisplay(GU_FALSE);
	sceGuTerm();
}

void update_gui()
{
	sceGuStart(GU_DIRECT, list);
 	sceGuDrawBufferList(GU_PSM_5650, draw_frame, PSP_LINE_SIZE);
	sceGuScissor(0, 0, SCREEN_WIDTH, SCREEN_HEIGHT);

	if ( nPrevStage != nGameStage ) {
		if ( nGameStage ) {
			sceGuTexImage(0, 512, 512, 512, GU_FRAME_ADDR(work_frame));
			sceGuTexFilter(GU_NEAREST, GU_NEAREST);
		} else {
			BurnDrvGetFullSize(&VideoBufferWidth, &VideoBufferHeight);
			sceGuTexImage(0, 512, 512, 512, GU_FRAME_ADDR(tex_frame));
			sceGuTexFilter(GU_LINEAR, GU_LINEAR);
		}
		nPrevStage = nGameStage;
	}

	if (!nGameStage) {
		// Fast hardware DMA copy from cached RAM to VRAM texture buffer
		sceGuCopyImage(GU_PSM_5650, 0, 0, (VideoBufferWidth > 0 ? VideoBufferWidth : 448), (VideoBufferHeight > 0 ? VideoBufferHeight : 224), PSP_LINE_SIZE, (void*)((unsigned int)g_cachedBurnDrawBuf & 0x0FFFFFFF), 0, 0, PSP_LINE_SIZE, (void*)(((unsigned int)tex_frame) | 0x4000000));
		sceGuTexFlush();
	}

	sceGuDrawArray(	GU_TRIANGLE_STRIP, 
					GU_TEXTURE_16BIT | GU_COLOR_5650 | GU_VERTEX_16BIT | GU_TRANSFORM_2D, 
					4, 0, vertices);

	sceGuFinish();
	sceGuSync(0, GU_SYNC_FINISH);
}

void clear_gui_texture(int color, int w, int h)
{
	int clearHeight = (h > 0 && h <= SCREEN_HEIGHT) ? h : SCREEN_HEIGHT;
	if (color == 0) {
		memset(g_cachedBurnDrawBuf, 0, PSP_LINE_SIZE * clearHeight * sizeof(unsigned short));
	} else {
		unsigned int color32 = ((unsigned short)color) | (((unsigned short)color) << 16);
		unsigned int *p = (unsigned int *)g_cachedBurnDrawBuf;
		int count = (PSP_LINE_SIZE * clearHeight) >> 1;
		for (int i = 0; i < count; i++) {
			p[i] = color32;
		}
	}
}
void configureVertices()
{
	if(vertices==0)
		return;
	if ( nGameStage ) {
			sceGuTexImage(0, 512, 512, 512, GU_FRAME_ADDR(work_frame));
			sceGuTexFilter(GU_NEAREST, GU_NEAREST);
	} else {
			memset(GU_FRAME_ADDR(0),0,PSP_LINE_SIZE * SCREEN_HEIGHT * 2 * 4);
			memset(g_cachedBurnDrawBuf, 0, sizeof(g_cachedBurnDrawBuf));
			BurnDrvGetFullSize(&VideoBufferWidth, &VideoBufferHeight);
			sceGuTexImage(0, 512, 512, 512, GU_FRAME_ADDR(tex_frame));
			sceGuTexFilter(GU_LINEAR, GU_LINEAR);
	}
	
	if ( nGameStage) {
		vertices[0].x = 0;
		vertices[1].x = SCREEN_WIDTH;
		vertices[2].x = 0;
		vertices[3].x = SCREEN_WIDTH;
		vertices[0].y = 0;
		vertices[1].y = 0;
		vertices[2].y = SCREEN_HEIGHT;
		vertices[3].y = SCREEN_HEIGHT;
		vertices[0].u = 0;
		vertices[0].v = 0;
		vertices[1].u = SCREEN_WIDTH;
		vertices[1].v = 0;
		vertices[2].u = 0;
		vertices[2].v = SCREEN_HEIGHT;
		vertices[3].u = SCREEN_WIDTH;
		vertices[3].v = SCREEN_HEIGHT;
	}else
	{
		vertices[0].x = (SCREEN_WIDTH-gameScreenWidth)/2;
		vertices[1].x = (SCREEN_WIDTH+gameScreenWidth)/2;
		vertices[2].x = vertices[0].x;
		vertices[3].x = vertices[1].x;
		vertices[0].y = (SCREEN_HEIGHT-gameScreenHeight)/2;
		vertices[1].y = vertices[0].y;
		vertices[2].y = (SCREEN_HEIGHT+gameScreenHeight)/2;
		vertices[3].y = vertices[2].y;
	
	switch(screenMode)
	{
		
		case 2:
		case 3:
			vertices[0].u = VideoBufferWidth;
			vertices[0].v = 0;
			vertices[1].u = VideoBufferWidth;
			vertices[1].v = VideoBufferHeight;
			vertices[2].u = 0;
			vertices[2].v = 0;
			vertices[3].u = 0;
			vertices[3].v = VideoBufferHeight;
			break;
		case 4:
		case 5:
			vertices[3].u = 0;
			vertices[3].v = 0;
			vertices[2].u = VideoBufferWidth;
			vertices[2].v = 0;
			vertices[1].u = 0;
			vertices[1].v = VideoBufferHeight;
			vertices[0].u = VideoBufferWidth;
			vertices[0].v = VideoBufferHeight;
			break;
		case 6:
		case 7:
			vertices[3].u = VideoBufferWidth;
			vertices[3].v = 0;
			vertices[2].u = VideoBufferWidth;
			vertices[2].v = VideoBufferHeight;
			vertices[1].u = 0;
			vertices[1].v = 0;
			vertices[0].u = 0;
			vertices[0].v = VideoBufferHeight;
			break;
		case 8:
			if(VideoBufferWidth>=SCREEN_WIDTH||VideoBufferHeight>=SCREEN_HEIGHT)
			{
				vertices[0].x = 0;
				vertices[1].x = VideoBufferWidth;
				vertices[2].x = 0;
				vertices[3].x = VideoBufferWidth;
				vertices[0].y = 0;
				vertices[1].y = 0;
				vertices[2].y = VideoBufferHeight;
				vertices[3].y = VideoBufferHeight;
				vertices[0].u = 0;
				vertices[0].v = 0;
				vertices[1].u = VideoBufferWidth;
				vertices[1].v = 0;
				vertices[2].u = 0;
				vertices[2].v = VideoBufferHeight;
				vertices[3].u = VideoBufferWidth;
				vertices[3].v = VideoBufferHeight;
			}else
			{
				vertices[0].x = (SCREEN_WIDTH-VideoBufferWidth)/2;
				vertices[1].x = (SCREEN_WIDTH+VideoBufferWidth)/2;
				vertices[2].x = (SCREEN_WIDTH-VideoBufferWidth)/2;
				vertices[3].x = (SCREEN_WIDTH+VideoBufferWidth)/2;
				vertices[0].y = (SCREEN_HEIGHT-VideoBufferHeight)/2;
				vertices[1].y = (SCREEN_HEIGHT-VideoBufferHeight)/2;
				vertices[2].y = (SCREEN_HEIGHT+VideoBufferHeight)/2;
				vertices[3].y = (SCREEN_HEIGHT+VideoBufferHeight)/2;
				vertices[0].u = 0;
				vertices[0].v = 0;
				vertices[1].u = VideoBufferWidth;
				vertices[1].v = 0;
				vertices[2].u = 0;
				vertices[2].v = VideoBufferHeight;
				vertices[3].u = VideoBufferWidth;
				vertices[3].v = VideoBufferHeight;
			}
			break;
		case 1:
		default:
			vertices[0].u = 0;
			vertices[0].v = 0;
			vertices[1].u = VideoBufferWidth;
			vertices[1].v = 0;
			vertices[2].u = 0;
			vertices[2].v = VideoBufferHeight;
			vertices[3].u = VideoBufferWidth;
			vertices[3].v = VideoBufferHeight;
	}
	}
	sceKernelDcacheWritebackAll();
}

