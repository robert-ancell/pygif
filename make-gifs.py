#!/usr/bin/python3

import itertools
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

def make_image (width, height, depth, values, left = 0, top = 0, colors = [], interlace = False, colors_sorted = False, reserved = 0, start_code_size = -1, start_with_clear = True, end_with_eoi = True, max_width = 12, clear_on_max_width = True, extra_data = b''):
    assert (0 <= width <= 65535)
    assert (0 <= height <= 65535)
    assert (0 <= left <= 65535)
    assert (0 <= top <= 65535)
    assert (0 <= reserved <= 3)

    color_table_size = get_color_table_size (colors)
    assert (color_table_size <= 8)

    # Image descriptor
    flags = 0x00
    if color_table_size > 0:
        flags |= 0x80
        flags |= color_table_size - 1
    if interlace:
        flags |= 0x40
    if colors_sorted:
        flags |= 0x20
    flags |= reserved << 3
    data = struct.pack ('<BHHHHB', 0x2C, left, top, width, height, flags)

    # Add optional color table
    data += make_color_table (colors)

    # Compress pixel values using LZW
    if start_code_size == -1:
        start_code_size = depth + 1
        # Spec says code size is minimum three
        if start_code_size < 3:
            start_code_size = 3
    data += make_lzw_data (values, start_code_size, start_with_clear = start_with_clear, end_with_eoi = end_with_eoi, max_width = max_width, clear_on_max_width = clear_on_max_width, extra_data = extra_data)

    return data

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

DISPOSAL_NONE         = 0
DISPOSAL_KEEP         = 1
DISPOSAL_RESTORE_BG   = 2
DISPOSAL_RESTORE_PREV = 3
def make_graphic_control_extension (disposal_method = DISPOSAL_NONE, delay_time = 0, user_input = False, has_transparent = False, transparent_color = 0, reserved = 0):
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

def make_code_table (code_size):
    codes = {}
    for i in range (2 ** (code_size - 1)):
        codes[(i,)] = i
    clear_code = 2 ** (code_size - 1)
    eoi_code = clear_code + 1
    next_code = clear_code + 2
    return (codes, clear_code, eoi_code, next_code)

def lzw_compress (values, start_code_size, start_with_clear = True, end_with_eoi = True, max_width = 12, clear_on_max_width = True):
    assert (start_code_size <= max_width)
    assert (3 <= max_width <= 12)

    code_size = start_code_size
    (codes, clear_code, eoi_code, next_code) = make_code_table (code_size)

    code = tuple ()
    stream = []
    if start_with_clear:
        stream.append ((clear_code, code_size))
    for value in values:
        code += (value,)
        if code in codes:
            continue

        # If there are available bits, then add a new code
        if next_code < 2 ** max_width:
            new_code = next_code
            next_code += 1
            codes[code] = new_code

        stream.append ((codes[code[:-1]], code_size))
        code = code[-1:]

        # Use enough bits to place the next code
        if next_code == 2 ** code_size + 1:
            code_size += 1

        # Clear when out of codes
        if next_code == 2 ** max_width and clear_on_max_width:
            stream.append ((clear_code, code_size))
            code_size = start_code_size
            (codes, clear_code, eoi_code, next_code) = make_code_table (code_size)
    stream.append ((codes[code], code_size))
    if end_with_eoi:
        stream.append ((eoi_code, code_size))
    return stream

def make_lzw_data (values, start_code_size, start_with_clear = True, end_with_eoi = True, max_width = 12, clear_on_max_width = True, extra_data = b''):
    codes = lzw_compress (values, start_code_size, start_with_clear, end_with_eoi, max_width, clear_on_max_width)

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

    # Add any extra data to the end
    if len (extra_data) > 0:
        last_block = blocks[-1]
        n_available = 255 - len (last_block)
        if n_available > 0:
            last_block += extra_data[:n_available]
            extra_data = extra_data[n_available:]
            blocks[-1] = last_block
        while len (extra_data) > 0:
            blocks.append (extra_data[:255])
            extra_data = extra_data[255:]

    # Terminate with an empty block
    blocks.append (b'')

    # Write blocks with block headers
    for b in blocks:
        data += struct.pack ('B', len (b)) + b

    return data

def make_trailer ():
    return b'\x3b'

test_count = 0
def make_gif (name, result, width, height, colors, images, background_color = 0, comment = '', loop_count = -1, buffer_size = -1, extensions = []):
    global test_count
    data = make_header (width, height, colors, background_color = background_color)
    if loop_count >= 0:
        data += make_netscape_extension (loop_count, buffer_size)
    if comment != '':
        data += make_comment_extension (comment)
    for extension in extensions:
        data += extension
    for image in images:
        data += image
    data += make_trailer ()

    filename = 'test-images/%03d_%s_%s.gif' % (test_count, name, result)
    open (filename, 'wb').write (data)
    test_count += 1

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
        v = (i * 255 // (n_colors - 1))
        colors.append ('#%02x%02x%02x' % (v, v, v))
    return colors
grays1 = make_grayscale_palette (1)
grays2 = make_grayscale_palette (2)
grays3 = make_grayscale_palette (3)
grays4 = make_grayscale_palette (4)
grays5 = make_grayscale_palette (5)
grays6 = make_grayscale_palette (6)
grays7 = make_grayscale_palette (7)
grays8 = make_grayscale_palette (8)

def single_image (width, height, depth, color):
    return [make_image (width, height, depth, [color] * (width * height))]

def dot_image (depth, color):
    return single_image (1, 1, depth, color)

# Single pixel image
make_gif ('dot', 'color-dot', 1, 1, ['#000000', '#aabbcc'], dot_image (1, 1))

# All possible color depths
make_gif ('depth1', 'white-dot', 1, 1, grays1, dot_image (1, 1))
make_gif ('depth2', 'white-dot', 1, 1, grays2, dot_image (2, 3))
make_gif ('depth3', 'white-dot', 1, 1, grays3, dot_image (3, 7))
make_gif ('depth4', 'white-dot', 1, 1, grays4, dot_image (4, 15))
make_gif ('depth5', 'white-dot', 1, 1, grays5, dot_image (5, 31))
make_gif ('depth6', 'white-dot', 1, 1, grays6, dot_image (6, 63))
make_gif ('depth7', 'white-dot', 1, 1, grays7, dot_image (7, 127))
make_gif ('depth8', 'white-dot', 1, 1, grays8, dot_image (8, 255))

# Image with different colours in each pixel
make_gif ('four-colors', 'four-colors', 2, 2, palette8, [make_image (2, 2, 8, [RED, GREEN, BLUE, WHITE])])

# Local color table overrides global one
make_gif ('local-color-table', 'white-dot', 1, 1, ['#ff0000', '#00ff00'], [make_image (1, 1, 1, [1], colors = ['#0000ff', '#ffffff'])])

# Global color table not needed if have local one
make_gif ('no-global-color-table', 'white-dot', 1, 1, [], [make_image (1, 1, 1, [1], colors = ['#0000ff', '#ffffff'])])

# Image with no data (just shows background)
make_gif ('no-data', 'white-dot', 1, 1, palette2, [], background_color = WHITE)

# Image with invalid background value
make_gif ('invalid-background', 'white-dot', 1, 1, palette2, dot_image (2, WHITE), background_color = 255)

# Test all color bits work
values = []
colors = []
for i in range (256):
    values.append (i)
    colors.append ('#%02x0000' % i)
make_gif ('all-reds', 'all-reds', 16, 16, colors, [make_image (16, 16, 8, values)])
values = []
colors = []
for i in range (256):
    values.append (i)
    colors.append ('#00%02x00' % i)
make_gif ('all-greens', 'all-greens', 16, 16, colors, [make_image (16, 16, 8, values)])
values = []
colors = []
for i in range (256):
    values.append (i)
    colors.append ('#0000%02x' % i)
make_gif ('all-blues', 'all-blues', 16, 16, colors, [make_image (16, 16, 8, values)])

# Interlaced image
colors = []
for i in range (256):
    colors.append ('#%02x0000' % i)
values = []
def interlace_rows (height):
    return itertools.chain (range (0, 16, 8), range (4, 16, 8), range (2, 16, 4), range (1, 16, 2))
for row in interlace_rows (16):
    for col in range (16):
        values.append (row * 16 + col)
make_gif ('interlace', 'all-reds', 16, 16, colors, [make_image (16, 16, 8, values, interlace = True)])

# Images that don't fully cover the background
make_gif ('image-inside-bg', 'image-indside-bg', 3, 3, palette8, [make_image (1, 1, 3, [RED], left = 1, top = 1)], background_color = WHITE)
make_gif ('image-overlap-bg', 'image-overlap-bg', 2, 2, palette8, [make_image (2, 2, 3, [RED] * 4, left = 1, top = 1)], background_color = WHITE)
make_gif ('image-outside-bg', 'image-outside-bg', 2, 2, palette8, [make_image (2, 2, 3, [RED] * 4, left = 2, top = 2)], background_color = WHITE)

# Multiple images in different places
make_gif ('images-combine', 'four-colors', 2, 2, palette8,
          [make_image (1, 1, 3, [RED],   left = 0, top = 0),
           make_image (1, 1, 3, [GREEN], left = 1, top = 0),
           make_image (1, 1, 3, [BLUE],  left = 0, top = 1),
           make_image (1, 1, 3, [WHITE], left = 1, top = 1)], background_color = WHITE)

# Multiple images overlapping
make_gif ('images-overlap', 'white-dot', 1, 1, palette8, [make_image (1, 1, 3, [RED]),
                                                          make_image (1, 1, 3, [WHITE])])

# Image with additional values
make_gif ('additional-data', 'white-dot', 1, 1, palette8, single_image (10, 10, 3, WHITE))
#make_gif ('additional-data-after-eoi', 'white-dot', 1, 1, single_image (10, 10, 3, WHITE), palette8)

# Addtional data after end-of-information
make_gif ('extra-data', 'white-dot', 1, 1, palette8, [make_image (1, 1, 3, [WHITE], extra_data = b'HIDDEN MESSAGES')])

# Optional clear and end-of-information codes
make_gif ('no-clear', 'white-dot', 1, 1, palette8, [make_image (1, 1, 3, [WHITE], start_with_clear = False)])
make_gif ('no-eoi', 'white-dot', 1, 1, palette8, [make_image (1, 1, 3, [WHITE], end_with_eoi = False)])
# Use 2x1 so the single byte of data contains two codes (6 bits) otherwise the decoder will read a second code due to the lack of EOI
make_gif ('no-clear-and-eoi', 'white-hline2', 2, 1, palette8, [make_image (2, 1, 3, [WHITE, WHITE], start_with_clear = False, end_with_eoi = False)])

# Maximum sizes
make_gif ('max-width', 'max-width', 65535, 1, palette8, single_image (65535, 1, 3, WHITE))
make_gif ('max-height', 'max-height', 1, 65535, palette8, single_image (1, 65535, 3, WHITE))
make_gif ('max-size', 'nocrash', 65535, 65535, palette8, [])

import random
values = []
seed = 1
for i in range (300*300):
    m = 2 ** 32
    seed = (1103515245 * seed + 12345) % m
    values.append (seed >> 31)

# Clear code when hit 12 bit limit
make_gif ('4095-codes-clear', '4095-codes', 300, 300, palette2, [make_image (300, 300, 1, values)])

# Stop adding code words when hit code 12 bit limit
make_gif ('4095-codes', '4095-codes', 300, 300, palette2, [make_image (300, 300, 1, values, clear_on_max_width = False)])

# Have lots of clears by having a small code bit limit
make_gif ('255-codes', '4095-codes', 300, 300, palette2, [make_image (300, 300, 1, values, max_width = 8)])

# Use a minimum code size
make_gif ('large-codes', '4095-codes', 300, 300, palette2, [make_image (300, 300, 1, values, start_code_size = 8)])
make_gif ('max-codes', '4095-codes', 300, 300, palette2, [make_image (300, 300, 1, values, start_code_size = 12)])

# Transparent image
make_gif ('transparent', 'four-colors-transparent', 2, 2, palette8,
          [ make_graphic_control_extension (has_transparent = True, transparent_color = RED),
            make_image (2, 2, 3, [RED, GREEN, BLUE, WHITE]) ])

# Invalid transparency color
make_gif ('invalid-transparent', 'four-colors', 2, 2, palette8,
          [ make_graphic_control_extension (has_transparent = True, transparent_color = 255),
            make_image (2, 2, 3, [RED, GREEN, BLUE, WHITE]) ])

# Transparency color set but transparency disabled
make_gif ('disabled-transparent', 'four-colors', 2, 2, palette8,
          [ make_graphic_control_extension (has_transparent = False, transparent_color = RED),
            make_image (2, 2, 3, [RED, GREEN, BLUE, WHITE]) ])

# Loops
make_gif ('loop-infinite', 'white-dot', 1, 1, palette8, dot_image (3, WHITE), loop_count = 0)
make_gif ('loop-once', 'white-dot', 1, 1, palette8, dot_image (3, WHITE), loop_count = 1)
make_gif ('loop-max', 'white-dot', 1, 1, palette8, dot_image (3, WHITE), loop_count = 65535)
make_gif ('loop-buffer', 'white-dot', 1, 1, palette8, dot_image (3, WHITE), loop_count = 0, buffer_size = 1024)
make_gif ('loop-buffer_max', 'white-dot', 1, 1, palette8, dot_image (3, WHITE), loop_count = 0, buffer_size = 4294967295)
make_gif ('loop-animexts', 'white-dot', 1, 1, palette8, dot_image (3, WHITE), extensions = [make_animexts_extension (loop_count = 0, buffer_size = 1024)])

# FIXME: NETSCAPE extension without loop field

# FIXME: NETSCAPE with multiple loop fields

# Animated image
make_gif ('animation', 'animation', 2, 2, palette2,
          [ make_graphic_control_extension (delay_time = 50),
            make_image (2, 2, 1, [WHITE, BLACK, BLACK, BLACK]),
            make_graphic_control_extension (delay_time = 50),
            make_image (2, 2, 1, [BLACK, WHITE, BLACK, BLACK]),
            make_graphic_control_extension (delay_time = 50),
            make_image (2, 2, 1, [BLACK, BLACK, BLACK, WHITE]),
            make_graphic_control_extension (delay_time = 50),
            make_image (2, 2, 1, [BLACK, BLACK, WHITE, BLACK]) ],
          loop_count = 0)

# Animation with variable frame speed
make_gif ('animation-speed', 'animation', 2, 2, palette2,
          [ make_graphic_control_extension (delay_time = 25),
            make_image (2, 2, 1, [WHITE, BLACK, BLACK, BLACK]),
            make_graphic_control_extension (delay_time = 50),
            make_image (2, 2, 1, [BLACK, WHITE, BLACK, BLACK]),
            make_graphic_control_extension (delay_time = 100),
            make_image (2, 2, 1, [BLACK, BLACK, BLACK, WHITE]),
            make_graphic_control_extension (delay_time = 200),
            make_image (2, 2, 1, [BLACK, BLACK, WHITE, BLACK]) ],
          loop_count = 0)

# Animated image with subimages
# NOTE: RESTORE_BG appears to be interpreted as transparency
make_gif ('animation-subimage', 'animation', 2, 2, palette2,
          [ make_graphic_control_extension (DISPOSAL_RESTORE_BG, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 0, 0),
            make_graphic_control_extension (DISPOSAL_RESTORE_BG, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 1, 0),
            make_graphic_control_extension (DISPOSAL_RESTORE_BG, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 1, 1,),
            make_graphic_control_extension (DISPOSAL_RESTORE_BG, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 0, 1) ],
          loop_count = 0)

# Background with animated subimages that add together
make_gif ('animation-subimage-add', 'animation-fill', 2, 2, palette2,
          [ make_graphic_control_extension (DISPOSAL_KEEP, delay_time = 50),
            make_image (2, 2, 1, [WHITE, BLACK, BLACK, BLACK]),
            make_graphic_control_extension (DISPOSAL_KEEP, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 1, 0),
            make_graphic_control_extension (DISPOSAL_KEEP, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 1, 1,),
            make_graphic_control_extension (DISPOSAL_KEEP, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 0, 1) ],
          loop_count = 0)

# Background with animated subimages that move over initial background
make_gif ('animation-subimage-move', 'animation', 2, 2, palette2,
          [ make_image (2, 2, 1, [BLACK, BLACK, BLACK, BLACK]),
            make_graphic_control_extension (DISPOSAL_RESTORE_PREV, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 0, 0),
            make_graphic_control_extension (DISPOSAL_RESTORE_PREV, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 1, 0),
            make_graphic_control_extension (DISPOSAL_RESTORE_PREV, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 1, 1,),
            make_graphic_control_extension (DISPOSAL_RESTORE_PREV, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 0, 1) ],
          loop_count = 0)

# Animation with multiple images per frame
# NOTE: Everyone seems to be doing this wrong...
make_gif ('animation-multi-image', 'animation', 2, 1, palette4,
          [ make_image (2, 1, 2, [BLACK, RED]),
            make_graphic_control_extension (delay_time = 50),
            make_image (2, 1, 2, [BLACK, WHITE]),
            make_image (2, 1, 2, [RED,   BLACK]),
            make_graphic_control_extension (delay_time = 50),
            make_image (2, 1, 2, [WHITE, BLACK]) ],
          loop_count = 0)

# FIXME: Animation with explicit delay times of zero

# FIXME: Animation without fixed first frame (everyone seems to be assuming transparent background)

# Comments
make_gif ('comment', 'white-dot', 1, 1, palette8, dot_image (3, WHITE), comment = 'Hello World!')
make_gif ('large-comment', 'white-dot', 1, 1, palette8, dot_image (3, WHITE), comment = ' '.join (['Hello World!'] * 1000))
make_gif ('nul-comment', 'white-dot', 1, 1, palette8, dot_image (3, WHITE), comment = '\0')
make_gif ('invalid-ascii-comment', 'white-dot', 1, 1, palette8, dot_image (3, WHITE), comment = '\xff')
make_gif ('invalid-utf8-comment', 'white-dot', 1, 1, palette8, dot_image (3, WHITE), comment = '\xc3\x28')

# Plain Text extension
plain_text_ext = make_plain_text_extension ('Hello', 0, 0, 5, 1, 8, 8, 1, 0)
make_gif ('plain-text', 'nocrash', 40, 8, palette8, single_image (40, 8, 3, BLACK), extensions = [plain_text_ext])

# Unknown extensions
unknown_ext = make_extension (0x2a, [b'Hello', b'World'])
make_gif ('unknown-extension', 'white-dot', 1, 1, palette8, dot_image (3, WHITE), extensions = [unknown_ext])
unknown_app_ext = make_application_extension ('UNKNOWN!', 'XXX', [b'Hello', b'World'])
make_gif ('unknown-application-extension', 'white-dot', 1, 1, palette8, dot_image (3, WHITE), extensions = [unknown_app_ext])
nul_app_ext = make_application_extension ('\0\0\0\0\0\0\0\0', '\0\0\0', [b'\0\0\0\0', b'\0\0\0\0'])
make_gif ('nul-application-extension', 'white-dot', 1, 1, palette8, dot_image (3, WHITE), extensions = [nul_app_ext])

# FIXME: Multiple clears in a row

# Regenerate the sample image from http://giflib.sourceforge.net/whatsinagif/
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
image = make_image (10, 10, 2, values)
open ('sample_1.gif', 'wb').write (header + gce + image + make_trailer ())
