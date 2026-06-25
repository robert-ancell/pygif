# Copyright 2018 Canonical Ltd.
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU Lesser General Public License version 3, as published by
# the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranties of MERCHANTABILITY,
# SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Lesser
# General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

import struct

from gif.lzw import LZWDecoder


class Version:
    GIF87a = b"GIF87a"
    GIF89a = b"GIF89a"


class DisposalMethod:
    NONE = 0
    KEEP = 1
    RESTORE_BACKGROUND = 2
    RESTORE_PREVIOUS = 3


class ExtensionLabel:
    PLAIN_TEXT = 0x01
    GRAPHIC_CONTROL = 0xF9
    COMMENT = 0xFE
    APPLICATION = 0xFF


class BlockType:
    EXTENSION = 0x21
    IMAGE = 0x2C
    TRAILER = 0x3B


class Block:
    def __init__(self, reader, offset: int, length: int) -> None:
        self.reader = reader
        self.offset = offset
        self.length = length

    def get_data(self) -> bytes:
        return self.reader.buffer[self.offset : self.offset + self.length]


class Image(Block):
    def __init__(
        self,
        reader,
        offset: int,
        length: int,
        left: int,
        top: int,
        width: int,
        height: int,
        color_table: list[tuple[int, int, int]],
        color_table_sorted: bool,
        interlace: bool,
        lzw_min_code_size: int,
    ) -> None:
        Block.__init__(self, reader, offset, length)
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self.color_table = color_table
        self.color_table_sorted = color_table_sorted
        self.interlace = interlace
        self.lzw_min_code_size = lzw_min_code_size

    def get_lzw_data(self):
        offset = self.offset + 10 + len(self.color_table) * 3 + 1
        (subblock_offsets, _) = _get_subblocks(self.reader.buffer, offset)
        data = b""
        for offset, length in subblock_offsets:
            data += self.reader.buffer[offset : offset + length]
        return data

    def decode_lzw(self) -> LZWDecoder:
        offset = self.offset + 10 + len(self.color_table) * 3 + 1
        (subblock_offsets, _) = _get_subblocks(self.reader.buffer, offset)
        if self.lzw_min_code_size >= 12:
            print("Image has invalid code size of %d" % self.lzw_min_code_size)
            return LZWDecoder()
        decoder = LZWDecoder(self.lzw_min_code_size)
        for offset, length in subblock_offsets:
            decoder.feed(self.reader.buffer, offset, length)
        return decoder

    def get_pixels(self) -> list[int]:
        return self.decode_lzw().values


class Extension(Block):
    def __init__(self, reader, offset: int, length: int, label: int) -> None:
        Block.__init__(self, reader, offset, length)
        self.label = label

    def get_subblocks(self) -> list[bytes]:
        (subblock_offsets, _) = _get_subblocks(self.reader.buffer, self.offset + 2)
        if subblock_offsets is None:
            return []
        subblocks = []
        for offset, length in subblock_offsets:
            subblocks.append(self.reader.buffer[offset : offset + length])
        return subblocks


class PlainTextExtension(Extension):
    def __init__(
        self,
        reader,
        offset: int,
        length: int,
        left: int,
        top: int,
        width: int,
        height: int,
        cell_width: int,
        cell_height: int,
        foreground_color: int,
        background_color: int,
    ) -> None:
        Extension.__init__(self, reader, offset, length, ExtensionLabel.PLAIN_TEXT)
        self.left = left
        self.top = top
        self.width = width
        self.height = height
        self.cell_width = cell_width
        self.cell_height = cell_height
        self.foreground_color = foreground_color
        self.background_color = background_color

    def get_text(self, encoding: str = "ascii") -> str:
        data = b""
        for subblock in self.get_subblocks()[1:]:
            data += subblock
        return data.decode(encoding)


class GraphicControlExtension(Extension):
    def __init__(
        self,
        reader,
        offset: int,
        length: int,
        disposal_method,
        delay_time: int,
        user_input,
        has_transparent,
        transparent_color,
    ) -> None:
        Extension.__init__(self, reader, offset, length, ExtensionLabel.GRAPHIC_CONTROL)
        self.disposal_method = disposal_method
        self.delay_time = delay_time
        self.user_input = user_input
        self.has_transparent = has_transparent
        self.transparent_color = transparent_color


class CommentExtension(Extension):
    def __init__(self, reader, offset: int, length: int) -> None:
        Extension.__init__(self, reader, offset, length, ExtensionLabel.COMMENT)

    def get_comment(self, encoding: str = "utf-8") -> str:
        data = b""
        for subblock in self.get_subblocks():
            data += subblock
        return data.decode(encoding)


class ApplicationExtension(Extension):
    def __init__(
        self,
        reader,
        offset: int,
        length: int,
        identifier: str,
        authentication_code: str,
    ) -> None:
        Extension.__init__(self, reader, offset, length, ExtensionLabel.APPLICATION)
        self.identifier = identifier
        self.authentication_code = authentication_code

    def get_application_data(self):
        return self.get_subblocks()[1:]


def _decode_animation_subblocks(
    block: ApplicationExtension,
) -> tuple[int | None, int | None, list[tuple[int, bytes]]]:
    loop_count: int | None = None
    buffer_size: int | None = None
    unused_subblocks = []
    for subblock in block.get_subblocks()[1:]:
        id = subblock[0]
        if id == 1 and len(subblock) == 3:
            (
                _,
                loop_count,
            ) = struct.unpack("<bH", subblock)
        elif id == 2 and len(subblock) == 5:
            (
                _,
                buffer_size,
            ) = struct.unpack("<bI", subblock)
        else:
            unused_subblocks.append((id, subblock[1:]))
    return (loop_count, buffer_size, unused_subblocks)


class NetscapeExtension(ApplicationExtension):
    def __init__(self, reader, offset: int, length: int) -> None:
        ApplicationExtension.__init__(self, reader, offset, length, "NETSCAPE", "2.0")
        (self.loop_count, self.buffer_size, self.unused_subblocks) = (
            _decode_animation_subblocks(self)
        )


class AnimationExtension(ApplicationExtension):
    def __init__(self, reader, offset: int, length: int) -> None:
        ApplicationExtension.__init__(self, reader, offset, length, "ANIMEXTS", "1.0")
        (self.loop_count, self.buffer_size, self.unused_subblocks) = (
            _decode_animation_subblocks(self)
        )


class XMPDataExtension(ApplicationExtension):
    def __init__(self, reader, offset: int, length: int) -> None:
        ApplicationExtension.__init__(self, reader, offset, length, "XMP Data", "XMP")

    def get_metadata(self, encoding="utf-8"):
        # This extension uses a clever hack to put raw XML in the file - it uses
        # a magic suffix that turns the XML text into valid GIF blocks.
        # We just need the raw blocks without the suffix
        return self.reader.buffer[
            self.offset + 14 : self.offset + self.length - 258
        ].decode(encoding)


class ICCColorProfileExtension(ApplicationExtension):
    def __init__(self, reader, offset: int, length: int) -> None:
        ApplicationExtension.__init__(self, reader, offset, length, "ICCRGBG1", "012")

    def get_icc_profile(self):
        data = b""
        for subblock in self.get_subblocks()[1:]:
            data += subblock
        return data


class Trailer(Block):
    def __init__(self, reader, offset: int, length: int) -> None:
        Block.__init__(self, reader, offset, length)


class UnknownBlock(Block):
    def __init__(self, reader, offset: int, block_type: int) -> None:
        Block.__init__(self, reader, offset, 0)
        self.block_type = block_type


def _get_subblocks(data, offset: int) -> tuple[list[tuple[int, int]], int]:
    n_required = 0
    n_available = len(data) - offset
    subblocks: list[tuple[int, int]] = []
    while True:
        if n_available < n_required + 1:
            raise ValueError("Insufficient data for subblock size")
        subblock_size = data[offset + n_required]
        n_required += 1
        if subblock_size == 0:
            return (subblocks, n_required)
        subblocks.append((offset + n_required, subblock_size))
        n_required += subblock_size
        if n_available < n_required:
            raise ValueError("Insufficient data for subblock")
