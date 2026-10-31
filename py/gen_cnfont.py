#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import io
from PIL import Image, ImageDraw, ImageFont
FONT = 'C:/Windows/Fonts/simsun.ttc'
STRINGS = {
    'S_PlotMode': '绘图模式', 'S_Bright': '亮度', 'S_Lsb': '分压系数',
    'S_PwmOut': '方波输出', 'S_PwmFreq': '方波频率', 'S_PwmDuty': '占空比',
    'S_WaveOut': '波形输出', 'S_WaveType': '波形类型', 'S_WaveFreq': '波形频率', 'S_UartOut': '串口输出',
    'S_Lang': '语言', 'S_Batt': '电池电压',
    'S_Cursor': '光标测量', 'S_Creator': '创作者信息', 'S_Cal': '校准表',
    'S_Ori': '原作', 'S_Dev': '开发', 'S_Proj': '项目说明地址',
    'S_On': '开', 'S_Off': '关', 'S_Dots': '点', 'S_Vect': '线',
    'S_Sine': '正弦', 'S_Tri': '三角', 'S_Saw': '锯齿',
    'S_Cn': '中文', 'S_En': '英文',
    'S_SaveOk': '保存成功', 'S_SaveFail': '保存失败',
    'S_Cancel': '已取消修改', 'S_Scroll': '滚动模式',
}
chars = []
for t in STRINGS.values():
    for c in t:
        if c not in chars:
            chars.append(c)
font = ImageFont.truetype(FONT, 12)
glyphs = []
for ch in chars:
    img = Image.new('L', (12, 12), 0)
    ImageDraw.Draw(img).text((0, -1), ch, fill=255, font=font)
    px = img.load()
    data = []
    for page in (0, 1):
        for x in range(12):
            b = 0
            for bit in range(8):
                y = page * 8 + bit
                if y < 12 and px[x, y] > 100:
                    b |= (1 << bit)
            data.append(b)
    glyphs.append(data)
out = ['/* cnfont.h - 由 py/gen_cnfont.py 自动生成, 请勿手改 */',
       '#ifndef CNFONT_H', '#define CNFONT_H', '',
       '#include "STC8A8K64S4A12.H"', '',
       '#define CN_CHAR_COUNT %d' % len(chars),
       '#define CN_W 12', '#define CN_H 12', '#define CN_GLYPH_END 0xFF', '',
       '/* 12x12 字模: 24 字节(2 页 x 12 列) */',
       'const unsigned char code CHS_12x12[CN_CHAR_COUNT][24] = {']
for g in glyphs:
    out.append('    {' + ', '.join('0x%02X' % b for b in g) + '},')
out += ['};', '', '/* 中文串(字模索引 + 0xFF 结束) */']
idx = {c: i for i, c in enumerate(chars)}
for name, txt in STRINGS.items():
    out.append('const unsigned char code %s[] = {%s};' % (name, ', '.join(str(idx[c]) for c in txt) + ', 255'))
out += ['', '#endif']
io.open('include/cnfont.h', 'w', encoding='gbk', newline='\r\n').write('\n'.join(out))
print('字模 %d 字, %d 串 -> include/cnfont.h' % (len(chars), len(STRINGS)))
