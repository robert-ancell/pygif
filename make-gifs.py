#!/usr/bin/python3

import gif
import io
import itertools
import math
import struct

def make_image (width, height, depth, values, left = 0, top = 0, colors = [], interlace = False, start_code_size = -1, start_with_clear = True, end_with_eoi = True, max_width = 12, clear_on_max_width = True, extra_data = b''):
    assert (0 <= width <= 65535)
    assert (0 <= height <= 65535)
    assert (0 <= left <= 65535)
    assert (0 <= top <= 65535)

    has_color_table = len (colors) > 0
    color_table_size = get_depth (colors)
    assert (color_table_size <= 8)

    buffer = io.BytesIO ()
    writer = gif.Writer (buffer)
    writer.write_image_descriptor (left, top, width, height, has_color_table = has_color_table, depth = color_table_size, interlace = interlace)
    if has_color_table:
        for color in colors:
            (red, green, blue) = parse_color (color)
            writer.write_color (red, green, blue)
        for i in range (len (colors), 2 ** color_table_size):
            writer.write_color (0, 0, 0)
    data = buffer.getvalue ()

    # Use a default code size big enough to fit all pixel values (min 2 according to spec)
    if start_code_size == -1:
        start_code_size = depth
    buffer = io.BytesIO ()
    encoder = gif.LZWEncoder (buffer, start_code_size, max_width, start_with_clear, clear_on_max_width)
    encoder.feed (values)
    encoder.finish (end_with_eoi, extra_data)
    data += buffer.getvalue ()

    return data

def get_depth (colors):
    n_colors = len (colors)
    if n_colors == 0:
        return 1
    else:
        return max (math.ceil (math.log2 (n_colors)), 1)

def parse_color (color):
    assert (len (color) == 7)
    assert (color[0] == '#')
    return (int (color[1:3], 16), int (color[3:5], 16), int (color[5:7], 16))

def parse_colors (colors):
    result = []
    for color in colors:
        result.append (parse_color (color))
    return result

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

def make_trailer ():
    return b'\x3b'

test_count = 0
def make_gif (name, result, width, height, colors, blocks, background_color = 0):
    global test_count

    filename = 'test-images/%03d_%s_%s.gif' % (test_count, name, result)
    writer = gif.Writer (open (filename, 'wb'))

    has_color_table = len (colors) > 0
    depth = get_depth (colors)
    assert (1 <= depth <= 8)

    writer.write_header ()
    writer.write_screen_descriptor (width, height, depth = depth, has_color_table = has_color_table, background_color = background_color)
    if has_color_table:
        for color in colors:
            (red, green, blue) = parse_color (color)
            writer.write_color (red, green, blue)
        for i in range (len (colors), 2 ** depth):
            writer.write_color (0, 0, 0)
    for block in blocks:
        writer.file.write (block)
    writer.write_trailer ()
    test_count += 1

def make_gif2 (name, result, width, height, colors, background_color = 0):
    global test_count

    filename = 'test-images/%03d_%s_%s.gif' % (test_count, name, result)
    writer = gif.Writer (open (filename, 'wb'))
    writer.write_headers (width, height, colors, background_color = background_color)

    test_count += 1

    return writer

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
        colors.append ((v, v, v))
    return colors

def filled_image (width, height, depth, color):
    return make_image (width, height, depth, [color] * (width * height))

# Single pixel, all possible color depths
for depth in range (1, 9):
    palette = make_grayscale_palette (depth)
    writer = make_gif2 ('depth%d' % depth, 'white-dot', 1, 1, palette)
    writer.write_image (1, 1, depth, [ 2 ** depth - 1 ])
    writer.write_trailer ()

# Image with different colours in each pixel
make_gif ('four-colors', 'four-colors', 2, 2, palette8, [make_image (2, 2, 8, [RED, GREEN, BLUE, WHITE])])

# Local color table overrides global one
make_gif ('local-color-table', 'white-dot', 1, 1, ['#ff0000', '#00ff00'], [make_image (1, 1, 1, [1], colors = ['#0000ff', '#ffffff'])])

# Global color table not needed if have local one
make_gif ('no-global-color-table', 'white-dot', 1, 1, [], [make_image (1, 1, 1, [1], colors = ['#0000ff', '#ffffff'])])

# Image with no data (just shows background)
make_gif ('no-data', 'white-dot', 1, 1, palette2, [], background_color = WHITE)

# Image with invalid background value
make_gif ('invalid-background', 'white-dot', 1, 1, palette2,
          [ make_image (1, 1, 2, [ WHITE ]) ],
          background_color = 255)

# Test all color bits work
pixels = []
colors = []
for i in range (256):
    pixels.append (i)
    colors.append ('#%02x0000' % i)
make_gif ('all-reds', 'all-reds', 16, 16, colors, [make_image (16, 16, 8, pixels)])
pixels = []
colors = []
for i in range (256):
    pixels.append (i)
    colors.append ('#00%02x00' % i)
make_gif ('all-greens', 'all-greens', 16, 16, colors, [make_image (16, 16, 8, pixels)])
pixels = []
colors = []
for i in range (256):
    pixels.append (i)
    colors.append ('#0000%02x' % i)
make_gif ('all-blues', 'all-blues', 16, 16, colors, [make_image (16, 16, 8, pixels)])

# Interlaced image
colors = []
for i in range (256):
    colors.append ('#%02x0000' % i)
pixels = []
def interlace_rows (height):
    return itertools.chain (range (0, 16, 8), range (4, 16, 8), range (2, 16, 4), range (1, 16, 2))
for row in interlace_rows (16):
    for col in range (16):
        pixels.append (row * 16 + col)
make_gif ('interlace', 'all-reds', 16, 16, colors, [make_image (16, 16, 8, pixels, interlace = True)])

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

# Image with additional pixels
make_gif ('additional-data', 'white-dot', 1, 1, palette8, [ filled_image (10, 10, 3, WHITE) ])
#make_gif ('additional-data-after-eoi', 'white-dot', 1, 1, [ filled_image (10, 10, 3, WHITE) ], palette8)

# Addtional data after end-of-information
make_gif ('extra-data', 'white-dot', 1, 1, palette8, [make_image (1, 1, 3, [WHITE], extra_data = b'HIDDEN MESSAGES')])

# Optional clear and end-of-information codes
make_gif ('no-clear', 'white-dot', 1, 1, palette8, [make_image (1, 1, 3, [WHITE], start_with_clear = False)])
make_gif ('no-eoi', 'white-dot', 1, 1, palette8, [make_image (1, 1, 3, [WHITE], end_with_eoi = False)])
# Use 2x1 so the single byte of data contains two codes (6 bits) otherwise the decoder will read a second code due to the lack of EOI
make_gif ('no-clear-and-eoi', 'white-hline2', 2, 1, palette8, [make_image (2, 1, 3, [WHITE, WHITE], start_with_clear = False, end_with_eoi = False)])

# Maximum sizes
make_gif ('max-width', 'max-width', 65535, 1, palette8, [ filled_image (65535, 1, 3, WHITE) ])
make_gif ('max-height', 'max-height', 1, 65535, palette8, [ filled_image (1, 65535, 3, WHITE) ])
make_gif ('max-size', 'nocrash', 65535, 65535, palette8, [])

# Generate a random image to test LZW compression
random_width = 100
random_height = 100
values = []
seed = 1
for i in range (random_width*random_height):
    m = 2 ** 32
    seed = (1103515245 * seed + 12345) % m
    values.append (math.floor (16 * seed / m))
    assert (values[-1] < 16)

# Clear code when hit 12 bit limit
make_gif ('4095-codes-clear', '4095-codes', random_width, random_height, palette16, [make_image (random_width, random_height, 4, values)])

# Stop adding code words when hit code 12 bit limit
make_gif ('4095-codes', '4095-codes', random_width, random_height, palette16, [make_image (random_width, random_height, 4, values, clear_on_max_width = False)])

# Have lots of clears by having a small code bit limit
make_gif ('255-codes', '4095-codes', random_width, random_height, palette16, [make_image (random_width, random_height, 4, values, max_width = 8)])

# Use a minimum code size
make_gif ('large-codes', '4095-codes', random_width, random_height, palette16, [make_image (random_width, random_height, 4, values, start_code_size = 7)])
make_gif ('max-codes', '4095-codes', random_width, random_height, palette16, [make_image (random_width, random_height, 4, values, start_code_size = 11)])

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
make_gif ('loop-infinite', 'white-dot', 1, 1, palette8,
          [ make_netscape_extension (loop_count = 0),
            make_image (1, 1, 3, [ WHITE ]) ])
make_gif ('loop-once', 'white-dot', 1, 1, palette8,
          [ make_netscape_extension (loop_count = 1),
            make_image (1, 1, 3, [ WHITE ]) ])
make_gif ('loop-max', 'white-dot', 1, 1, palette8,
          [ make_netscape_extension (loop_count = 65535),
            make_image (1, 1, 3, [ WHITE ]) ])
make_gif ('loop-buffer', 'white-dot', 1, 1, palette8,
          [ make_netscape_extension (loop_count = 0, buffer_size = 1024),
            make_image (1, 1, 3, [ WHITE ]) ])
make_gif ('loop-buffer_max', 'white-dot', 1, 1, palette8,
          [ make_netscape_extension (loop_count = 0, buffer_size = 4294967295),
            make_image (1, 1, 3, [ WHITE ]) ])
make_gif ('loop-animexts', 'white-dot', 1, 1, palette8,
          [ make_animexts_extension (loop_count = 0, buffer_size = 1024),
            make_image (1, 1, 3, [ WHITE ]) ])

# FIXME: NETSCAPE extension without loop field

# FIXME: NETSCAPE with multiple loop fields

# Animated image
make_gif ('animation', 'animation', 2, 2, palette2,
          [ make_netscape_extension (loop_count = 0),
            make_graphic_control_extension (delay_time = 50),
            make_image (2, 2, 1, [WHITE, BLACK, BLACK, BLACK]),
            make_graphic_control_extension (delay_time = 50),
            make_image (2, 2, 1, [BLACK, WHITE, BLACK, BLACK]),
            make_graphic_control_extension (delay_time = 50),
            make_image (2, 2, 1, [BLACK, BLACK, BLACK, WHITE]),
            make_graphic_control_extension (delay_time = 50),
            make_image (2, 2, 1, [BLACK, BLACK, WHITE, BLACK]) ])

# Animation with variable frame speed
make_gif ('animation-speed', 'animation', 2, 2, palette2,
          [ make_netscape_extension (loop_count = 0),
            make_graphic_control_extension (delay_time = 25),
            make_image (2, 2, 1, [WHITE, BLACK, BLACK, BLACK]),
            make_graphic_control_extension (delay_time = 50),
            make_image (2, 2, 1, [BLACK, WHITE, BLACK, BLACK]),
            make_graphic_control_extension (delay_time = 100),
            make_image (2, 2, 1, [BLACK, BLACK, BLACK, WHITE]),
            make_graphic_control_extension (delay_time = 200),
            make_image (2, 2, 1, [BLACK, BLACK, WHITE, BLACK]) ])

# Animated image with subimages
# NOTE: RESTORE_BG appears to be interpreted as transparency
make_gif ('animation-subimage', 'animation', 2, 2, palette2,
          [ make_netscape_extension (loop_count = 0),
            make_graphic_control_extension (DISPOSAL_RESTORE_BG, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 0, 0),
            make_graphic_control_extension (DISPOSAL_RESTORE_BG, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 1, 0),
            make_graphic_control_extension (DISPOSAL_RESTORE_BG, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 1, 1,),
            make_graphic_control_extension (DISPOSAL_RESTORE_BG, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 0, 1) ])

# Background with animated subimages that add together
make_gif ('animation-subimage-add', 'animation-fill', 2, 2, palette2,
          [ make_netscape_extension (loop_count = 0),
            make_graphic_control_extension (DISPOSAL_KEEP, delay_time = 50),
            make_image (2, 2, 1, [WHITE, BLACK, BLACK, BLACK]),
            make_graphic_control_extension (DISPOSAL_KEEP, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 1, 0),
            make_graphic_control_extension (DISPOSAL_KEEP, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 1, 1,),
            make_graphic_control_extension (DISPOSAL_KEEP, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 0, 1) ])

# Background with animated subimages that move over initial background
make_gif ('animation-subimage-move', 'animation', 2, 2, palette2,
          [ make_netscape_extension (loop_count = 0),
            make_image (2, 2, 1, [BLACK, BLACK, BLACK, BLACK]),
            make_graphic_control_extension (DISPOSAL_RESTORE_PREV, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 0, 0),
            make_graphic_control_extension (DISPOSAL_RESTORE_PREV, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 1, 0),
            make_graphic_control_extension (DISPOSAL_RESTORE_PREV, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 1, 1,),
            make_graphic_control_extension (DISPOSAL_RESTORE_PREV, delay_time = 50),
            make_image (1, 1, 1, [WHITE], 0, 1) ])

# FIXME: Test restore only applies to area drawn on

# Animation with multiple images per frame
# NOTE: Everyone seems to be doing this wrong...
make_gif ('animation-multi-image', 'animation', 2, 1, palette4,
          [ make_netscape_extension (loop_count = 0),
            make_image (2, 1, 2, [BLACK, RED]),
            make_graphic_control_extension (delay_time = 50),
            make_image (2, 1, 2, [BLACK, WHITE]),
            make_image (2, 1, 2, [RED,   BLACK]),
            make_graphic_control_extension (delay_time = 50),
            make_image (2, 1, 2, [WHITE, BLACK]) ])

# FIXME: Animation with explicit delay times of zero

# FIXME: Animation without fixed first frame (everyone seems to be assuming transparent background)

# Comments
make_gif ('comment', 'white-dot', 1, 1, palette8,
          [ make_comment_extension ('Hello World!'),
            make_image (1, 1, 3, [ WHITE ]) ])
make_gif ('large-comment', 'white-dot', 1, 1, palette8,
          [ make_comment_extension (' '.join (['Hello World!'] * 1000)),
            make_image (1, 1, 3, [ WHITE ]) ])
make_gif ('nul-comment', 'white-dot', 1, 1, palette8,
          [ make_comment_extension ('\0'),
            make_image (1, 1, 3, [ WHITE ]) ])
make_gif ('invalid-ascii-comment', 'white-dot', 1, 1, palette8,
          [ make_comment_extension ('\xff'),
            make_image (1, 1, 3, [ WHITE ]) ])
make_gif ('invalid-utf8-comment', 'white-dot', 1, 1, palette8,
          [ make_comment_extension ('\xc3\x28'),
            make_image (1, 1, 3, [ WHITE ]) ])

# Plain Text extension
make_gif ('plain-text', 'nocrash', 40, 8, palette8,
          [ make_plain_text_extension ('Hello', 0, 0, 5, 1, 8, 8, 1, 0),
            filled_image (40, 8, 3, BLACK) ])

# Unknown extensions
make_gif ('unknown-extension', 'white-dot', 1, 1, palette8,
          [ make_extension (0x2a, [b'Hello', b'World']),
            make_image (1, 1, 3, [ WHITE ]) ])
make_gif ('unknown-application-extension', 'white-dot', 1, 1, palette8,
          [ make_application_extension ('UNKNOWN!', 'XXX', [b'Hello', b'World']),
            make_image (1, 1, 3, [ WHITE ]) ])
make_gif ('nul-application-extension', 'white-dot', 1, 1, palette8,
          [ make_application_extension ('\0\0\0\0\0\0\0\0', '\0\0\0', [b'\0\0\0\0', b'\0\0\0\0']),
            make_image (1, 1, 3, [ WHITE ]) ])

# FIXME: Multiple clears in a row

# FIXME: XMP data

# FIXME: ICC profile
