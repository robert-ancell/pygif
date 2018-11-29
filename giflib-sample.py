#!/usr/bin/python3

import gif

writer = gif.Writer (open ('sample_1.gif', 'wb'))

# Regenerate the sample image from http://giflib.sourceforge.net/whatsinagif/
colors = [ (0xff, 0xff, 0xff), (0xff, 0x00, 0x00), (0x00, 0x00, 0xff), (0x00, 0x00, 0x00) ]
depth = 2
pixels = [ 1, 1, 1, 1, 1, 2, 2, 2, 2, 2,
           1, 1, 1, 1, 1, 2, 2, 2, 2, 2,
           1, 1, 1, 1, 1, 2, 2, 2, 2, 2,
           1, 1, 1, 0, 0, 0, 0, 2, 2, 2,
           1, 1, 1, 0, 0, 0, 0, 2, 2, 2,
           2, 2, 2, 0, 0, 0, 0, 1, 1, 1,
           2, 2, 2, 0, 0, 0, 0, 1, 1, 1,
           2, 2, 2, 2, 2, 1, 1, 1, 1, 1,
           2, 2, 2, 2, 2, 1, 1, 1, 1, 1,
           2, 2, 2, 2, 2, 1, 1, 1, 1, 1 ]
writer.write_header ()
writer.write_screen_descriptor (10, 10, has_color_table = True, depth = depth, original_depth = 2)
writer.write_color_table (colors, depth)
writer.write_graphic_control_extension ()
writer.write_image_descriptor (0, 0, 10, 10)
encoder = gif.LZWEncoder (writer.file, depth)
encoder.feed (pixels)
encoder.finish ()
writer.write_trailer ()
