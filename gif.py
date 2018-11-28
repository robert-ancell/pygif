#!/usr/bin/python3

__all__ = [ 'Reader', 'Writer' ]

import struct

class Block:
    def __init__ (self, reader, offset, length):
        self.reader = reader
        self.offset = offset
        self.length = length

class Image (Block):
    def __init__ (self, reader, offset, length, left, top, width, height, color_table, color_table_sorted, interlace, lzw_min_code_size):
        Block.__init__ (self, reader, offset, length)
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self.color_table = color_table
        self.color_table_sorted = color_table_sorted
        self.interlace = interlace
        self.lzw_min_code_size = lzw_min_code_size

class Extension (Block):
    def __init__ (self, reader, offset, length):
        Block.__init__ (self, reader, offset, length)

    def get_subblocks (self):
        (subblock_offsets, _) = get_subblocks (self.reader.buffer, self.offset + 2)
        if subblock_offsets is None:
            return []
        subblocks = []
        for offset in subblock_offsets:
            length = self.reader.buffer[offset]
            subblocks.append (self.reader.buffer[offset + 1: offset + 1 + length])
        return subblocks

class Trailer (Block):
    def __init__ (self, reader, offset, length):
        Block.__init__ (self, reader, offset, length)

class UnknownBlock (Block):
    def __init__ (self, reader, offset, block_type):
        Block.__init__ (self, reader, offset, 0)
        self.block_type = block_type

class Reader:
    """
    GIF decoder in pure Python.
    """

    def __init__ (self,):
        self.buffer = b''
        self.width = 0
        self.height = 0
        self.original_depth = 0
        self.color_table_sorted = False
        self.background_color = 0
        self.pixel_aspect_ratio = 0
        self.blocks = []

    def feed (self, data):
        old_len = len (self.buffer)
        self.buffer += data

        # Read logical screen descriptor
        if old_len < 13 and len (self.buffer) >= 13:
            (_, self.width, self.height, flags, self.background_color, self.pixel_aspect_ratio) = struct.unpack ('<6sHHBBB', self.buffer[:13])
            has_color_table = flags & 0x80 != 0
            self.original_depth = ((flags >> 4) & 0x7) + 1
            self.color_table_sorted = flags & 0x08 != 0
            self.color_table_size = flags & 0x7
            if has_color_table:
                self.color_table = [ (0, 0, 0) ] * 2 ** (self.color_table_size + 1)
            else:
                self.color_table = []

        # Read color table
        n_colors = len (self.color_table)
        header_size = 13 + n_colors * 3
        if old_len < header_size and len (data) >= header_size:
            for i in range (n_colors):
                offset = 13 + i * 3
                (red, green, blue) = struct.unpack ('BBB', self.buffer[offset: offset + 3])
                self.color_table.append ((red, green, blue))

        # Read blocks
        while not self.is_complete () and not self.has_unknown_block ():
            # See if we have the start of the next block
            if len (self.blocks) == 0:
                block_start = header_size
            else:
                block_start = self.blocks[-1].offset + self.blocks[-1].length
            if block_start >= len (self.buffer):
                return

            block_type = self.buffer[block_start]
            n_available = len (self.buffer) - block_start
            block_length = 1

            # Image
            if block_type == 0x2c:
                block_length += 9
                if n_available < block_length:
                    return
                (left, top, width, height, flags) = struct.unpack ('<HHHHB', self.buffer[block_start + 1: block_start + 10])
                has_color_table = flags & 0x80 != 0
                interlace = flags & 0x40 != 0
                color_table_sorted = flags & 0x20 != 0
                color_table_size = flags & 0x7

                # Check enough space for color table
                n_colors = 2 ** (color_table_size + 1)
                if has_color_table:
                    block_length += n_colors * 3
                    if n_available < block_length:
                        return

                # Check enough space for image data
                if n_available < block_length + 1:
                    return
                lzw_min_code_size = self.buffer[block_start + block_length]
                block_length += 1
                (subblock_offsets, subblocks_length) = get_subblocks (self.buffer, block_start + block_length)
                if subblock_offsets is None:
                    return
                block_length += subblocks_length

                # Read color table
                color_table = []
                if has_color_table:
                    for i in range (n_colors):
                        offset = 10 + i * 3
                        (red, green, blue) = struct.unpack ('BBB', self.buffer[offset: offset + 3])
                        color_table.append ((red, green, blue))

                block = Image (self, block_start, block_length, left, top, width, height, color_table, color_table_sorted, interlace, lzw_min_code_size)
                self.blocks.append (block)

            # Extension
            elif block_type == 0x21:
                block_length += 1
                if n_available < block_length:
                    return
                label = self.buffer[block_start + 1]

                # Check enough space for blocks
                (subblock_offsets, subblocks_length) = get_subblocks (self.buffer, block_start + block_length)
                if subblock_offsets is None:
                    return
                block_length += subblocks_length

                block = Extension (self, block_start, block_length)
                self.blocks.append (block)

            # Trailer
            elif block_type == 0x3b:
                self.blocks.append (Trailer (self, block_start, 1))
                return

            else:
                self.blocks.append (UnknownBlock (self, block_start, block_type))
                return

    def has_header (self):
        return len (self.buffer) >= 6

    def is_gif (self):
        return self.buffer[:6] in [ b'GIF87a', b'GIF89a' ]

    def has_screen_descriptor (self):
        return len (self.buffer) >= 13

    def is_complete (self):
        return len (self.blocks) > 0 and isinstance (self.blocks[-1], Trailer)

    def has_unknown_block (self):
        return len (self.blocks) > 0 and isinstance (self.blocks[-1], UnknownBlock)

def get_subblocks (data, offset):
    n_required = 0
    n_available = len (data) - offset
    subblocks = []
    while True:
        if n_available < n_required + 1:
            return (None, 0)
        subblock_size = data[offset + n_required]
        n_required += 1
        if subblock_size == 0:
            return (subblocks, n_required)
        subblocks.append (offset + n_required - 1)
        n_required += subblock_size
        if n_available < n_required:
            return (None, 0)

class Writer:
    def __init__ (self, write_cb):
        self.write_cb = write_cb
