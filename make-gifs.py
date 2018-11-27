#!/usr/bin/python3

import math
import struct

HEADER_87A = b'GIF87a'
HEADER_89A = b'GIF89a'

def make_header (width, height, depth = 1, header = HEADER_89A, background_color = 0, pixel_aspect_ratio = 0, has_color_table = False, colors_sorted = False, color_table_size = 0):
    assert (0 <= width <= 65535)
    assert (0 <= height <= 65535)
    assert (1 <= depth <= 8)
    assert (0 <= color_table_size <= 7)

    flags = 0x00
    if has_color_table:
        flags |= 0x80
    flags = flags | (depth - 1) << 4
    if colors_sorted:
        flags |= 0x08
    flags |= color_table_size
    return struct.pack ('<6sHHBBB', header, width, height, flags, background_color, pixel_aspect_ratio)

def make_image_descriptor (width, height, left = 0, top = 0, has_color_table = False, interlace = False, colors_sorted = False, reserved = 0, color_table_size = 0):
    assert (0 <= width <= 65535)
    assert (0 <= height <= 65535)
    assert (0 <= left <= 65535)
    assert (0 <= top <= 65535)
    assert (0 <= reserved <= 3)
    assert (0 <= color_table_size <= 7)
    flags = 0x00
    if has_color_table:
        flags |= 0x80
    if interlace:
        flags |= 0x40
    if colors_sorted:
        flags |= 0x20
    flags |= reserved << 3
    flags |= color_table_size
    return struct.pack ('<BHHHHB', 0x2C, left, top, width, height, flags)

def parse_color (color):
    assert (len (color) == 7)
    assert (color[0] == '#')
    return (int (color[1:3], 16), int (color[3:5], 16), int (color[5:7], 16))

def make_color_table (colors):
    data = b''
    for color in colors:
        (red, green, blue) = parse_color (color)
        data += struct.pack ('BBB', red, green, blue)
    return data

def make_extension (label, data):
    return struct.pack ('BBB', 0x21, label, len (data)) + data + b'\0'

def make_graphic_control_extension (disposal_method = 0, reserved = 0, delay_time = 0, user_input = False, has_transparent = False, transparent_color = 0):
    assert (0 <= disposal_method <= 7)
    assert (0 <= reserved <= 7)
    assert (0 <= delay_time <= 65535)
    flags = 0x00
    flags |= disposal_method << 2
    if user_input:
        flags |= 0x02
    if has_transparent:
        flags |= 0x01
    data = struct.pack ('<BHB', flags, delay_time, transparent_color)
    return make_extension (0xf9, data)

def bits_required (value):
    if value == 0:
        return 1
    else:
        return math.ceil (math.log2 (value + 1))

def lzw_compress (values, depth = 0):
    if depth == 0:
        max_v = 0
        for v in values:
            max_v = max (v, max_v)
        depth = bits_required (max_v)
    else:
        for v in values:
            assert (v < 2**depth)
    n_colors = 2 ** depth

    codes = {}
    for i in range (n_colors):
        codes[(i,)] = i
    clear_code = n_colors # FIXME: Send clear when need code 4096
    eoi_code = n_colors + 1
    next_code = n_colors + 2

    code_size = bits_required (eoi_code)
    #if code_size < 3:
    #    code_size = 3

    code = (values[0],)
    stream = [(clear_code, code_size)]
    index = 1
    while index < len (values):
        code += (values[index],)
        index += 1
        if code not in codes:
            new_code = next_code
            next_code += 1

            codes[code] = new_code
            stream.append ((codes[code[:-1]], code_size))
            code = code[-1:]

            if new_code == 2 ** code_size:
                code_size += 1
    stream.append ((codes[code], code_size))
    stream.append ((eoi_code, code_size))
    return stream

def make_lzw_data (values, depth = 0):
    codes = lzw_compress (values, depth)

    # Write starting code size
    data = struct.pack ('B', codes[0][1] - 1)

    # Pack bits into blocks
    block = b''
    blocks = []
    octet = 0
    octet_length = 0
    for (code, code_size) in codes:
        octet |= code << octet_length
        octet_length += code_size
        while octet_length > 8:
            block += struct.pack ('B', octet & 0xFF)
            if len (block) == 255:
                blocks.append (block)
                block = b''
            octet >>= 8
            octet_length -= 8

    # Use partially filled octet and block
    if octet_length > 0:
        block += struct.pack ('B', octet)
    if len (block) > 0:
        blocks.append (block)

    # Terminate with an empty block
    blocks.append (b'')

    # Write blocks with block headers
    for b in blocks:
        data += struct.pack ('B', len (b)) + b

    return data

def make_trailer ():
    return b'\x3b'

def make_simple_gif (width, height, values, colors, background_color = 0):
    depth = bits_required (len (colors) - 1)
    data = make_header (width, height, depth = depth, has_color_table = True, color_table_size = depth - 1, background_color = background_color)
    data += make_color_table (colors)
    data += make_image_descriptor (width, height)
    data += make_lzw_data (values, depth)
    return data + make_trailer ()

open ('0_1x1_aabbcc.gif', 'wb').write (make_simple_gif (1, 1, [1], ['#000000', '#aabbcc']))
open ('0_2x2_aabbcc.gif', 'wb').write (make_simple_gif (2, 2, [1] * 4, ['#000000', '#aabbcc']))
open ('0_3x3_aabbcc.gif', 'wb').write (make_simple_gif (3, 3, [1] * 9, ['#000000', '#aabbcc', '#000000', '#000000']))
open ('0_10x10_aabbcc.gif', 'wb').write (make_simple_gif (10, 10, [1] * 100, ['#000000', '#aabbcc', '#000000', '#000000']))

open ('0_2x2_colors.gif', 'wb').write (make_simple_gif (2, 2, [0, 1, 2, 3], ['#ff0000', '#ffff00', '#ff00ff', '#ffffff']))

open ('0_16x16_red.gif', 'wb').write (make_simple_gif (16, 16, [1] * 256, ['#000000', '#ff0000']))
values = []
colors = []
for i in range (256):
    values.append (i)
    colors.append ('#%02x0000' % i)
open ('0_16x16_reds.gif', 'wb').write (make_simple_gif (16, 16, values, colors))

open ('0_16x16_green.gif', 'wb').write (make_simple_gif (16, 16, [1] * 256, ['#000000', '#00ff00']))
values = []
colors = []
for i in range (256):
    values.append (i)
    colors.append ('#00%02x00' % i)
open ('0_16x16_greens.gif', 'wb').write (make_simple_gif (16, 16, values, colors))

open ('0_16x16_blue.gif', 'wb').write (make_simple_gif (16, 16, [1] * 256, ['#000000', '#0000ff']))
values = []
colors = []
for i in range (256):
    values.append (i)
    colors.append ('#0000%02x' % i)
open ('0_16x16_blues.gif', 'wb').write (make_simple_gif (16, 16, values, colors))

open ('0_65535x1.gif', 'wb').write (make_simple_gif (65535, 1, [1] * 65535, ['#000000', '#ff0000', '#00ff00', '#0000ff']))
open ('0_1x65535.gif', 'wb').write (make_simple_gif (1, 65535, [1] * 65535, ['#000000', '#ff0000', '#00ff00', '#0000ff']))

colors = ['#ffffff', '#ff0000', '#0000ff', '#000000']
values = [ 1, 1, 1, 1, 1, 2, 2, 2, 2, 2,
           1, 1, 1, 1, 1, 2, 2, 2, 2, 2,
           1, 1, 1, 1, 1, 2, 2, 2, 2, 2,
           1, 1, 1, 0, 0, 0, 0, 2, 2, 2,
           1, 1, 1, 0, 0, 0, 0, 2, 2, 2,
           2, 2, 2, 0, 0, 0, 0, 1, 1, 1,
           2, 2, 2, 0, 0, 0, 0, 1, 1, 1,
           2, 2, 2, 2, 2, 1, 1, 1, 1, 1,
           2, 2, 2, 2, 2, 1, 1, 1, 1, 1,
           2, 2, 2, 2, 2, 1, 1, 1, 1, 1 ]
header = make_header (10, 10, depth = 2, has_color_table = True, color_table_size = 1)
color_table = make_color_table (colors)
gce = make_graphic_control_extension ()
image_descriptor = make_image_descriptor (10, 10)
data = make_lzw_data (values)
image = header + color_table + gce + image_descriptor + data + make_trailer ()
open ('sample_2.gif', 'wb').write (image)
