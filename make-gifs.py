#!/usr/bin/python3

import math
import struct

HEADER_87A = b'GIF87a'
HEADER_89A = b'GIF89a'

def make_header (width, height, colors, original_depth = 8, header = HEADER_89A, background_color = 0, pixel_aspect_ratio = 0, colors_sorted = False):
    assert (0 <= width <= 65535)
    assert (0 <= height <= 65535)
    assert (1 <= original_depth <= 8)

    color_table_size = get_color_table_size (colors)
    assert (color_table_size <= 8)

    flags = 0x00
    if color_table_size > 0:
        flags |= 0x80
        flags |= color_table_size - 1
    flags = flags | (original_depth - 1) << 4
    if colors_sorted:
        flags |= 0x08
    return struct.pack ('<6sHHBBB', header, width, height, flags, background_color, pixel_aspect_ratio) + make_color_table (colors)

def make_image_descriptor (width, height, left = 0, top = 0, colors = [], interlace = False, colors_sorted = False, reserved = 0):
    assert (0 <= width <= 65535)
    assert (0 <= height <= 65535)
    assert (0 <= left <= 65535)
    assert (0 <= top <= 65535)
    assert (0 <= reserved <= 3)

    color_table_size = get_color_table_size (colors)
    assert (color_table_size <= 8)

    flags = 0x00
    if color_table_size > 0:
        flags |= 0x80
        flags |= color_table_size - 1
    if interlace:
        flags |= 0x40
    if colors_sorted:
        flags |= 0x20
    flags |= reserved << 3
    return struct.pack ('<BHHHHB', 0x2C, left, top, width, height, flags) + make_color_table (colors)

def get_color_table_size (colors):
    n_colors = len (colors)
    if n_colors == 0:
        return 0
    else:
        return max (math.ceil (math.log2 (n_colors)), 1)

def parse_color (color):
    assert (len (color) == 7)
    assert (color[0] == '#')
    return (int (color[1:3], 16), int (color[3:5], 16), int (color[5:7], 16))

def make_color_table (colors):
    if len (colors) == 0:
        return b''

    data = b''
    for color in colors:
        (red, green, blue) = parse_color (color)
        data += struct.pack ('BBB', red, green, blue)
    for i in range (len (colors) - 1, get_color_table_size (colors)):
        data += struct.pack ('BBB', 0, 0, 0)
    return data

def make_extension (label, blocks):
    data = struct.pack ('BB', 0x21, label)
    for block in blocks:
        assert (len (block) < 256)
        data += struct.pack ('B', len (block)) + block
    data += struct.pack ('B', 0)
    return data

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
    return make_extension (0xf9, [data])

def make_comment_extension (text):
    blocks = []
    while len (text) > 0:
        blocks.append (bytes (text[:255], 'utf-8'))
        text = text[254:]
    return make_extension (0xfe, blocks)

def make_plain_text_extension (text, left, top, width, height, cell_width, cell_height, foreground_color, background_color):
    assert (0 <= left <= 65535)
    assert (0 <= top <= 65535)
    assert (0 <= width <= 65535)
    assert (0 <= height <= 65535)
    assert (0 <= cell_width <= 255)
    assert (0 <= cell_height <= 255)
    assert (0 <= foreground_color <= 255)
    assert (0 <= background_color <= 255)
    blocks = []
    blocks.append (struct.pack ('<HHHHBBBB', left, top, width, height, cell_width, cell_height, foreground_color, background_color))
    while len (text) > 0:
        blocks.append (bytes (text[:255], 'ascii'))
        text = text[254:]
    return make_extension (0x01, blocks)

def make_application_extension (application_identifier, application_authentication_code, blocks):
    assert (len (application_identifier) == 8)
    assert (len (application_authentication_code) == 3)
    block = bytes (application_identifier + application_authentication_code, 'ascii')
    return make_extension (0xff, [block] + blocks)

def make_netscape_extension (loop_count = -1, buffer_size = -1):
    assert (loop_count < 65536)
    assert (buffer_size < 4294967296)
    blocks = []
    if loop_count >= 0:
        blocks.append (struct.pack ('<BH', 1, loop_count))
    if buffer_size >= 0:
        blocks.append (struct.pack ('<BI', 2, buffer_size))
    return make_application_extension ('NETSCAPE', '2.0', blocks)

def make_animexts_extension (loop_count = -1, buffer_size = -1):
    assert (loop_count < 65536)
    blocks = []
    if loop_count >= 0:
        blocks.append (struct.pack ('<BH', 1, loop_count))
    if buffer_size >= 0:
        blocks.append (struct.pack ('<BI', 2, buffer_size))
    return make_application_extension ('ANIMEXTS', '1.0', blocks)

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

    # Spec says code size is minimum three
    code_size = depth + 1
    if code_size < 3:
        code_size = 3

    codes = {}
    for i in range (2 ** (code_size - 1)):
        codes[(i,)] = i
    clear_code = 2 ** (code_size - 1) # FIXME: Send clear when need code 4096
    eoi_code = clear_code + 1
    next_code = clear_code + 2

    code = (values[0],)
    stream = [(clear_code, code_size)]
    index = 1
    while index < len (values):
        code += (values[index],)
        index += 1
        if code not in codes:
            if next_code < 4096:
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

def make_simple_gif (filename, width, height, values, colors, background_color = 0, comment = '', loop_count = -1, buffer_size = -1, use_animexts = False, extensions = []):
    depth = bits_required (len (colors) - 1)
    data = make_header (width, height, colors, background_color = background_color)
    if loop_count >= 0:
        if use_animexts:
            data += make_animexts_extension (loop_count, buffer_size)
        else:
            data += make_netscape_extension (loop_count, buffer_size)
    if comment != '':
        data += make_comment_extension (comment)
    for e in extensions:
        data += e
    data += make_image_descriptor (width, height)
    data += make_lzw_data (values, depth)
    data += make_trailer ()

    open (filename, 'wb').write (data)

make_simple_gif ('0_1x1_aabbcc.gif', 1, 1, [1], ['#000000', '#aabbcc'])
make_simple_gif ('0_2x2_aabbcc.gif', 2, 2, [1] * 4, ['#000000', '#aabbcc'])
make_simple_gif ('0_3x3_aabbcc.gif', 3, 3, [1] * 9, ['#000000', '#aabbcc', '#000000', '#000000'])
make_simple_gif ('0_10x10_aabbcc.gif', 10, 10, [1] * 100, ['#000000', '#aabbcc', '#000000', '#000000'])

make_simple_gif ('0_2x2_colors.gif', 2, 2, [0, 1, 2, 3], ['#ff0000', '#ffff00', '#ff00ff', '#ffffff'])

make_simple_gif ('0_16x16_red.gif', 16, 16, [1] * 256, ['#000000', '#ff0000'])
values = []
colors = []
for i in range (256):
    values.append (i)
    colors.append ('#%02x0000' % i)
make_simple_gif ('0_16x16_reds.gif', 16, 16, values, colors)

make_simple_gif ('0_16x16_green.gif', 16, 16, [1] * 256, ['#000000', '#00ff00'])
values = []
colors = []
for i in range (256):
    values.append (i)
    colors.append ('#00%02x00' % i)
make_simple_gif ('0_16x16_greens.gif', 16, 16, values, colors)

make_simple_gif ('0_16x16_blue.gif', 16, 16, [1] * 256, ['#000000', '#0000ff'])
values = []
colors = []
for i in range (256):
    values.append (i)
    colors.append ('#0000%02x' % i)
make_simple_gif ('0_16x16_blues.gif', 16, 16, values, colors)

# Maximum sizes
make_simple_gif ('0_65535x1.gif', 65535, 1, [1] * 65535, ['#000000', '#ff0000', '#00ff00', '#0000ff'])
make_simple_gif ('0_1x65535.gif', 1, 65535, [1] * 65535, ['#000000', '#ff0000', '#00ff00', '#0000ff'])

# Uses maximum 4095 codes
import random
values = []
seed = 1
for i in range (300*300):
    m = 2 ** 32
    seed = (1103515245 * seed + 12345) % m
    values.append (seed >> 31)
make_simple_gif ('0_300x300_4095_codes.gif', 300, 300, values, ['#000000', '#ffffff'])

# Comments
make_simple_gif ('0_1x1_comment.gif', 1, 1, [1], ['#000000', '#ffffff'], comment = 'Hello World!')
make_simple_gif ('0_1x1_large_comment.gif', 1, 1, [1], ['#000000', '#ffffff'], comment = ' '.join (['Hello World!'] * 1000))
make_simple_gif ('0_1x1_nul_comment.gif', 1, 1, [1], ['#000000', '#ffffff'], comment = '\0')
make_simple_gif ('0_1x1_invalid_ascii_comment.gif', 1, 1, [1], ['#000000', '#ffffff'], comment = '\xff')
make_simple_gif ('0_1x1_invalid_utf8_comment.gif', 1, 1, [1], ['#000000', '#ffffff'], comment = '\xc3\x28')

# Loops
make_simple_gif ('0_1x1_loop_infinite.gif', 1, 1, [1], ['#000000', '#ffffff'], loop_count = 0)
make_simple_gif ('0_1x1_loop_once.gif', 1, 1, [1], ['#000000', '#ffffff'], loop_count = 1)
make_simple_gif ('0_1x1_loop_max.gif', 1, 1, [1], ['#000000', '#ffffff'], loop_count = 65535)
make_simple_gif ('0_1x1_loop_buffer.gif', 1, 1, [1], ['#000000', '#ffffff'], loop_count = 0, buffer_size = 1024)
make_simple_gif ('0_1x1_loop_buffer_max.gif', 1, 1, [1], ['#000000', '#ffffff'], loop_count = 0, buffer_size = 4294967295)
make_simple_gif ('0_1x1_loop_animexts.gif', 1, 1, [1], ['#000000', '#ffffff'], loop_count = 0, use_animexts = True)
# Netscape extension without loop field
# Netscape extension with multiple loop fields

# Plain Text extension
plain_text_ext = make_plain_text_extension ('Hello', 0, 0, 5, 1, 8, 8, 1, 0)
make_simple_gif ('0_40x8_plain_text.gif', 40, 8, [0] * 40 * 8, ['#000000', '#ffffff'], extensions = [plain_text_ext])

# Unknown extensions
unknown_ext = make_extension (0x2a, [b'Hello', b'World'])
make_simple_gif ('0_1x1_unknown_extension.gif', 1, 1, [1], ['#000000', '#ffffff'], extensions = [unknown_ext])
unknown_app_ext = make_application_extension ('UNKNOWN!', 'XXX', [b'Hello', b'World'])
make_simple_gif ('0_1x1_unknown_application_extension.gif', 1, 1, [1], ['#000000', '#ffffff'], extensions = [unknown_app_ext])
nul_app_ext = make_application_extension ('\0\0\0\0\0\0\0\0', '\0\0\0', [b'\0\0\0\0', b'\0\0\0\0'])
make_simple_gif ('0_1x1_nul_application_extension.gif', 1, 1, [1], ['#000000', '#ffffff'], extensions = [nul_app_ext])

# LZW without clear, end
# Various disposal methods
# Double frame (overwrite)
# No global color table
# Background color outside color table
# Local color table

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
header = make_header (10, 10, colors, original_depth = 2)
gce = make_graphic_control_extension ()
image_descriptor = make_image_descriptor (10, 10)
data = make_lzw_data (values)
image = header + gce + image_descriptor + data + make_trailer ()
open ('sample_2.gif', 'wb').write (image)
