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

from gif.image import (
    AnimationExtension,
    ApplicationExtension,
    Block,
    BlockType,
    CommentExtension,
    Extension,
    ExtensionLabel,
    GraphicControlExtension,
    ICCColorProfileExtension,
    Image,
    NetscapeExtension,
    PlainTextExtension,
    Trailer,
    UnknownBlock,
    Version,
    XMPDataExtension,
    _get_subblocks,
)


class Reader:
    """
    GIF decoder in pure Python.
    """

    def __init__(
        self,
    ) -> None:
        self.buffer = b""
        self.version = b""
        self.width = 0
        self.height = 0
        self.original_depth = 0
        self.color_table_sorted = False
        self.background_color = 0
        self.pixel_aspect_ratio = 0
        self.color_table: list[tuple[int, int, int]] = []
        self.blocks: list[Block] = []

    def feed(self, data: bytes) -> None:
        old_len = len(self.buffer)
        self.buffer += data

        if old_len < 6 and len(self.buffer) >= 6:
            self.version = self.buffer[:6]

        # Read logical screen descriptor
        if old_len < 13 and len(self.buffer) >= 13:
            (
                _,
                self.width,
                self.height,
                flags,
                self.background_color,
                self.pixel_aspect_ratio,
            ) = struct.unpack("<6sHHBBB", self.buffer[:13])
            has_color_table = flags & 0x80 != 0
            self.original_depth = ((flags >> 4) & 0x7) + 1
            self.color_table_sorted = flags & 0x08 != 0
            color_table_size = flags & 0x7
            if has_color_table:
                self.color_table = [(0, 0, 0)] * (2 ** (color_table_size + 1))

        # Read color table
        n_colors = len(self.color_table)
        header_size = 13 + n_colors * 3
        if old_len < header_size and len(data) >= header_size:
            for i in range(n_colors):
                offset = 13 + i * 3
                (red, green, blue) = struct.unpack(
                    "BBB", self.buffer[offset : offset + 3]
                )
                self.color_table[i] = (red, green, blue)

        # Read blocks
        while not self.is_complete() and not self.has_unknown_block():
            # See if we have the start of the next block
            if len(self.blocks) == 0:
                block_start = header_size
            else:
                block_start = self.blocks[-1].offset + self.blocks[-1].length
            if block_start >= len(self.buffer):
                return

            block_type = self.buffer[block_start]
            n_available = len(self.buffer) - block_start
            block_length = 1

            # Image
            if block_type == BlockType.IMAGE:
                block_length += 9
                if n_available < block_length:
                    return
                (left, top, width, height, flags) = struct.unpack(
                    "<HHHHB", self.buffer[block_start + 1 : block_start + 10]
                )
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
                (subblock_offsets, subblocks_length) = _get_subblocks(
                    self.buffer, block_start + block_length
                )
                if subblock_offsets is None:
                    return
                block_length += subblocks_length

                # Read color table
                color_table = []
                if has_color_table:
                    for i in range(n_colors):
                        offset = block_start + 10 + i * 3
                        (red, green, blue) = struct.unpack(
                            "BBB", self.buffer[offset : offset + 3]
                        )
                        color_table.append((red, green, blue))

                self.blocks.append(
                    Image(
                        self.buffer,
                        block_start,
                        block_length,
                        left,
                        top,
                        width,
                        height,
                        color_table,
                        color_table_sorted,
                        interlace,
                        lzw_min_code_size,
                    )
                )

            # Extension
            elif block_type == BlockType.EXTENSION:
                block_length += 1
                if n_available < block_length:
                    return
                label = self.buffer[block_start + 1]

                # Check enough space for blocks
                (subblock_offsets, subblocks_length) = _get_subblocks(
                    self.buffer, block_start + block_length
                )
                if subblock_offsets is None:
                    return
                block_length += subblocks_length

                if len(subblock_offsets) > 0:
                    (offset, length) = subblock_offsets[0]
                    first_subblock = self.buffer[offset : offset + length]
                else:
                    first_subblock = b""

                if label == ExtensionLabel.PLAIN_TEXT and len(first_subblock) == 12:
                    (
                        left,
                        top,
                        width,
                        height,
                        cell_width,
                        cell_height,
                        foreground_color,
                        background_color,
                    ) = struct.unpack("<HHHHBBBB", first_subblock)
                    block: Block = PlainTextExtension(
                        self.buffer,
                        block_start,
                        block_length,
                        left,
                        top,
                        width,
                        height,
                        cell_width,
                        cell_height,
                        foreground_color,
                        background_color,
                    )
                elif (
                    label == ExtensionLabel.GRAPHIC_CONTROL and len(first_subblock) == 4
                ):
                    (flags, delay_time, transparent_color) = struct.unpack(
                        "<BHB", first_subblock
                    )
                    disposal_method = flags >> 2 & 0x7
                    user_input = flags & 0x02 != 0
                    has_transparent = flags & 0x01 != 0
                    block = GraphicControlExtension(
                        self.buffer,
                        block_start,
                        block_length,
                        disposal_method,
                        delay_time,
                        user_input,
                        has_transparent,
                        transparent_color,
                    )
                elif label == ExtensionLabel.COMMENT:
                    block = CommentExtension(self.buffer, block_start, block_length)
                elif label == ExtensionLabel.APPLICATION and len(first_subblock) == 11:
                    identifier = first_subblock[:8].decode("ascii")
                    authentication_code = first_subblock[8:11].decode("ascii")
                    if identifier == "NETSCAPE" and authentication_code == "2.0":
                        block = NetscapeExtension(
                            self.buffer, block_start, block_length
                        )
                    elif identifier == "ANIMEXTS" and authentication_code == "1.0":
                        block = AnimationExtension(
                            self.buffer, block_start, block_length
                        )
                    elif identifier == "XMP Data" and authentication_code == "XMP":
                        block = XMPDataExtension(self.buffer, block_start, block_length)
                    elif identifier == "ICCRGBG1" and authentication_code == "012":
                        block = ICCColorProfileExtension(
                            self.buffer, block_start, block_length
                        )
                    else:
                        block = ApplicationExtension(
                            self.buffer,
                            block_start,
                            block_length,
                            identifier,
                            authentication_code,
                        )
                else:
                    block = Extension(self.buffer, block_start, block_length, label)
                self.blocks.append(block)

            # Trailer
            elif block_type == BlockType.TRAILER:
                self.blocks.append(Trailer(self.buffer, block_start, 1))
                return

            else:
                self.blocks.append(UnknownBlock(self.buffer, block_start, block_type))
                return

    def has_header(self) -> bool:
        return len(self.buffer) >= 6

    def is_gif(self) -> bool:
        return self.version in [Version.GIF87a, Version.GIF89a]

    def has_screen_descriptor(self) -> bool:
        return len(self.buffer) >= 13

    def is_complete(self) -> bool:
        return len(self.blocks) > 0 and isinstance(self.blocks[-1], Trailer)

    def has_unknown_block(self) -> bool:
        return len(self.blocks) > 0 and isinstance(self.blocks[-1], UnknownBlock)
