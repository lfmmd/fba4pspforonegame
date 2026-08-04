#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PGM Tile Viewer - 浏览游戏ROM中的tile字体数据
用于从PGM游戏ROM/Cache文件中查看tiles，辅助建立字符→tile索引映射表

支持格式:
  - 4bpp packed:   PGM text layer 8x8 tiles (32 bytes/tile, 0xf=透明)
  - 5bpp packed:   PGM BG tiles 原始格式 (5 bytes per 8 pixels)
  - 5bpp expanded: 已展开的5bpp (1 byte/pixel, 0x1f=透明)

用法:
  python tile_viewer.py
  python tile_viewer.py <romfile>
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import os
import sys


# ============================================================================
# Tile 解码引擎
# ============================================================================

def unpack_4bpp_row(src):
    """解包 4bpp packed 一行 (4 bytes → 8 pixels, low nibble first)"""
    return [
        src[0] & 0xf, (src[0] >> 4) & 0xf,
        src[1] & 0xf, (src[1] >> 4) & 0xf,
        src[2] & 0xf, (src[2] >> 4) & 0xf,
        src[3] & 0xf, (src[3] >> 4) & 0xf,
    ]


def unpack_5bpp_8px(src):
    """解包 5bpp packed (5 bytes → 8 pixels, 5 bits each)"""
    return [
        (src[0]      ) & 0x1f,
        ((src[0] >> 5) & 0x07) | ((src[1] << 3) & 0x18),
        ((src[1] >> 2) & 0x1f),
        ((src[1] >> 7) & 0x01) | ((src[2] << 1) & 0x1e),
        ((src[2] >> 4) & 0x0f) | ((src[3] << 4) & 0x10),
        ((src[3] >> 1) & 0x1f),
        ((src[3] >> 6) & 0x03) | ((src[4] << 2) & 0x1c),
        ((src[4] >> 3) & 0x1f),
    ]


def decode_tile_4bpp(data, offset, w=8, h=8):
    """解码 4bpp packed tile → 2D list[0..15]"""
    row_bytes = w // 2
    return [unpack_4bpp_row(data[offset + y * row_bytes:
                                   offset + y * row_bytes + row_bytes])[:w]
            for y in range(h)]


def decode_tile_5bpp_exp(data, offset, w=32, h=32):
    """解码 expanded 5bpp tile → 2D list[0..31]"""
    return [[data[offset + y * w + x] & 0x1f for x in range(w)] for y in range(h)]


def decode_tile_5bpp_packed(data, offset, w=32, h=32):
    """解码 packed 5bpp tile → 2D list[0..31]"""
    row_packed = w * 5 // 8
    rows = []
    for y in range(h):
        row = []
        for x8 in range(0, w, 8):
            row.extend(unpack_5bpp_8px(
                data[offset + y * row_packed + (x8 // 8) * 5:
                     offset + y * row_packed + (x8 // 8) * 5 + 5]))
        rows.append(row[:w])
    return rows


def bytes_per_tile(fmt, w, h):
    if fmt == "4bpp_packed":
        return w * h // 2
    elif fmt == "5bpp_expanded":
        return w * h
    elif fmt == "5bpp_packed":
        return w * h * 5 // 8
    return 0


def get_tile_decoder(fmt):
    if fmt == "4bpp_packed":
        return decode_tile_4bpp
    elif fmt == "5bpp_expanded":
        return decode_tile_5bpp_exp
    elif fmt == "5bpp_packed":
        return decode_tile_5bpp_packed
    raise ValueError(f"Unknown format: {fmt}")


# ============================================================================
# 调色板
# ============================================================================

GRAY4 = [(int(i * 255 / 14), int(i * 255 / 14), int(i * 255 / 14))
         if i != 15 else (255, 0, 255) for i in range(16)]

GRAY5 = [(int(i * 255 / 30), int(i * 255 / 30), int(i * 255 / 30))
         if i != 31 else (255, 0, 255) for i in range(32)]

INV4 = [(int(255 - i * 255 / 14), int(255 - i * 255 / 14), int(255 - i * 255 / 14))
        if i != 15 else (0, 180, 0) for i in range(16)]

AMBER4 = [(int(160 + i * 95 / 14), int((160 + i * 95 / 14) * 0.7), 0)
          if i != 15 else (0, 0, 0) for i in range(16)]

PALETTES = {
    "grayscale": {"4bpp_packed": GRAY4, "5bpp_packed": GRAY5, "5bpp_expanded": GRAY5},
    "inverted":  {"4bpp_packed": INV4, "5bpp_packed": GRAY5, "5bpp_expanded": GRAY5},
    "amber":     {"4bpp_packed": AMBER4, "5bpp_packed": GRAY5, "5bpp_expanded": GRAY5},
}


# ============================================================================
# Tile 网格渲染
# ============================================================================

def render_grid(data, offset, count, fmt, tw, th, palette, scale=2, cols=32):
    """
    渲染 tile 网格为 PPM P6 字节流
    返回: (ppm_bytes, width, height, n_tiles, n_cols, n_rows)
    """
    max_tiles = min(count, 4096)
    n_rows = (max_tiles + cols - 1) // cols
    cell_w = tw * scale + 1
    cell_h = th * scale + 1
    img_w = cols * cell_w + 1
    img_h = n_rows * cell_h + 1

    # 安全限制
    if img_h > 16000:
        n_rows = 16000 // cell_h
        img_h = n_rows * cell_h + 1
        max_tiles = n_rows * cols

    decode = get_tile_decoder(fmt)
    bpt = bytes_per_tile(fmt, tw, th)

    # 预分配图像缓冲区 (RGB 交错)
    img = bytearray(b'\x00' * img_w * img_h * 3)

    # 背景填充
    for y in range(img_h):
        base = y * img_w * 3
        for x in range(img_w):
            img[base + x * 3] = 30
            img[base + x * 3 + 1] = 30
            img[base + x * 3 + 2] = 50

    for idx in range(max_tiles):
        row, col = divmod(idx, cols)
        ox = col * cell_w + 1
        oy = row * cell_h + 1

        # 网格线
        for yy in range(cell_h):
            py = oy + yy
            if py >= img_h:
                break
            base = py * img_w * 3
            # 右边线
            rx = ox + tw * scale
            if rx < img_w:
                img[base + rx * 3] = 80
                img[base + rx * 3 + 1] = 80
                img[base + rx * 3 + 2] = 80
            # 底边线
            if yy == cell_h - 1:
                for xx in range(cell_w):
                    if ox + xx < img_w:
                        img[base + (ox + xx) * 3] = 80
                        img[base + (ox + xx) * 3 + 1] = 80
                        img[base + (ox + xx) * 3 + 2] = 80

        tile_off = offset + idx * bpt
        if tile_off + bpt > len(data):
            continue  # 超出文件范围，留空

        tile = decode(data, tile_off, tw, th)

        for ty in range(th):
            for sy in range(scale):
                py = oy + ty * scale + sy
                if py >= img_h:
                    break
                base = py * img_w * 3

                for tx in range(tw):
                    r, g, b = palette[tile[ty][tx]]
                    for sx in range(scale):
                        px = ox + tx * scale + sx
                        if px >= img_w:
                            break
                        img[base + px * 3] = r
                        img[base + px * 3 + 1] = g
                        img[base + px * 3 + 2] = b

    ppm = b'P6\n' + f'{img_w} {img_h}\n255\n'.encode() + bytes(img)
    return ppm, img_w, img_h, max_tiles, cols, n_rows


# ============================================================================
# GUI 应用
# ============================================================================

SZ_PRESETS = [
    ("PGM Text 8×8",      "4bpp_packed",   8,  8),
    ("PGM BG 32×32",      "5bpp_packed",  32, 32),
    ("PGM BG 16×16",      "5bpp_packed",  16, 16),
    ("5bpp expanded 32×32","5bpp_expanded",32, 32),
    ("",                   "",              0,  0),
]

# 常见 PGM cache 偏移 (PRG 总大小之后)
# kovshp: 68K BIOS 0x20000 + PRG 0x400000 = 0x420000 (tiles起点)
#         再加 4MB BIOS tiles → 0x820000 (游戏 BG tiles)
PGM_CACHE_HINTS = {
    "kovshp":    {"prg_total": 0x420000, "bios_tiles": 0x400000},
    "kovsh":     {"prg_total": 0x220000, "bios_tiles": 0x400000},
    "kov2":      {"prg_total": 0x620000, "bios_tiles": 0x800000},
    "olds":      {"prg_total": 0x220000, "bios_tiles": 0x400000},
    "killbld":   {"prg_total": 0x220000, "bios_tiles": 0x400000},
    "dmnfrnt":   {"prg_total": 0x420000, "bios_tiles": 0x400000},
    "ddp2":      {"prg_total": 0x220000, "bios_tiles": 0x400000},
    "martmast":  {"prg_total": 0x420000, "bios_tiles": 0x400000},
}


class TileViewer:
    def __init__(self, root):
        self.root = root
        self.root.title("PGM Tile Viewer — 游戏ROM字体浏览工具")
        self.root.geometry("1280x850")

        self.data = None
        self.filename = ""
        self.imgs = {}  # 防止 GC
        self.grid_info = None

        self.fmt_var = tk.StringVar(value="4bpp_packed")
        self.tw_var = tk.IntVar(value=8)
        self.th_var = tk.IntVar(value=8)
        self.offset_var = tk.StringVar(value="0")
        self.count_var = tk.StringVar(value="2048")
        self.cols_var = tk.IntVar(value=32)
        self.scale_var = tk.IntVar(value=2)
        self.pal_var = tk.StringVar(value="grayscale")

        self._build_ui()
        self._bind_keys()

        if len(sys.argv) > 1:
            self._load(sys.argv[1])

    # ---- UI 构建 ----

    def _build_ui(self):
        bar = ttk.Frame(self.root)
        bar.pack(fill=tk.X, padx=4, pady=3)

        # 第一行
        r1 = ttk.Frame(bar)
        r1.pack(fill=tk.X, pady=1)

        ttk.Button(r1, text="打开 ROM/Cache 文件...", command=self._open).pack(side=tk.LEFT, padx=2)
        ttk.Separator(r1, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        ttk.Label(r1, text="格式:").pack(side=tk.LEFT)
        c = ttk.Combobox(r1, textvariable=self.fmt_var, width=14,
                         values=["4bpp_packed", "5bpp_packed", "5bpp_expanded"],
                         state="readonly")
        c.pack(side=tk.LEFT, padx=2)

        ttk.Label(r1, text="宽:").pack(side=tk.LEFT, padx=(6, 0))
        ttk.Entry(r1, textvariable=self.tw_var, width=3).pack(side=tk.LEFT)
        ttk.Label(r1, text="高:").pack(side=tk.LEFT, padx=2)
        ttk.Entry(r1, textvariable=self.th_var, width=3).pack(side=tk.LEFT)

        ttk.Label(r1, text="  起始偏移:").pack(side=tk.LEFT, padx=(6, 0))
        ttk.Entry(r1, textvariable=self.offset_var, width=10).pack(side=tk.LEFT, padx=2)
        ttk.Label(r1, text="(支持 0x 前缀)").pack(side=tk.LEFT)

        ttk.Label(r1, text="  数量:").pack(side=tk.LEFT, padx=(10, 0))
        ttk.Entry(r1, textvariable=self.count_var, width=6).pack(side=tk.LEFT, padx=2)

        ttk.Label(r1, text="  列:").pack(side=tk.LEFT)
        ttk.Entry(r1, textvariable=self.cols_var, width=3).pack(side=tk.LEFT, padx=2)

        ttk.Label(r1, text="  缩放:").pack(side=tk.LEFT)
        ttk.Combobox(r1, textvariable=self.scale_var, width=2,
                     values=[1, 2, 3, 4, 6, 8], state="readonly").pack(side=tk.LEFT, padx=2)

        ttk.Label(r1, text="  调色板:").pack(side=tk.LEFT)
        ttk.Combobox(r1, textvariable=self.pal_var, width=8,
                     values=["grayscale", "inverted", "amber"], state="readonly").pack(side=tk.LEFT, padx=2)

        ttk.Button(r1, text="刷新 (F5)", command=self._refresh).pack(side=tk.LEFT, padx=6)
        ttk.Button(r1, text="跳到Tile...", command=self._goto).pack(side=tk.LEFT, padx=2)

        # 第二行：预设 + PGM 快捷偏移
        r2 = ttk.Frame(bar)
        r2.pack(fill=tk.X, pady=2)

        for label, fmt, tw, th in SZ_PRESETS:
            if fmt:
                ttk.Button(r2, text=label,
                           command=lambda f=fmt, w=tw, h=th: self._preset(f, w, h)).pack(side=tk.LEFT, padx=2)
            else:
                ttk.Separator(r2, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=6)

        ttk.Separator(r2, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=8)
        ttk.Label(r2, text="PGM快捷:").pack(side=tk.LEFT, padx=2)

        # 自动检测 PGM cache 结构
        ttk.Button(r2, text="自动检测PGM偏移",
                   command=self._pgm_auto).pack(side=tk.LEFT, padx=2)

        # 游戏选择 + 跳转 BG tiles
        self.pgm_game_var = tk.StringVar(value="kovshp")
        pgm_combo = ttk.Combobox(r2, textvariable=self.pgm_game_var, width=10,
                                 values=list(PGM_CACHE_HINTS.keys()),
                                 state="readonly")
        pgm_combo.pack(side=tk.LEFT, padx=2)
        ttk.Button(r2, text="→BG起点",
                   command=self._pgm_goto_bg).pack(side=tk.LEFT, padx=2)
        ttk.Button(r2, text="→Text起点",
                   command=self._pgm_goto_text).pack(side=tk.LEFT, padx=2)

        # Canvas
        cframe = ttk.Frame(self.root)
        cframe.pack(fill=tk.BOTH, expand=True, padx=4, pady=2)

        self.canvas = tk.Canvas(cframe, bg="#1a1a2e", highlightthickness=0)
        self.canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        vsb = ttk.Scrollbar(cframe, orient=tk.VERTICAL, command=self.canvas.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb = ttk.Scrollbar(self.root, orient=tk.HORIZONTAL, command=self.canvas.xview)
        hsb.pack(side=tk.BOTTOM, fill=tk.X, padx=4)

        self.canvas.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)

        self.canvas.bind("<Button-1>", self._click)
        self.canvas.bind("<MouseWheel>", lambda e: self.canvas.yview_scroll(-e.delta // 120, "units"))

        # 状态栏
        sf = ttk.Frame(self.root)
        sf.pack(fill=tk.X, padx=4, pady=2)
        self.status_lbl = ttk.Label(sf, text="就绪 — 请打开 ROM 文件")
        self.status_lbl.pack(side=tk.LEFT)
        self.info_lbl = ttk.Label(sf, text="")
        self.info_lbl.pack(side=tk.RIGHT)

    def _bind_keys(self):
        self.root.bind("<Control-o>", lambda e: self._open())
        self.root.bind("<F5>", lambda e: self._refresh())
        self.root.bind("<Control-g>", lambda e: self._goto())
        self.root.bind("<Control-f>", lambda e: self._goto())

    # ---- 操作 ----

    def _open(self):
        path = filedialog.askopenfilename(
            title="打开 ROM/Cache 文件",
            filetypes=[("ROM/BIN/Cache", "*.rom *.bin *.cache *.dat"), ("All", "*.*")])
        if path:
            self._load(path)

    def _load(self, path):
        try:
            size = os.path.getsize(path)
            read = min(size, 128 * 1024 * 1024)
            with open(path, "rb") as f:
                self.data = f.read(read)
            self.filename = path
            bname = os.path.basename(path)
            self.status_lbl.config(
                text=f"文件: {bname}  |  {size:,} bytes  "
                     f"({read:,} 已读取)")
            self._refresh()
        except Exception as e:
            messagebox.showerror("错误", str(e))

    def _preset(self, fmt, tw, th):
        self.fmt_var.set(fmt)
        self.tw_var.set(tw)
        self.th_var.set(th)
        self._refresh()

    def _pgm_auto(self):
        """自动检测 PGM cache 文件中的 tile 区域"""
        if not self.data:
            messagebox.showinfo("提示", "请先打开 PGM cache 文件")
            return
        # 扫描文件头找到 68K BIOS 特征，然后推算偏移
        # PGM cache: offset 0 = 68K BIOS, 包含 "PGM" 或复位向量
        result = []
        for name, info in PGM_CACHE_HINTS.items():
            off = info["prg_total"]
            if off + 100 < len(self.data):
                result.append(f"{name}: tile起点=0x{off:X}, BG起点=0x{off + info['bios_tiles']:X}")
        if result:
            messagebox.showinfo("PGM Cache 偏移参考",
                                "根据常见 PGM 游戏 ROM 大小推算:\n\n" +
                                "\n".join(result) +
                                f"\n\n当前选择: {self.pgm_game_var.get()}\n"
                                "点击 '→BG起点' 跳转到中文汉字所在的 BG tile 区\n"
                                "点击 '→Text起点' 跳转到 ASCII 文本 tile 区")
        else:
            messagebox.showwarning("?", "无法自动识别，请手动设置偏移")

    def _pgm_goto_bg(self):
        """跳转到 BG tiles 起点 (中文汉字区域)"""
        game = self.pgm_game_var.get()
        info = PGM_CACHE_HINTS.get(game)
        if info:
            off = info["prg_total"] + info["bios_tiles"]
            self.offset_var.set(f"0x{off:X}")
            self.fmt_var.set("5bpp_packed")
            self.tw_var.set(32)
            self.th_var.set(32)
            self.count_var.set("2048")
            self.cols_var.set(16)
            self.scale_var.set(1)
            self._refresh()

    def _pgm_goto_text(self):
        """跳转到 Text tiles 起点 (ASCII 区域)"""
        game = self.pgm_game_var.get()
        info = PGM_CACHE_HINTS.get(game)
        if info:
            off = info["prg_total"]
            self.offset_var.set(f"0x{off:X}")
            self.fmt_var.set("4bpp_packed")
            self.tw_var.set(8)
            self.th_var.set(8)
            self.count_var.set("2048")
            self.cols_var.set(32)
            self.scale_var.set(2)
            self._refresh()

    def _refresh(self):
        if not self.data:
            return
        try:
            off = int(self.offset_var.get(), 0)
            cnt = int(self.count_var.get())
        except ValueError:
            messagebox.showerror("参数错误", "偏移/数量需为整数")
            return

        fmt = self.fmt_var.get()
        tw = self.tw_var.get()
        th = self.th_var.get()
        scale = self.scale_var.get()
        cols = self.cols_var.get()

        if off >= len(self.data):
            messagebox.showerror("错误", f"偏移 0x{off:X} 超出文件范围")
            return

        pal = PALETTES[self.pal_var.get()][fmt]

        try:
            ppm, iw, ih, n, nc, nr = render_grid(
                self.data, off, cnt, fmt, tw, th, pal, scale, cols)
        except Exception as e:
            messagebox.showerror("渲染失败", str(e))
            import traceback; traceback.print_exc()
            return

        self.imgs['grid'] = img = tk.PhotoImage(data=ppm)
        self.grid_info = (off, cnt, fmt, tw, th, scale, cols, n, nc, nr)

        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor=tk.NW, image=img)
        self.canvas.configure(scrollregion=(0, 0, iw, ih))

        # Tile 编号标注
        cell_w = tw * scale + 1
        cell_h = th * scale + 1
        font_sz = max(5, scale * 3)
        for idx in range(n):
            r, c = divmod(idx, nc)
            self.canvas.create_text(
                c * cell_w + 2, r * cell_h + 2,
                text=str(idx), anchor=tk.NW,
                fill="#00ff00", font=("Consolas", font_sz))

        self.status_lbl.config(
            text=f"{os.path.basename(self.filename)}  |  "
                 f"{n} tiles  |  偏移: 0x{off:X}  |  {fmt}  |  {tw}×{th}×{scale}")
        self.info_lbl.config(text="点击 tile 查看详情 | Ctrl+G 跳转")

    def _click(self, evt):
        if not self.grid_info:
            return
        off, cnt, fmt, tw, th, scale, cols, n, nc, nr = self.grid_info
        cell_w = tw * scale + 1
        cell_h = th * scale + 1
        c = evt.x // cell_w
        r = evt.y // cell_h
        idx = r * nc + c
        if idx >= n:
            return

        bpt = bytes_per_tile(fmt, tw, th)
        file_off = off + idx * bpt

        # 高亮
        self.canvas.delete("hl")
        self.canvas.create_rectangle(
            c * cell_w, r * cell_h, (c + 1) * cell_w, (r + 1) * cell_h,
            outline="#ff3333", width=2, tags="hl")
        self.canvas.create_rectangle(
            c * cell_w + 1, r * cell_h + 1, (c + 1) * cell_w - 1, (r + 1) * cell_h - 1,
            outline="#ff3333", width=1, tags="hl")

        self.info_lbl.config(
            text=f"选中 Tile #{idx}  |  偏移: 0x{file_off:X} ({file_off})  "
                 f"|  坐标: ({c},{r})")

        self._show_zoom(idx, file_off, fmt, tw, th)

    def _show_zoom(self, idx, file_off, fmt, tw, th):
        palette = PALETTES[self.pal_var.get()][fmt]
        decode = get_tile_decoder(fmt)
        tile = decode(self.data, file_off, tw, th)

        z = max(2, min(16, 256 // max(tw, th)))
        from tile_viewer import render_tile_to_image
        # inline helper
        ppm_data = bytearray()
        for y in range(th):
            row = bytearray()
            for x in range(tw):
                r, g, b = palette[tile[y][x]]
                for _ in range(z):
                    row.extend([r, g, b])
            for _ in range(z):
                ppm_data.extend(row)
        sw, sh = tw * z, th * z
        ppm = f'P6\n{sw} {sh}\n255\n'.encode() + bytes(ppm_data)

        if hasattr(self, '_zw') and self._zw:
            try: self._zw.destroy()
            except: pass

        self._zw = tk.Toplevel(self.root)
        self._zw.title(f"Tile #{idx} — 0x{file_off:X}")
        self._zw.resizable(False, False)
        self.imgs['zoom'] = zimg = tk.PhotoImage(data=ppm)

        tk.Label(self._zw, image=zimg).pack(padx=8, pady=8)
        tk.Label(self._zw,
                 text=f"Tile #{idx}    偏移: 0x{file_off:X} ({file_off})\n"
                      f"尺寸: {tw}×{th}    格式: {fmt}",
                 font=("Consolas", 9)).pack(pady=2)

        def copy():
            self.root.clipboard_clear()
            self.root.clipboard_append(f"0x{file_off:X}")

        bf = ttk.Frame(self._zw)
        bf.pack(pady=4)
        ttk.Button(bf, text="复制偏移 (0x{:X})".format(file_off), command=copy).pack(side=tk.LEFT, padx=4)
        ttk.Button(bf, text="上一个", command=lambda: self._nav_zoom(-1, idx)).pack(side=tk.LEFT, padx=2)
        ttk.Button(bf, text="下一个", command=lambda: self._nav_zoom(1, idx)).pack(side=tk.LEFT, padx=2)

    def _nav_zoom(self, d, cur):
        new_idx = cur + d
        if not self.grid_info:
            return
        off, cnt, fmt, tw, th, scale, cols, n, nc, nr = self.grid_info
        if 0 <= new_idx < n:
            bpt = bytes_per_tile(fmt, tw, th)
            file_off = off + new_idx * bpt
            self._show_zoom(new_idx, file_off, fmt, tw, th)

    def _goto(self):
        if not self.grid_info:
            return
        n = self.grid_info[7]
        v = simpledialog.askinteger("跳转", f"输入 tile 编号 (0~{n - 1}):", parent=self.root,
                                     minvalue=0, maxvalue=n - 1)
        if v is not None:
            _, _, _, tw, th, scale, cols, _, nc, nr = self.grid_info
            cell_h = th * scale + 1
            r = v // nc
            frac = r / nr if nr > 1 else 0
            self.canvas.yview_moveto(frac)


def main():
    root = tk.Tk()
    TileViewer(root)
    root.mainloop()


if __name__ == "__main__":
    main()
