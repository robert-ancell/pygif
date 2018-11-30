#!/usr/bin/python3

import configparser
import gif
import itertools
import math

def make_gif (name, result, width, height, colors = [], background_color = 0, version = gif.Version.GIF89a, loop_count = 0, buffer_size = 0, comment = '', xmp_files = []):
    # Add to list of tests
    test_list = open ('test-suite/TESTS').readlines ()
    line = name + '\n'
    if not line in test_list:
        test_list.append (line)
        open ('test-suite/TESTS', 'w').writelines (test_list)

    # Write test description
    config = configparser.ConfigParser ()
    def yes_no (value):
        if value:
            return 'yes'
        else:
            return 'no'
    config['config'] = { 'input': '%s.gif' % name }
    config['config']['version'] = version.decode ('ascii')
    if loop_count < 0:
        config['config']['loop-count'] = 'infinite'
    else:
        config['config']['loop-count'] = '%d' % loop_count
    config['config']['buffer-size'] = '%d' % buffer_size
    config['config']['comment'] = repr (comment)
    config['config']['xmp-data'] = ','.join (xmp_files)
    if isinstance (result, list):
        frames = []
        for (i, (image, delay)) in enumerate (result):
            id = 'frame%d' % i
            frames.append (id)
            config[id] = { 'image': '%s.png' % image }
            if delay > 0:
                config[id]['delay'] = '%d' % delay
        config['config']['frames'] = ','.join (frames)
    else:
        config['config']['frames'] = 'frame0'
        config['frame0'] = { 'image': '%s.png' % result }
    file = open ('test-suite/%s.conf' % name, 'w')
    file.write ('# Automatically generated, do not edit!\n')
    config.write (file)

    # Write test GIF
    filename = 'test-suite/%s.gif' % name
    writer = gif.Writer (open (filename, 'wb'))
    writer.write_header (version)
    if len (colors) > 0:
        depth = math.ceil (math.log2 (len (colors)))
        writer.write_screen_descriptor (width, height, has_color_table = True, depth = depth, background_color = background_color)
        writer.write_color_table (colors, depth)
    else:
        writer.write_screen_descriptor (width, height, background_color = background_color)

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
palette16 =  [ (0x00, 0x00, 0x00), (0xff, 0xff, 0xff),
               (0xff, 0x00, 0x00), (0x00, 0xff, 0x00),
               (0x00, 0x00, 0xff), (0x00, 0xff, 0xff), (0xff, 0x00, 0xff), (0xff, 0xff, 0x00),
               (0x55, 0x55, 0x55), (0xaa, 0xaa, 0xaa), (0x80, 0x00, 0x00), (0x00, 0x80, 0x00), (0x00, 0x00, 0x80), (0x00, 0x80, 0x80), (0x80, 0x00, 0x80), (0x80, 0x80, 0x00)]
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

def filled_pixels (width, height, color):
    return [color] * (width * height)

# Single pixel, all possible color depths
for depth in range (1, 9):
    palette = make_grayscale_palette (depth)
    writer = make_gif ('depth%d' % depth, 'white-dot', 1, 1, palette)
    writer.write_image (1, 1, depth, [ 2 ** depth - 1 ])
    writer.write_trailer ()

# Image with different colours in each pixel
writer = make_gif ('four-colors', 'four-colors', 2, 2, palette8)
writer.write_image (2, 2, 8, [RED, GREEN, BLUE, WHITE])
writer.write_trailer ()

# Local color table overrides global one
writer = make_gif ('local-color-table', 'white-dot', 1, 1, [(0xff, 0x00, 0x00), (0x00, 0xff, 0x00)])
writer.write_image (1, 1, 1, [1], colors = [(0x00, 0x00, 0xff), (0xff, 0xff, 0xff)])
writer.write_trailer ()

# Global color table not needed if have local one
writer = make_gif ('no-global-color-table', 'white-dot', 1, 1)
writer.write_image (1, 1, 1, [1], colors = [(0x00, 0x00, 0xff), (0xff, 0xff, 0xff)])
writer.write_trailer ()

# Image with no data (just shows background)
writer = make_gif ('no-data', 'white-dot', 1, 1, palette2, background_color = WHITE)
writer.write_trailer ()

# Image with invalid background value
writer = make_gif ('invalid-background', 'white-dot', 1, 1, palette2, background_color = 255)
writer.write_image (1, 1, 2, [ WHITE ])
writer.write_trailer ()

# Test all color bits work
pixels = []
colors = []
for i in range (256):
    pixels.append (i)
    colors.append ((i, 0, 0))
writer = make_gif ('all-reds', 'all-reds', 16, 16, colors)
writer.write_image (16, 16, 8, pixels)
writer.write_trailer ()
pixels = []
colors = []
for i in range (256):
    pixels.append (i)
    colors.append ((0, i, 0))
writer = make_gif ('all-greens', 'all-greens', 16, 16, colors)
writer.write_image (16, 16, 8, pixels)
writer.write_trailer ()
pixels = []
colors = []
for i in range (256):
    pixels.append (i)
    colors.append ((0, 0, i))
writer = make_gif ('all-blues', 'all-blues', 16, 16, colors)
writer.write_image (16, 16, 8, pixels)
writer.write_trailer ()

# Interlaced image
colors = []
for i in range (256):
    colors.append ((i, 0, 0))
pixels = []
def interlace_rows (height):
    return itertools.chain (range (0, 16, 8), range (4, 16, 8), range (2, 16, 4), range (1, 16, 2))
for row in interlace_rows (16):
    for col in range (16):
        pixels.append (row * 16 + col)
writer = make_gif ('interlace', 'all-reds', 16, 16, colors)
writer.write_image (16, 16, 8, pixels, interlace = True)
writer.write_trailer ()

# Images that don't fully cover the background
writer = make_gif ('image-inside-bg', 'image-indside-bg', 3, 3, palette8, background_color = WHITE)
writer.write_image (1, 1, 3, [ RED ], left = 1, top = 1)
writer.write_trailer ()
writer = make_gif ('image-overlap-bg', 'image-overlap-bg', 2, 2, palette8, background_color = WHITE)
writer.write_image (2, 2, 3, [ RED ] * 4, left = 1, top = 1)
writer.write_trailer ()
writer = make_gif ('image-outside-bg', 'image-outside-bg', 2, 2, palette8, background_color = WHITE)
writer.write_image (2, 2, 3, [ RED ] * 4, left = 2, top = 2)
writer.write_trailer ()

# Multiple images in different places
writer = make_gif ('images-combine', 'four-colors', 2, 2, palette8, background_color = WHITE)
writer.write_image (1, 1, 3, [ RED ],   left = 0, top = 0)
writer.write_image (1, 1, 3, [ GREEN ], left = 1, top = 0)
writer.write_image (1, 1, 3, [ BLUE ],  left = 0, top = 1)
writer.write_image (1, 1, 3, [ WHITE ], left = 1, top = 1)
writer.write_trailer ()

# Multiple images overlapping
writer = make_gif ('images-overlap', 'white-dot', 1, 1, palette8)
writer.write_image (1, 1, 3, [ RED ])
writer.write_image (1, 1, 3, [ WHITE ])
writer.write_trailer ()

# Image with >256 colors by using local color tables
writer = make_gif ('high-color', 'high-color', 32, 32)
pixels = list (range (256))
colors0 = []
colors1 = []
colors2 = []
colors3 = []
for y in range (16):
    for x in range (16):
        def get_color (x, y):
            return (math.floor (x * 256 / 32), math.floor (y * 256 / 32), 0)
        colors0.append (get_color (x, y))
        colors1.append (get_color (x + 16, y))
        colors2.append (get_color (x, y + 16))
        colors3.append (get_color (x + 16, y + 16))
writer.write_image (16, 16, 8, pixels, left = 0, top = 0, colors = colors0)
writer.write_image (16, 16, 8, pixels, left = 16, top = 0, colors = colors1)
writer.write_image (16, 16, 8, pixels, left = 0, top = 16, colors = colors2)
writer.write_image (16, 16, 8, pixels, left = 16, top = 16, colors = colors3)
writer.write_trailer ()

# Image with additional pixels
writer = make_gif ('additional-data', 'white-dot', 1, 1, palette8)
writer.write_image (10, 10, 3, filled_pixels (10, 10, WHITE))
writer.write_trailer ()
#writer = make_gif ('additional-data-after-eoi', 'white-dot', 1, 1, palette8)
#writer.write_image (10, 10, 3, filled_pixels (10, 10, WHITE))
#writer.write_trailer ()

# Addtional data after end-of-information
writer = make_gif ('extra-data', 'white-dot', 1, 1, palette8)
writer.write_image_descriptor (0, 0, 1, 1)
encoder = gif.LZWEncoder (writer.file, min_code_size = 3)
encoder.feed ([ WHITE ])
encoder.finish (extra_data = b'HIDDEN MESSAGES')
writer.write_trailer ()

# Optional clear and end-of-information codes
writer = make_gif ('no-clear', 'white-dot', 1, 1, palette8)
writer.write_image_descriptor (0, 0, 1, 1)
encoder = gif.LZWEncoder (writer.file, min_code_size = 3, start_with_clear = False)
encoder.feed ([ WHITE ])
encoder.finish ()
writer.write_trailer ()
writer = make_gif ('no-eoi', 'white-dot', 1, 1, palette8)
writer.write_image_descriptor (0, 0, 1, 1)
encoder = gif.LZWEncoder (writer.file, min_code_size = 3)
encoder.feed ([ WHITE ])
encoder.finish (send_eoi = False)
writer.write_trailer ()
# Use 2x1 so the single byte of data contains two codes (6 bits) otherwise the decoder will read a second code due to the lack of EOI
writer = make_gif ('no-clear-and-eoi', 'white-hline2', 2, 1, palette8)
writer.write_image_descriptor (0, 0, 2, 1)
encoder = gif.LZWEncoder (writer.file, min_code_size = 3, start_with_clear = False)
encoder.feed ([ WHITE, WHITE ])
encoder.finish (send_eoi = False)
writer.write_trailer ()

# Maximum sizes
writer = make_gif ('max-width', 'max-width', 65535, 1, palette8)
writer.write_image (65535, 1, 3, filled_pixels (65535, 1, WHITE))
writer.write_trailer ()
writer = make_gif ('max-height', 'max-height', 1, 65535, palette8)
writer.write_image (1, 65535, 3, filled_pixels (1, 65535, WHITE))
writer.write_trailer ()
writer = make_gif ('max-size', 'nocrash', 65535, 65535, palette8)
writer.write_trailer ()

# Generate a random image to test LZW compression
random_width = 100
random_height = 100
pixels = []
seed = 1
for i in range (random_width*random_height):
    m = 2 ** 32
    seed = (1103515245 * seed + 12345) % m
    pixels.append (math.floor (16 * seed / m))
    assert (pixels[-1] < 16)

# Clear code when hit 12 bit limit
writer = make_gif ('4095-codes-clear', '4095-codes', random_width, random_height, palette16)
writer.write_image (random_width, random_height, 4, pixels)
writer.write_trailer ()

# Stop adding code words when hit code 12 bit limit
writer = make_gif ('4095-codes', '4095-codes', random_width, random_height, palette16)
writer.write_image_descriptor (0, 0, random_width, random_height)
encoder = gif.LZWEncoder (writer.file, min_code_size = 4, clear_on_max_width = False)
encoder.feed (pixels)
encoder.finish ()
writer.write_trailer ()

# Have lots of clears by having a small code bit limit
writer = make_gif ('255-codes', '4095-codes', random_width, random_height, palette16)
writer.write_image_descriptor (0, 0, random_width, random_height)
encoder = gif.LZWEncoder (writer.file, min_code_size = 4, max_code_size = 8)
encoder.feed (pixels)
encoder.finish ()
writer.write_trailer ()

# Use a minimum code size
writer = make_gif ('large-codes', '4095-codes', random_width, random_height, palette16)
writer.write_image_descriptor (0, 0, random_width, random_height)
encoder = gif.LZWEncoder (writer.file, min_code_size = 7)
encoder.feed (pixels)
encoder.finish ()
writer.write_trailer ()
writer = make_gif ('max-codes', '4095-codes', random_width, random_height, palette16)
writer.write_image_descriptor (0, 0, random_width, random_height)
encoder = gif.LZWEncoder (writer.file, min_code_size = 11)
encoder.feed (pixels)
encoder.finish ()
writer.write_trailer ()

# Transparent image
writer = make_gif ('transparent', 'four-colors-transparent', 2, 2, palette8)
writer.write_graphic_control_extension (has_transparent = True, transparent_color = RED)
writer.write_image (2, 2, 3, [ RED, GREEN, BLUE, WHITE ])
writer.write_trailer ()

# Invalid transparency color
writer = make_gif ('invalid-transparent', 'four-colors', 2, 2, palette8)
writer.write_graphic_control_extension (has_transparent = True, transparent_color = 255)
writer.write_image (2, 2, 3, [ RED, GREEN, BLUE, WHITE ])
writer.write_trailer ()

# Transparency color set but transparency disabled
writer = make_gif ('disabled-transparent', 'four-colors', 2, 2, palette8)
writer.write_graphic_control_extension (has_transparent = False, transparent_color = RED)
writer.write_image (2, 2, 3, [ RED, GREEN, BLUE, WHITE ])
writer.write_trailer ()

# Loops
writer = make_gif ('loop-infinite', 'white-dot', 1, 1, palette8, loop_count = -1)
writer.write_netscape_extension (loop_count = 0)
writer.write_image (1, 1, 3, [ WHITE ])
writer.write_trailer ()
writer = make_gif ('loop-once', 'white-dot', 1, 1, palette8, loop_count = 1)
writer.write_netscape_extension (loop_count = 1)
writer.write_image (1, 1, 3, [ WHITE ])
writer.write_trailer ()
writer = make_gif ('loop-max', 'white-dot', 1, 1, palette8, loop_count = 65535)
writer.write_netscape_extension (loop_count = 65535)
writer.write_image (1, 1, 3, [ WHITE ])
writer.write_trailer ()
writer = make_gif ('loop-buffer', 'white-dot', 1, 1, palette8, loop_count = -1, buffer_size = 1024)
writer.write_netscape_extension (loop_count = 0, buffer_size = 1024)
writer.write_image (1, 1, 3, [ WHITE ])
writer.write_trailer ()
writer = make_gif ('loop-buffer_max', 'white-dot', 1, 1, palette8, loop_count = -1, buffer_size = 4294967295)
writer.write_netscape_extension (loop_count = 0, buffer_size = 4294967295)
writer.write_image (1, 1, 3, [ WHITE ])
writer.write_trailer ()
writer = make_gif ('loop-animexts', 'white-dot', 1, 1, palette8, loop_count = -1, buffer_size = 1024)
writer.write_animexts_extension (loop_count = 0, buffer_size = 1024)
writer.write_image (1, 1, 3, [ WHITE ])
writer.write_trailer ()

# FIXME: NETSCAPE extension without loop field

# FIXME: NETSCAPE with multiple loop fields

# Animated image
writer = make_gif ('animation', [('animation.0', 50), ('animation.1', 50), ('animation.2', 50), ('animation.3', 50)], 2, 2, palette2, loop_count = -1)
writer.write_netscape_extension (loop_count = 0)
writer.write_graphic_control_extension (delay_time = 50)
writer.write_image (2, 2, 1, [WHITE, BLACK, BLACK, BLACK])
writer.write_graphic_control_extension (delay_time = 50)
writer.write_image (2, 2, 1, [BLACK, WHITE, BLACK, BLACK])
writer.write_graphic_control_extension (delay_time = 50)
writer.write_image (2, 2, 1, [BLACK, BLACK, BLACK, WHITE])
writer.write_graphic_control_extension (delay_time = 50)
writer.write_image (2, 2, 1, [BLACK, BLACK, WHITE, BLACK])
writer.write_trailer ()

# Animation with variable frame speed
writer = make_gif ('animation-speed', [('animation.0', 25), ('animation.1', 50), ('animation.2', 100), ('animation.3', 200)], 2, 2, palette2, loop_count = -1)
writer.write_netscape_extension (loop_count = 0)
writer.write_graphic_control_extension (delay_time = 25)
writer.write_image (2, 2, 1, [WHITE, BLACK, BLACK, BLACK])
writer.write_graphic_control_extension (delay_time = 50)
writer.write_image (2, 2, 1, [BLACK, WHITE, BLACK, BLACK])
writer.write_graphic_control_extension (delay_time = 100)
writer.write_image (2, 2, 1, [BLACK, BLACK, BLACK, WHITE])
writer.write_graphic_control_extension (delay_time = 200)
writer.write_image (2, 2, 1, [BLACK, BLACK, WHITE, BLACK])
writer.write_trailer ()

# Animated image with subimages
# NOTE: RESTORE_BG appears to be interpreted as transparency
writer = make_gif ('animation-subimage', [('animation.0', 50), ('animation.1', 50), ('animation.2', 50), ('animation.3', 50)], 2, 2, palette2, loop_count = -1)
writer.write_netscape_extension (loop_count = 0)
writer.write_graphic_control_extension (gif.DisposalMethod.RESTORE_BACKGROUND, delay_time = 50)
writer.write_image (1, 1, 1, [ WHITE ], 0, 0)
writer.write_graphic_control_extension (gif.DisposalMethod.RESTORE_BACKGROUND, delay_time = 50)
writer.write_image (1, 1, 1, [ WHITE ], 1, 0)
writer.write_graphic_control_extension (gif.DisposalMethod.RESTORE_BACKGROUND, delay_time = 50)
writer.write_image (1, 1, 1, [ WHITE ], 1, 1,)
writer.write_graphic_control_extension (gif.DisposalMethod.RESTORE_BACKGROUND, delay_time = 50)
writer.write_image (1, 1, 1, [ WHITE ], 0, 1)
writer.write_trailer ()

# Background with animated subimages that add together
writer = make_gif ('animation-subimage-add', 'animation-fill', 2, 2, palette2, loop_count = -1)
writer.write_netscape_extension (loop_count = 0)
writer.write_graphic_control_extension (gif.DisposalMethod.KEEP, delay_time = 50)
writer.write_image (2, 2, 1, [WHITE, BLACK, BLACK, BLACK])
writer.write_graphic_control_extension (gif.DisposalMethod.KEEP, delay_time = 50)
writer.write_image (1, 1, 1, [ WHITE ], 1, 0)
writer.write_graphic_control_extension (gif.DisposalMethod.KEEP, delay_time = 50)
writer.write_image (1, 1, 1, [ WHITE ], 1, 1,)
writer.write_graphic_control_extension (gif.DisposalMethod.KEEP, delay_time = 50)
writer.write_image (1, 1, 1, [ WHITE ], 0, 1)
writer.write_trailer ()

# Background with animated subimages that move over initial background
writer = make_gif ('animation-subimage-move', [('animation.0', 50), ('animation.1', 50), ('animation.2', 50), ('animation.3', 50)], 2, 2, palette2, loop_count = -1)
writer.write_netscape_extension (loop_count = 0)
writer.write_image (2, 2, 1, [ BLACK, BLACK, BLACK, BLACK ])
writer.write_graphic_control_extension (gif.DisposalMethod.RESTORE_PREVIOUS, delay_time = 50)
writer.write_image (1, 1, 1, [ WHITE ], 0, 0)
writer.write_graphic_control_extension (gif.DisposalMethod.RESTORE_PREVIOUS, delay_time = 50)
writer.write_image (1, 1, 1, [ WHITE ], 1, 0)
writer.write_graphic_control_extension (gif.DisposalMethod.RESTORE_PREVIOUS, delay_time = 50)
writer.write_image (1, 1, 1, [ WHITE ], 1, 1,)
writer.write_graphic_control_extension (gif.DisposalMethod.RESTORE_PREVIOUS, delay_time = 50)
writer.write_image (1, 1, 1, [ WHITE ], 0, 1)
writer.write_trailer ()

# FIXME: Test restore only applies to area drawn on

# Animation with multiple images per frame
# NOTE: Everyone seems to be doing this wrong...
writer = make_gif ('animation-multi-image', [('animation.0', 50), ('animation.1', 50), ('animation.2', 50), ('animation.3', 50)], 2, 1, palette4, loop_count = -1)
writer.write_netscape_extension (loop_count = 0)
writer.write_image (2, 1, 2, [ BLACK, RED ])
writer.write_graphic_control_extension (delay_time = 50)
writer.write_image (2, 1, 2, [ BLACK, WHITE ])
writer.write_image (2, 1, 2, [ RED,   BLACK ])
writer.write_graphic_control_extension (delay_time = 50)
writer.write_image (2, 1, 2, [ WHITE, BLACK ])
writer.write_trailer ()

# FIXME: Animation with explicit delay times of zero

# FIXME: Animation without fixed first frame (everyone seems to be assuming transparent background)

# Comments
comment = 'Hello World!'
writer = make_gif ('comment', 'white-dot', 1, 1, palette8, comment = comment)
writer.write_comment_extension (comment)
writer.write_image (1, 1, 3, [ WHITE ])
writer.write_trailer ()
comment = ' '.join (['Hello World!'] * 1000)
writer = make_gif ('large-comment', 'white-dot', 1, 1, palette8, comment = comment)
writer.write_comment_extension (comment)
writer.write_image (1, 1, 3, [ WHITE ])
writer.write_trailer ()
comment = '\0'
writer = make_gif ('nul-comment', 'white-dot', 1, 1, palette8, comment = comment)
writer.write_comment_extension (comment)
writer.write_image (1, 1, 3, [ WHITE ])
writer.write_trailer ()
comment = '\xff'
writer = make_gif ('invalid-ascii-comment', 'white-dot', 1, 1, palette8, comment = comment)
writer.write_comment_extension (comment)
writer.write_image (1, 1, 3, [ WHITE ])
writer.write_trailer ()
comment = '\xc3\x28'
writer = make_gif ('invalid-utf8-comment', 'white-dot', 1, 1, palette8, comment = comment)
writer.write_comment_extension (comment)
writer.write_image (1, 1, 3, [ WHITE ])
writer.write_trailer ()

# Plain Text extension
writer = make_gif ('plain-text', 'nocrash', 40, 8, palette8)
writer.write_plain_text_extension ('Hello', 0, 0, 5, 1, 8, 8, 1, 0)
writer.write_image (40, 8, 3, filled_pixels (40, 8, BLACK))
writer.write_trailer ()

# XMP Data
data = open ('test-suite/test.xmp').read ()
writer = make_gif ('xmpd-data', 'white-dot', 1, 1, palette8, xmp_files = ['test.xmp'])
writer.write_xmp_data_extension (data)
writer.write_image (1, 1, 3, [ WHITE ])
writer.write_trailer ()
writer = make_gif ('xmpd-data-empty', 'white-dot', 1, 1, palette8, xmp_files = ['empty.xmp'])
writer.write_xmp_data_extension ('')
writer.write_image (1, 1, 3, [ WHITE ])
writer.write_trailer ()

# Unknown extensions
writer = make_gif ('unknown-extension', 'white-dot', 1, 1, palette8)
writer.write_extension (0x2a, [b'Hello', b'World'])
writer.write_image (1, 1, 3, [ WHITE ])
writer.write_trailer ()
writer = make_gif ('unknown-application-extension', 'white-dot', 1, 1, palette8)
writer.write_application_extension ('UNKNOWN!', 'XXX', [b'Hello', b'World'])
writer.write_image (1, 1, 3, [ WHITE ])
writer.write_trailer ()
writer = make_gif ('nul-application-extension', 'white-dot', 1, 1, palette8)
writer.write_application_extension ('\0\0\0\0\0\0\0\0', '\0\0\0', [b'\0\0\0\0', b'\0\0\0\0'])
writer.write_image (1, 1, 3, [ WHITE ])
writer.write_trailer ()

# FIXME: Multiple clears in a row

# FIXME: ICC profile

# Support older version
writer = make_gif ('gif87a', 'white-dot', 1, 1, palette2, version = gif.Version.GIF87a)
writer.write_image (1, 1, 2, [ WHITE ])
writer.write_trailer ()

# FIXME: Check 89a features don't work in 87a
