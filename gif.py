#!/usr/bin/python3

__version__  = '0.1'
__all__      = [ 'AnimationExtension',
                 'ApplicationExtension',
                 'Block',
                 'CommentExtension',
                 'DisposalMethod',
                 'Extension',
                 'GraphicControlExtension',
                 'ICCColorProfileExtension',
                 'Image',
                 'LZWDecoder',
                 'LZWEncoder',
                 'NetscapeExtension',
                 'PlainTextExtension',
                 'Reader',
                 'Trailer',
                 'UnknownBlock',
                 'Writer',
                 'XMPDataExtension' ]

import struct

class DisposalMethod:
    NONE               = 0
    KEEP               = 1
    RESTORE_BACKGROUND = 2
    RESTORE_PREVIOUS   = 3

class ExtensionLabel:
    PLAIN_TEXT         = 0x01
    GRAPHIC_CONTROL    = 0xf9
    COMMENT            = 0xfe
    APPLICATION        = 0xff

class BlockType:
    EXTENSION          = 0x21
    IMAGE              = 0x2c
    TRAILER            = 0x3b

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

    def get_lzw_data (self):
        offset = self.offset + 10 + len (self.color_table) * 3 + 1
        (subblock_offsets, _) = _get_subblocks (self.reader.buffer, offset)
        data = b''
        for (offset, length) in subblock_offsets:
            data += self.reader.buffer[offset: offset + length]
        return data

    def decode_lzw (self):
        offset = self.offset + 10 + len (self.color_table) * 3 + 1
        (subblock_offsets, _) = _get_subblocks (self.reader.buffer, offset)
        decoder = LZWDecoder (self.lzw_min_code_size)
        for (offset, length) in subblock_offsets:
            decoder.feed (self.reader.buffer, offset, length)
        return decoder

    def get_pixels (self):
        return self.decode_lzw ().values

class Extension (Block):
    def __init__ (self, reader, offset, length, label):
        Block.__init__ (self, reader, offset, length)
        self.label = label

    def get_subblocks (self):
        (subblock_offsets, _) = _get_subblocks (self.reader.buffer, self.offset + 2)
        if subblock_offsets is None:
            return []
        subblocks = []
        for (offset, length) in subblock_offsets:
            subblocks.append (self.reader.buffer[offset: offset + length])
        return subblocks

class PlainTextExtension (Extension):
    def __init__ (self, reader, offset, length, left, top, width, height, cell_width, cell_height, foreground_color, background_color):
        Extension.__init__ (self, reader, offset, length, ExtensionLabel.PLAIN_TEXT)
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
        Extension.__init__ (self, reader, offset, length, ExtensionLabel.GRAPHIC_CONTROL)
        self.disposal_method = disposal_method
        self.delay_time = delay_time
        self.user_input = user_input
        self.has_transparent = has_transparent
        self.transparent_color = transparent_color

class CommentExtension (Extension):
    def __init__ (self, reader, offset, length):
        Extension.__init__ (self, reader, offset, length, ExtensionLabel.COMMENT)

    def get_comment (self, encoding = 'utf-8'):
        data = b''
        for subblock in self.get_subblocks ()[1:]:
            data += subblock
        return data.decode (encoding)

class ApplicationExtension (Extension):
    def __init__ (self, reader, offset, length, identifier, authentication_code):
        Extension.__init__ (self, reader, offset, length, ExtensionLabel.APPLICATION)
        self.identifier = identifier
        self.authentication_code = authentication_code

    def get_data (self):
        return self.get_subblocks ()[1:]

def _decode_animation_subblocks (block):
    loop_count = None
    buffer_size = None
    unused_subblocks = []
    for subblock in block.get_subblocks ()[1:]:
        id = subblock[0]
        if id == 1 and len (subblock) == 3:
            (loop_count,) = struct.unpack ('<xH', subblock)
        elif id == 2 and len (subblock) == 5:
            (buffer_size,) = struct.unpack ('<xI', subblock)
        else:
            unused_subblocks.append ((id, subblock[1:]))
    return (loop_count, buffer_size, unused_subblocks)

class NetscapeExtension (ApplicationExtension):
    def __init__ (self, reader, offset, length):
        ApplicationExtension.__init__ (self, reader, offset, length, 'NETSCAPE', '2.0')
        (self.loop_count, self.buffer_size, self.unused_subblocks) = _decode_animation_subblocks (self)

class AnimationExtension (ApplicationExtension):
    def __init__ (self, reader, offset, length):
        ApplicationExtension.__init__ (self, reader, offset, length, 'ANIMEXTS', '1.0')
        (self.loop_count, self.buffer_size, self.unused_subblocks) = _decode_animation_subblocks (self)

class XMPDataExtension (ApplicationExtension):
    def __init__ (self, reader, offset, length):
        ApplicationExtension.__init__ (self, reader, offset, length, 'XMP Data', 'XMP')

    def get_metadata (self):
        # This extension uses a clever hack to put raw XML in the file - it uses
        # a magic suffix that turns the XML text into valid GIF blocks.
        # We just need the raw blocks without the suffix
        return self.reader.buffer[self.offset + 14: self.offset + self.length - 258]

class ICCColorProfileExtension (ApplicationExtension):
    def __init__ (self, reader, offset, length):
        ApplicationExtension.__init__ (self, reader, offset, length, 'ICCRGBG1', '012')

    def get_icc_profile (self):
        data = b''
        for subblock in self.get_subblocks ()[1:]:
            data += subblock
        return data

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
            if block_type == BlockType.IMAGE:
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
                (subblock_offsets, subblocks_length) = _get_subblocks (self.buffer, block_start + block_length)
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
            elif block_type == BlockType.EXTENSION:
                block_length += 1
                if n_available < block_length:
                    return
                label = self.buffer[block_start + 1]

                # Check enough space for blocks
                (subblock_offsets, subblocks_length) = _get_subblocks (self.buffer, block_start + block_length)
                if subblock_offsets is None:
                    return
                block_length += subblocks_length

                if len (subblock_offsets) > 0:
                    (offset, length) = subblock_offsets[0]
                    first_subblock = self.buffer[offset: offset + length]
                else:
                    first_subblock = b''

                if label == ExtensionLabel.PLAIN_TEXT and len (first_subblock) == 12:
                    (left, top, width, height, cell_width, cell_height, foreground_color, background_color) = struct.unpack ('<HHHHBBBB', subblocks[0])
                    block = PlainTextExtension (self, block_start, block_length, left, top, width, height, cell_width, cell_height, foreground_color, background_color)
                elif label == ExtensionLabel.GRAPHIC_CONTROL and len (first_subblock) == 4:
                    (flags, delay_time, transparent_color) = struct.unpack ('<BHB', first_subblock)
                    disposal_method = flags >> 2 & 0x7
                    user_input = flags & 0x02 != 0
                    has_transparent = flags & 0x01 != 0
                    block = GraphicControlExtension (self, block_start, block_length, disposal_method, delay_time, user_input, has_transparent, transparent_color)
                elif label == ExtensionLabel.COMMENT:
                    block = CommentExtension (self, block_start, block_length)
                elif label == ExtensionLabel.APPLICATION and len (first_subblock) == 11:
                    identifier = first_subblock[:8].decode ('ascii')
                    authentication_code = first_subblock[8:11].decode ('ascii')
                    if identifier == 'NETSCAPE' and authentication_code == '2.0':
                        block = NetscapeExtension (self, block_start, block_length)
                    elif identifier == 'ANIMEXTS' and authentication_code == '1.0':
                        block = AnimationExtension (self, block_start, block_length)
                    elif identifier == 'XMP Data' and authentication_code == 'XMP':
                        block = XMPDataExtension (self, block_start, block_length)
                    elif identifier == 'ICCRGBG1' and authentication_code == '012':
                        block = ICCColorProfileExtension (self, block_start, block_length)
                    else:
                        block = ApplicationExtension (self, block_start, block_length, identifier, authentication_code)
                else:
                    block = Extension (self, block_start, block_length, label)
                self.blocks.append (block)

            # Trailer
            elif block_type == BlockType.TRAILER:
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

def _get_subblocks (data, offset):
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
        subblocks.append ((offset + n_required, subblock_size))
        n_required += subblock_size
        if n_available < n_required:
            return (None, 0)

class LZWDecoder:
    def __init__ (self, min_code_size = 3, max_code_size = 12):
        self.min_code_size = min_code_size
        self.max_code_size = max_code_size

        # Codes and values to output
        self.codes = []
        self.values = []
        self.n_used = 0

        # Code table
        self.clear_code = 2 ** (min_code_size - 1)
        self.eoi_code = self.clear_code + 1
        self.code_table = []
        for i in range (2 ** (min_code_size - 1)):
            self.code_table.append ((i,))
        self.code_table.append (self.clear_code)
        self.code_table.append (self.eoi_code)

        # Code currently being decoded
        self.code = 0                       # Current bits of code
        self.code_bits = 0                  # Current number of bits
        self.code_size = self.min_code_size # Required number of bits
        self.last_code = self.clear_code    # Previous code processed

    def feed (self, data, offset = 0, length = -1):
        if length < 0:
            length = len (data) - offset
        for i in range (offset, offset + length):
            d = data[i]
            self.n_used += 1
            n_available = 8
            while n_available > 0:
                # Number of bits to get
                n_bits = min (self.code_size - self.code_bits, n_available)

                # Extract bits from octet
                new_bits = d & ((1 << n_bits) - 1)
                d >>= n_bits
                n_available -= n_bits

                # Add new bits to the top of the code
                self.code = new_bits << self.code_bits | self.code
                self.code_bits += n_bits

                # Keep going until we get a full code word
                if self.code_bits < self.code_size:
                    continue
                code = self.code
                self.code = 0
                self.code_bits = 0
                self.codes.append (code)

                # Stop on end of information code
                if code == self.eoi_code:
                    return

                # Reset code table on clear
                if code == self.clear_code:
                    self.code_size = self.min_code_size
                    self.code_table = self.code_table[:self.eoi_code + 1]
                    self.last_code = code
                    continue

                if code < len (self.code_table):
                    for v in self.code_table[code]:
                        self.values.append (v)
                    if self.last_code != self.clear_code and len (self.code_table) < 2 ** self.max_code_size - 1:
                        self.code_table.append (self.code_table[self.last_code] + (self.code_table[code][0],))
                        assert (len (self.code_table) < 2 ** self.max_code_size)
                        if len (self.code_table) == 2 ** self.code_size and self.code_size < self.max_code_size:
                            self.code_size += 1
                    self.last_code = code
                elif code == len (self.code_table):
                    if len (self.code_table) < 2 ** self.max_code_size - 1:
                        self.code_table.append (self.code_table[self.last_code] + (self.code_table[self.last_code][0],))
                        assert (len (self.code_table) < 2 ** self.max_code_size)
                        if len (self.code_table) == 2 ** self.code_size and self.code_size < self.max_code_size:
                            self.code_size += 1
                    for v in self.code_table[-1]:
                        self.values.append (v)
                    self.last_code = code
                else:
                    print ('Ignoring unexpected code %d' % code)

    def is_complete (self):
        return len (self.codes) > 0 and self.codes[-1] == self.eoi_code

class Writer:
    def __init__ (self, file):
        self.file = file

    # FIXME: Give a proper name?
    def write_headers (self, width, height, colors = [], original_depth = 8, background_color = 0, pixel_aspect_ratio = 0):
        has_color_table = len (colors) > 0
        if has_color_table:
            from math import ceil, log2
            depth = max (ceil (log2 (len (colors))), 1)
        else:
            depth = 1
        assert (1 <= depth <= 8)

        self.write_header ()
        self.write_screen_descriptor (width, height, has_color_table = has_color_table, depth = depth, original_depth = original_depth, background_color = background_color, pixel_aspect_ratio = pixel_aspect_ratio)
        if has_color_table:
            self.write_color_table (colors, depth)

    def write_header (self):
        self.file.write (b'GIF89a') # FIXME: Support 87a version

    def write_screen_descriptor (self, width, height, has_color_table = False, colors_sorted = False, depth = 1, original_depth = 8, background_color = 0, pixel_aspect_ratio = 0):
        assert (0 <= width <= 65535)
        assert (0 <= height <= 65535)
        assert (1 <= depth <= 8)
        assert (1 <= original_depth <= 8)

        flags = 0x00
        if has_color_table:
            flags |= 0x80
        flags |= depth - 1
        flags = flags | (original_depth - 1) << 4
        if colors_sorted:
            flags |= 0x08
        self.file.write (struct.pack ('<HHBBB', width, height, flags, background_color, pixel_aspect_ratio))

    def write_color (self, red, green, blue):
        self.file.write (struct.pack ('BBB', red, green, blue))

    def write_color_table (self, colors, depth):
        assert (1 <= depth <= 8)
        assert (len (colors) <= 2 ** depth)
        for (red, green, blue) in colors:
            self.write_color (red, green, blue)
        for i in range (len (colors), 2 ** depth):
            self.write_color (0, 0, 0)

    def write_image (self, width, height, depth, pixels, left = 0, top = 0, global_colors = [], colors = [], interlace = False, colors_sorted = False, reserved = 0):
        has_color_table = len (colors) > 0
        if has_color_table:
            color_table_size = depth
        else:
            color_table_size = 1
        self.write_image_descriptor (left, top, width, height, has_color_table = has_color_table, depth = color_table_size, interlace = interlace)
        if has_color_table:
            self.write_color_table (colors, depth)
        encoder = LZWEncoder (self.file, min_code_size = max (depth, 2))
        encoder.feed (pixels)
        encoder.finish ()

    def write_image_descriptor (self, left, top, width, height, has_color_table = False, depth = 1, interlace = False, colors_sorted = False, reserved = 0):
        assert (0 <= width <= 65535)
        assert (0 <= height <= 65535)
        assert (0 <= left <= 65535)
        assert (0 <= top <= 65535)
        assert (1 <= depth <= 8)
        assert (0 <= reserved <= 3)

        flags = 0x00
        if has_color_table:
            flags |= 0x80
        flags |= depth - 1
        if interlace:
            flags |= 0x40
        if colors_sorted:
            flags |= 0x20
        flags |= reserved << 3
        self.file.write (struct.pack ('<BHHHHB', BlockType.IMAGE, left, top, width, height, flags))

    def write_extension (self, label, blocks):
        self.write_extension_header (label)
        for block in blocks:
            self.write_extension_block (block)
        self.write_extension_trailer ()

    def write_extension_header (self, label):
        self.file.write (struct.pack ('BB', BlockType.EXTENSION, label))

    def write_extension_block (self, block):
        assert (len (block) < 256)
        self.file.write (struct.pack ('B', len (block)))
        self.file.write (block)

    def write_extension_trailer (self):
        self.file.write (b'\x00')

    def write_plain_text_extension (self, text, left, top, width, height, cell_width, cell_height, foreground_color, background_color):
        assert (0 <= left <= 65535)
        assert (0 <= top <= 65535)
        assert (0 <= width <= 65535)
        assert (0 <= height <= 65535)
        assert (0 <= cell_width <= 255)
        assert (0 <= cell_height <= 255)
        assert (0 <= foreground_color <= 255)
        assert (0 <= background_color <= 255)
        self.write_extension_header (ExtensionLabel.PLAIN_TEXT)
        self.write_extension_block (struct.pack ('<HHHHBBBB', left, top, width, height, cell_width, cell_height, foreground_color, background_color))
        while len (text) > 0:
            self.write_extension_block (bytes (text[:255], 'ascii'))
            text = text[254:]
        self.write_extension_trailer ()

    def write_graphic_control_extension (self, disposal_method = DisposalMethod.NONE, delay_time = 0, user_input = False, has_transparent = False, transparent_color = 0, reserved = 0):
        assert (0 <= disposal_method <= 7)
        assert (0 <= reserved <= 7)
        assert (0 <= delay_time <= 65535)
        flags = 0x00
        flags |= disposal_method << 2
        if user_input:
            flags |= 0x02
        if has_transparent:
            flags |= 0x01
        self.write_extension_header (ExtensionLabel.GRAPHIC_CONTROL)
        self.write_extension_block (struct.pack ('<BHB', flags, delay_time, transparent_color))
        self.write_extension_trailer ()

    def write_comment_extension (self, text):
        self.write_extension_header (ExtensionLabel.COMMENT)
        while len (text) > 0:
            self.write_extension_block (bytes (text[:255], 'utf-8'))
            text = text[254:]
        self.write_extension_trailer ()

    def write_application_extension (self, application_identifier, application_authentication_code, blocks):
        assert (len (application_identifier) == 8)
        assert (len (application_authentication_code) == 3)
        self.write_application_extension_header (application_identifier, application_authentication_code)
        for block in blocks:
            self.write_extension_block (block)
        self.write_extension_trailer ()

    def write_application_extension_header (self, application_identifier, application_authentication_code):
        self.write_extension_header (ExtensionLabel.APPLICATION)
        self.write_extension_block (bytes (application_identifier + application_authentication_code, 'ascii'))

    def write_netscape_extension (self, loop_count = -1, buffer_size = -1):
        assert (loop_count < 65536)
        assert (buffer_size < 4294967296)
        self.write_application_extension_header ('NETSCAPE', '2.0')
        if loop_count >= 0:
            self.write_extension_block (struct.pack ('<BH', 1, loop_count))
        if buffer_size >= 0:
            self.write_extension_block (struct.pack ('<BI', 2, buffer_size))
        self.write_extension_trailer ()

    def write_animexts_extension (self, loop_count = -1, buffer_size = -1):
        assert (loop_count < 65536)
        self.write_application_extension_header ('ANIMEXTS', '1.0')
        if loop_count >= 0:
            self.write_extension_block (struct.pack ('<BH', 1, loop_count))
        if buffer_size >= 0:
            self.write_extension_block (struct.pack ('<BI', 2, buffer_size))
        self.write_extension_trailer ()

    def write_xmp_data_extension (self, metadata):
        self.write_application_extension_header ('XMP Data', 'XMP')
        # This extension uses a clever hack to put raw XML in the file - it uses
        # a magic suffix that turns the XML text into valid GIF blocks.
        self.file.write (bytes (metadata, 'utf-8'))
        self.file.write (b'\x01')
        for i in range (256):
            self.file.write (struct.pack ('B', 0xff - i))
        self.file.write (b'\x00')

    def write_icc_color_profile_extension (self, icc_profile):
        self.write_application_extension_header ('ICCRGBG1', '012')
        offset = 0
        while offset < len (icc_profile):
            length = min (len (icc_profile) - offset, 255)
            self.write_extension_block (icc_profile[offset: offset + length])
            offset += length
        self.write_extension_trailer ()

    def write_trailer (self):
        self.file.write (struct.pack ('B', BlockType.TRAILER))

class LZWEncoder:
    def __init__ (self, file, min_code_size = 2, max_code_size = 12, start_with_clear = True, clear_on_max_width = True):
        self.file = file
        self.min_code_size = max (min_code_size, 2)
        self.max_code_size = max_code_size
        self.clear_on_max_width = clear_on_max_width

        # Data being output
        self.data = b''
        self.octet = 0x00
        self.octet_bits = 0

        # Code table
        self.clear_code = 2 ** self.min_code_size
        self.eoi_code = self.clear_code + 1
        self.code_table = {}
        for i in range (2 ** self.min_code_size):
            self.code_table[(i,)] = i
        self.next_code = self.eoi_code + 1

        # Code currently being encoded
        self.code = tuple ()
        self.code_size = self.min_code_size + 1

        if start_with_clear:
            self.write_code (self.clear_code)

        self.file.write (struct.pack ('B', self.min_code_size))

    def feed (self, values):
        for value in values:
            self.code += (value,)

            if self.code in self.code_table:
                continue

            # If there are available bits, then add a new code
            if self.next_code < 2 ** self.max_code_size:
                new_code = self.next_code
                self.next_code += 1
                self.code_table[self.code] = new_code

            self.write_code (self.code_table[self.code[:-1]])
            self.code = self.code[-1:]

            # Use enough bits to place the next code
            if self.next_code == 2 ** self.code_size + 1:
                self.code_size += 1

            # Clear when out of codes
            if self.next_code == 2 ** self.max_code_size and self.clear_on_max_width:
                self.write_code (self.clear_code)
                self.code_table = {}
                for i in range (2 ** self.min_code_size):
                    self.code_table[(i,)] = i
                self.code_size = self.min_code_size + 1
                self.next_code = self.eoi_code + 1

    def finish (self, send_eoi = True, extra_data = None):
        # Write last code in progress
        self.write_code (self.code_table[self.code])
        if send_eoi:
            self.write_code (self.eoi_code)
        if self.octet_bits > 0:
            self.data += struct.pack ('B', self.octet)

        if extra_data is not None:
            self.data += extra_data

        # Write remaining blocks
        while len (self.data) > 0:
            length = min (len (self.data), 255)
            self.file.write (struct.pack ('B', length))
            self.file.write (self.data[:length])
            self.data = self.data[length:]
        self.file.write (b'\x00')

        self.data = b''
        self.code = tuple ()

    def write_code (self, code):
        bits_needed = self.code_size
        while bits_needed > 0:
            bits_used = min (bits_needed, 8 - self.octet_bits)
            self.octet |= (code << self.octet_bits) & 0xff
            self.octet_bits += bits_used
            code >>= bits_used
            bits_needed -= bits_used
            if self.octet_bits == 8:
                self.data += struct.pack ('B', self.octet)
                if len (self.data) == 255:
                    self.file.write (b'\xff')
                    self.file.write (self.data)
                    self.data = b''
                self.octet = 0x00
                self.octet_bits = 0
