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

def lzw_compress (values, depth = 0, start_with_clear = True, end_with_eoi = True):
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
    stream = []
    if start_with_clear:
        stream.append ((clear_code, code_size))
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
    if end_with_eoi:
        stream.append ((eoi_code, code_size))
    return stream

def make_lzw_data (values, depth = 0, start_with_clear = True, end_with_eoi = True):
    codes = lzw_compress (values, depth, start_with_clear, end_with_eoi)

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

def make_gif (name, width, height, values, colors, background_color = 0, comment = '', loop_count = -1, buffer_size = -1, extensions = [], start_with_clear = True, end_with_eoi = True):
    depth = bits_required (len (colors) - 1)
    data = make_header (width, height, colors, background_color = background_color)
    if loop_count >= 0:
        data += make_netscape_extension (loop_count, buffer_size)
    if comment != '':
        data += make_comment_extension (comment)
    for e in extensions:
        data += e
    data += make_image_descriptor (width, height)
    data += make_lzw_data (values, depth, start_with_clear, end_with_eoi)
    data += make_trailer ()

    filename = '%s.gif' % name
    open (filename, 'wb').write (data)

BLACK        = 0
WHITE        = 1
RED          = 2
GREEN        = 3
BLUE         = 4
CYAN         = 5
MAGENTA      = 6
YELLOW       = 7
DARK_GREY    = 8
LIGHT_GREY   = 9
DARK_RED     = 10
DARK_GREEN   = 11
DARK_BLUE    = 12
DARK_CYAN    = 13
DARK_MAGENTA = 14
DARK_YELLOW  = 15
palette16 = [ '#000000', '#ffffff',
              '#ff0000', '#00ff00',
              '#0000ff', '#00ffff', '#ff00ff', '#ffff00',
              '#555555', '#aaaaaa', '#800000', '#008000', '#000080', '#008080', '#800080', '#808000']
palette8 = palette16[:8]
palette4 = palette16[:4]
palette2 = palette16[:2]

def make_grayscale_palette (depth):
    n_colors = 2 ** depth
    colors = []
    for i in range (n_colors):
        colors.append ('#0000%02x' % (i * 255 // (n_colors - 1)))
    return colors
grays1 = make_grayscale_palette (1)
grays2 = make_grayscale_palette (2)
grays3 = make_grayscale_palette (3)
grays4 = make_grayscale_palette (4)
grays5 = make_grayscale_palette (5)
grays6 = make_grayscale_palette (6)
grays7 = make_grayscale_palette (7)
grays8 = make_grayscale_palette (8)

# Single pixel images
make_gif ('1x1x1_aabbcc', 1, 1, [1], ['#000000', '#aabbcc'])
make_gif ('1x1x1_ffffff', 1, 1, [1], grays1)
make_gif ('1x1x2_ffffff', 1, 1, [3], grays2)
make_gif ('1x1x3_ffffff', 1, 1, [7], grays3)
make_gif ('1x1x4_ffffff', 1, 1, [15], grays4)
make_gif ('1x1x5_ffffff', 1, 1, [31], grays5)
make_gif ('1x1x6_ffffff', 1, 1, [63], grays6)
make_gif ('1x1x7_ffffff', 1, 1, [127], grays7)
make_gif ('1x1x8_ffffff', 1, 1, [255], grays8)

# Filled images of increasing sizes
make_gif ('2x2_ffffff', 2, 2, [WHITE] * 4, palette2)
make_gif ('3x3_ffffff', 3, 3, [WHITE] * 9, palette2)
make_gif ('10x10_ffffff', 10, 10, [WHITE] * 100, palette2)

make_gif ('2x2_colors', 2, 2, [RED, YELLOW, MAGENTA, WHITE], palette8)

make_gif ('16x16_ff0000', 16, 16, [RED] * 256, palette8)
values = []
colors = []
for i in range (256):
    values.append (i)
    colors.append ('#%02x0000' % i)
make_gif ('16x16_reds', 16, 16, values, colors)

make_gif ('16x16_00ff00', 16, 16, [GREEN] * 256, palette8)
values = []
colors = []
for i in range (256):
    values.append (i)
    colors.append ('#00%02x00' % i)
make_gif ('16x16_greens', 16, 16, values, colors)

make_gif ('16x16_0000ff', 16, 16, [BLUE] * 256, palette8)
values = []
colors = []
for i in range (256):
    values.append (i)
    colors.append ('#0000%02x' % i)
make_gif ('16x16_blues', 16, 16, values, colors)

# Image with additional values
make_gif ('1x1_ff0000_additional_data', 1, 1, [RED] * 100, palette8)
#make_gif ('1x1_additional_data_after_eoi', 1, 1, [RED] * 100, palette8)

# Optional clear and end-of-information codes
make_gif ('1x1_ff0000_no_clear', 1, 1, [RED], palette8, start_with_clear = False)
make_gif ('1x1_ff0000_no_eoi', 1, 1, [RED], palette8, end_with_eoi = False)
# Use 2x1 so the single byte of data contains two codes (6 bits) otherwise the decoder will read a second code due to the lack of EOI
make_gif ('2x1_ff0000_no_clear_and_eoi', 2, 1, [RED, RED], palette8, start_with_clear = False, end_with_eoi = False)

# Maximum sizes
make_gif ('65535x1_ffffff', 65535, 1, [WHITE] * 65535, palette8)
make_gif ('1x65535_ffffff', 1, 65535, [WHITE] * 65535, palette8)

# Uses maximum 4095 codes
import random
values = []
seed = 1
for i in range (300*300):
    m = 2 ** 32
    seed = (1103515245 * seed + 12345) % m
    values.append (seed >> 31)
make_gif ('300x300_noise_4095_codes', 300, 300, values, palette2)

# Comments
make_gif ('1x1_ffffff_comment', 1, 1, [WHITE], palette8, comment = 'Hello World!')
make_gif ('1x1_ffffff_large_comment', 1, 1, [WHITE], palette8, comment = ' '.join (['Hello World!'] * 1000))
make_gif ('1x1_ffffff_nul_comment', 1, 1, [WHITE], palette8, comment = '\0')
make_gif ('1x1_ffffff_invalid_ascii_comment', 1, 1, [WHITE], palette8, comment = '\xff')
make_gif ('1x1_ffffff_invalid_utf8_comment', 1, 1, [WHITE], palette8, comment = '\xc3\x28')

# Loops
make_gif ('1x1_ffffff_loop_infinite', 1, 1, [WHITE], palette8, loop_count = 0)
make_gif ('1x1_ffffff_loop_once', 1, 1, [WHITE], palette8, loop_count = 1)
make_gif ('1x1_ffffff_loop_max', 1, 1, [WHITE], palette8, loop_count = 65535)
make_gif ('1x1_ffffff_loop_buffer', 1, 1, [WHITE], palette8, loop_count = 0, buffer_size = 1024)
make_gif ('1x1_ffffff_loop_buffer_max', 1, 1, [WHITE], palette8, loop_count = 0, buffer_size = 4294967295)
make_gif ('1x1_ffffff_loop_animexts', 1, 1, [WHITE], palette8, extensions = [make_animexts_extension (loop_count = 0, buffer_size = 1024)])
# Netscape extension without loop field
# Netscape extension with multiple loop fields

# Plain Text extension
plain_text_ext = make_plain_text_extension ('Hello', 0, 0, 5, 1, 8, 8, 1, 0)
make_gif ('40x8_plain_text', 40, 8, [0] * 40 * 8, palette8, extensions = [plain_text_ext])

# Unknown extensions
unknown_ext = make_extension (0x2a, [b'Hello', b'World'])
make_gif ('1x1_ffffff_unknown_extension', 1, 1, [WHITE], palette8, extensions = [unknown_ext])
unknown_app_ext = make_application_extension ('UNKNOWN!', 'XXX', [b'Hello', b'World'])
make_gif ('1x1_ffffff_unknown_application_extension', 1, 1, [WHITE], palette8, extensions = [unknown_app_ext])
nul_app_ext = make_application_extension ('\0\0\0\0\0\0\0\0', '\0\0\0', [b'\0\0\0\0', b'\0\0\0\0'])
make_gif ('1x1_ffffff_nul_application_extension', 1, 1, [WHITE], palette8, extensions = [nul_app_ext])

# Trailing data after end
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
