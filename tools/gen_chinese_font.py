#!/usr/bin/env python
"""Generate Chinese font bitmap data for FBA4PSP font12[] format.

Renders each Chinese character at 12px height using SimHei (bold sans-serif),
converts to the unsigned short column-bitmask format used by font12[]:
  - One unsigned short per character column
  - Bits 0x8000 through 0x0010 represent rows 0-11 (top to bottom)
  - Width varies per character
"""

from PIL import Image, ImageFont, ImageDraw
import os

# Chinese characters needed for UI (~36 chars)
CHINESE_CHARS = (
    # Main menu items
    "加载游戏保存重置截图控制器跳帧联机同步服务模式退出"
    # Browse UI, status bar
    "路径信息发行商硬件电池"
)

# Map each character to a byte code 0x80+
CHAR_MAP = {}
for i, ch in enumerate(CHINESE_CHARS):
    CHAR_MAP[ch] = 0x80 + i

# Ensure no duplicates
assert len(CHINESE_CHARS) == len(set(CHINESE_CHARS)), "Duplicate characters!"
assert len(CHINESE_CHARS) <= 128, f"Too many characters: {len(CHINESE_CHARS)} > 128"

FONT_SIZE = 12
FONT_PATH = r"C:\Windows\Fonts\simhei.ttf"


def render_char(ch, font):
    """Render one character and return column-bitmask list."""
    # Get bounding box
    bbox = font.getbbox(ch)
    if bbox is None:
        # Fallback: use full height, estimate width
        return [0xFFFF] * 8  # solid block as fallback

    # Render to larger image for anti-aliasing, then threshold
    # Use 2x scale for sub-pixel accuracy
    scale = 3
    img_size = 32
    img = Image.new("L", (img_size * scale, img_size * scale), 0)
    draw = ImageDraw.Draw(img)
    draw.text((0, 0), ch, font=font, fill=255)

    # Find tight bounding box of rendered content
    arr = img.load()  # Use load() and array access instead of deprecated getdata
    # Build a list of non-empty rows and columns
    rows = [y for y in range(img.height) if any(arr[x, y] > 40 for x in range(img.width))]
    cols = [x for x in range(img.width) if any(arr[x, y] > 40 for y in range(img.height))]

    if not cols or not rows:
        return [0x0000]

    min_x, max_x = min(cols), max(cols)
    min_y, max_y = min(rows), max(rows)

    # Crop and scale down to FONT_SIZE height
    content_h = max_y - min_y + 1
    content_w = max_x - min_x + 1

    # Scale: the character should be ~12px tall in the original font
    # Calculate actual target height
    target_h = FONT_SIZE
    target_w = max(1, int(content_w * target_h / content_h + 0.5))

    # Ensure minimum reasonable width
    if target_w < 4 and len(ch.encode('utf-8')) > 1:
        target_w = max(4, target_w)

    # Clamp width
    if target_w > 16:
        target_w = 16

    # Resize the character image
    char_img = img.crop((min_x, min_y, max_x + 1, max_y + 1))
    char_img = char_img.resize((target_w, target_h), Image.LANCZOS)

    # Threshold: > 80 is "on"
    pix = char_img.load()
    columns = []
    for x in range(target_w):
        col_val = 0
        for y in range(min(target_h, 12)):
            if pix[x, y] > 80:
                # Row 0 = 0x8000, row 11 = 0x0010
                col_val |= (0x8000 >> y)
        columns.append(col_val)

    # Remove empty trailing columns
    while len(columns) > 1 and columns[-1] == 0:
        columns.pop()

    return columns


def main():
    # Try to load SimHei font
    try:
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE * 3)  # 3x for quality rendering
        print(f"Using font: {FONT_PATH}")
    except Exception:
        # Fallback: try other fonts
        fallbacks = [
            r"C:\Windows\Fonts\simsun.ttc",
            r"C:\Windows\Fonts\mingliub.ttc",
        ]
        font = None
        for fb in fallbacks:
            try:
                font = ImageFont.truetype(fb, FONT_SIZE * 3)
                print(f"Using fallback font: {fb}")
                break
            except Exception:
                continue
        if font is None:
            print("ERROR: No Chinese font found!")
            return

    # Render each character and collect data
    all_data = []  # flat list of unsigned shorts
    info_entries = []  # (offset, width) pairs

    for i, ch in enumerate(CHINESE_CHARS):
        columns = render_char(ch, font)
        offset = len(all_data)
        width = len(columns)
        all_data.extend(columns)
        info_entries.append((offset, width, ch, CHAR_MAP[ch]))

    # Generate C code
    print("=" * 60)
    print(f"Generated {len(CHINESE_CHARS)} Chinese characters")
    print(f"Total font data entries: {len(all_data)}")
    print("=" * 60)

    # Output font12[] data (Chinese portion only)
    print("\n// Chinese character bitmap data (SimHei 12px)")
    print("// Codes 0x80-0x{:02X}".format(0x80 + len(CHINESE_CHARS) - 1))
    print("// Format: one unsigned short per column, 0x8000=row0 ... 0x0010=row11")
    print()
    print("// --- Copy into font12[] at the end of the existing array ---")
    line_data = []
    for j, val in enumerate(all_data):
        line_data.append(f"0x{val:04X}")
        if len(line_data) == 8 or j == len(all_data) - 1:
            print("    " + ",".join(line_data) + ",")
            line_data = []

    # Output font12inf[] entries
    print()
    print("// Chinese character info entries (append to font12inf[])")
    print("// Index = 0x5F + (char_code - 0x80)")
    print()

    # Show the mapping table
    print("// Character mapping table for reference:")
    print("// Code | Char | Unicode | Meaning")
    print("// -----|------|---------|--------")
    for offset, width, ch, code in info_entries:
        print(f"// 0x{code:02X}  |  {ch}   | U+{ord(ch):04X}  | {width}px wide")

    print()
    # Print the font12inf entries as C code
    base_offset = len(all_data)  # This will be adjusted manually
    print("// font12inf[] entries for Chinese characters (starting after ASCII entries at index 0x5F):")
    prev_offset = 0  # Will be filled in manually
    for offset, width, ch, code in sorted(info_entries, key=lambda x: x[3]):
        # The offset value here is relative to all_data start
        # We'll note the cumulative offset for the user
        print(f"    {{{offset:3d},{width:2d}}}," f"  /* 0x{code:02X} '{ch}' */")

    # Also output a mapping header for ui.cpp
    print()
    print("// ====== For ui.cpp: character code constants ======")
    for offset, width, ch, code in sorted(info_entries, key=lambda x: x[3]):
        print(f"#define CH_{ord(ch):04X}  \\x{code:02X}  /* {ch} */")

    # Generate the complete string replacements
    print()
    print("// ====== String replacements for ui.cpp ======")

    def map_str(s):
        """Map Chinese chars to their byte codes."""
        return "".join(chr(CHAR_MAP[c]) for c in s)

    strings = {
        "LOAD_GAME": ("%1u 加载游戏 ", "%1u " + map_str("加载游戏") + " "),
        "SAVE_GAME": ("%1u 保存游戏 ", "%1u " + map_str("保存游戏") + " "),
        "RESET_GAME": ("重置游戏 ", map_str("重置游戏") + " "),
        "SCREEN_SHOT": ("截图 ", map_str("截图") + " "),
        "CONTROLLER": ("控制器: %1uP ", map_str("控制器") + ": %1uP "),
        "SKIP_FRAMES": ("跳帧: %1u", map_str("跳帧") + ": %1u"),
        "WIFI_GAME": ("联机: %s ", map_str("联机") + ": %s "),
        "SYNC_GAME": ("同步游戏 ", map_str("同步游戏") + " "),
        "SERVICE_MODE": ("服务模式", map_str("服务模式")),
        "EXIT_FBA": ("退出", map_str("退出")),
    }

    for key, (cn_str, hex_str) in strings.items():
        print(f"// {key}: {cn_str}")
        # Build the actual C escape string
        c_esc = '"'
        for ch in hex_str:
            if ch == ' ':
                c_esc += ' '
            elif ord(ch) >= 0x80:
                c_esc += f"\\x{ord(ch):02X}"
            else:
                c_esc += ch
        c_esc += '"'
        print(f"//   → {c_esc}")


if __name__ == "__main__":
    main()
