#!/usr/bin/python3

__all__ = [ 'Reader', 'Writer' ]

import struct

class Block:
    def __init__ (self, reader, offset, length):
        self.reader = reader
        self.offset = offset
        self.length = length

    def get_data (self):
        return self.reader.buffer[self.offset: self.offset + self.length]

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

    def get_pixels (self):
        offset = self.offset + 10 + len (self.color_table) * 3 + 1
        (subblock_offsets, _) = get_subblocks (self.reader.buffer, offset)
        data = b''
        for offset in subblock_offsets:
            data == get_subblock (self.reader.buffer, offset)
        (_, _, _, values, _) = lzw_decode (data, self.lzw_min_code_size)
        return values

class Extension (Block):
    def __init__ (self, reader, offset, length, label):
        Block.__init__ (self, reader, offset, length)
        self.label = label

    def get_subblocks (self):
        (subblock_offsets, _) = get_subblocks (self.reader.buffer, self.offset + 2)
        if subblock_offsets is None:
            return []
        subblocks = []
        for offset in subblock_offsets:
            subblocks.append (get_subblock (self.reader.buffer, offset))
        return subblocks

class PlainTextExtension (Extension):
    def __init__ (self, reader, offset, length, left, top, width, height, cell_width, cell_height, foreground_color, background_color):
        Extension.__init__ (self, reader, offset, length, 0x01)
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self.cell_width = cell_width
        self.cell_height = cell_height
        self.foreground_color = foreground_color
        self.background_color = background_color

    def get_text (self, encoding = 'ascii'):
        data = b''
        for subblock in self.get_subblocks ()[1:]:
            data += subblock
        return data.decode (encoding)

class GraphicControlExtension (Extension):
    def __init__ (self, reader, offset, length, disposal_method, delay_time, user_input, has_transparent, transparent_color):
        Extension.__init__ (self, reader, offset, length, 0xf9)
        self.disposal_method = disposal_method
        self.delay_time = delay_time
        self.user_input = user_input
        self.has_transparent = has_transparent
        self.transparent_color = transparent_color

class CommentExtension (Extension):
    def __init__ (self, reader, offset, length):
        Extension.__init__ (self, reader, offset, length, 0xfe)

    def get_comment (self, encoding = 'utf-8'):
        data = b''
        for subblock in self.get_subblocks ()[1:]:
            data += subblock
        return data.decode (encoding)

class ApplicationExtension (Extension):
    def __init__ (self, reader, offset, length):
        Extension.__init__ (self, reader, offset, length, 0xff)
        subblocks = self.get_subblocks ()
        if len (subblocks) > 0 and len (subblocks[0]) == 11:
            self.identifier = subblocks[0][:8].decode ('ascii')
            self.authentication_code = subblocks[0][8:11].decode ('ascii')
        else:
            self.identifier = ''
            self.authentication_code = ''

    def is_valid (self):
        return self.identifier != ''

    def get_data (self):
        return self.get_subblocks ()[1:]

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
        self.color_table = []
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
            color_table_size = flags & 0x7
            if has_color_table:
                self.color_table = [ (0, 0, 0) ] * (2 ** (color_table_size + 1))

        # Read color table
        n_colors = len (self.color_table)
        header_size = 13 + n_colors * 3
        if old_len < header_size and len (data) >= header_size:
            for i in range (n_colors):
                offset = 13 + i * 3
                (red, green, blue) = struct.unpack ('BBB', self.buffer[offset: offset + 3])
                self.color_table[i] = (red, green, blue)

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

                block = Image (self, block_start, block_length, left, top, width, height, color_table, color_table_sorted, interlace, lzw_min_code_size + 1)
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

                if len (subblock_offsets) > 0:
                    first_subblock = get_subblock (self.buffer, subblock_offsets[0])
                else:
                    first_subblock = b''

                if label == 0x01 and len (first_subblock) == 12:
                    (left, top, width, height, cell_width, cell_height, foreground_color, background_color) = struct.unpack ('<HHHHBBBB', subblocks[0])
                    block = PlainTextExtension (self, block_start, block_length, left, top, width, height, cell_width, cell_height, foreground_color, background_color)
                elif label == 0xf9 and len (first_subblock) == 4:
                    (flags, delay_time, transparent_color) = struct.unpack ('<BHB', first_subblock)
                    disposal_method = flags >> 2 & 0x7
                    user_input = flags & 0x02 != 0
                    has_transparent = flags & 0x01 != 0
                    block = GraphicControlExtension (self, block_start, block_length, disposal_method, delay_time, user_input, has_transparent, transparent_color)
                elif label == 0xfe:
                    block = CommentExtension (self, block_start, block_length)
                elif label == 0xff:
                    block = ApplicationExtension (self, block_start, block_length)
                else:
                    block = Extension (self, block_start, block_length, label)
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

def get_subblock (data, offset):
    length = data[offset]
    return data[offset + 1: offset + 1 + length]

def lzw_decode (data, start_code_size, max_code_size = 12):
    values = []
    first_code_is_clear = False
    clear_count = 0
    code = 0
    code_bits = 0
    code_count = 0
    code_size = start_code_size
    (codes, clear_code, eoi_code) = make_code_table (code_size)
    last_code = clear_code
    for (index, d) in enumerate (data):
        n_available = 8
        while n_available > 0:
            # Number of bits to get
            n_bits = min (code_size - code_bits, n_available)

            # Extract bits from octet
            new_bits = d & ((1 << n_bits) - 1)
            d >>= n_bits
            n_available -= n_bits

            # Add new bits to the top of the code
            code = new_bits << code_bits | code
            code_bits += n_bits

            # Keep going until we get a full code word
            if code_bits < code_size:
                continue
            code_count += 1

            # Check if the first code is a clear
            if code == clear_code:
                if code_count == 1:
                    first_code_is_clear = True
                else:
                    clear_count += 1

            if code == eoi_code:
                return (first_code_is_clear, clear_count, True, values, data[index + 1:])
            elif code == clear_code:
                code_size = start_code_size
                (codes, clear_code, eoi_code) = make_code_table (code_size)
                last_code = clear_code
            elif code < len (codes):
                for v in codes[code]:
                    values.append (v)
                if last_code != clear_code and len (codes) < 2 ** max_code_size - 1:
                    codes.append (codes[last_code] + (codes[code][0],))
                    assert (len (codes) < 2 ** max_code_size)
                    if len (codes) == 2 ** code_size and code_size < max_code_size:
                        code_size += 1
                last_code = code
            elif code == len (codes):
                if len (codes) < 2 ** max_code_size - 1:
                    codes.append (codes[last_code] + (codes[last_code][0],))
                    assert (len (codes) < 2 ** max_code_size)
                    if len (codes) == 2 ** code_size and code_size < max_code_size:
                        code_size += 1
                for v in codes[-1]:
                    values.append (v)
                last_code = code
            else:
                print ('Ignoring unexpected code %d' % code)
            code = 0
            code_bits = 0

    return (first_code_is_clear, clear_count, False, values, b'')

def make_code_table (code_size):
    codes = []
    for i in range (2 ** (code_size - 1)):
        codes.append ((i,))
    clear_code = 2 ** (code_size - 1)
    eoi_code = clear_code + 1
    codes.append (clear_code)
    codes.append (eoi_code)
    return (codes, clear_code, eoi_code)

class Writer:
    def __init__ (self, write_cb):
        self.write_cb = write_cb
