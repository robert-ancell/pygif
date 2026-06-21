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

from gif.image import BlockType, DisposalMethod, ExtensionLabel, Version
from gif.lzw import LZWEncoder


class Writer:
    def __init__(self, file):
        self.file = file

    def write_header(self, version=Version.GIF89a):
        self.file.write(version)

    def write_screen_descriptor(
        self,
        width,
        height,
        has_color_table=False,
        depth=1,
        colors_sorted=False,
        original_depth=8,
        background_color=0,
        pixel_aspect_ratio=0,
    ):
        assert 0 <= width <= 65535
        assert 0 <= height <= 65535
        assert 1 <= depth <= 8
        assert 1 <= original_depth <= 8

        flags = 0x00
        if has_color_table:
            flags |= 0x80
        flags |= depth - 1
        flags = flags | (original_depth - 1) << 4
        if colors_sorted:
            flags |= 0x08
        self.file.write(
            struct.pack(
                "<HHBBB", width, height, flags, background_color, pixel_aspect_ratio
            )
        )

    def write_color(self, red, green, blue):
        self.file.write(struct.pack("BBB", red, green, blue))

    def write_color_table(self, colors, depth):
        assert 1 <= depth <= 8
        assert len(colors) <= 2**depth
        for red, green, blue in colors:
            self.write_color(red, green, blue)
        for i in range(len(colors), 2**depth):
            self.write_color(0, 0, 0)

    def write_image(
        self,
        width,
        height,
        depth,
        pixels,
        left=0,
        top=0,
        colors=[],
        interlace=False,
        colors_sorted=False,
        reserved=0,
    ):
        has_color_table = len(colors) > 0
        if has_color_table:
            color_table_size = depth
        else:
            color_table_size = 1
        self.write_image_descriptor(
            left,
            top,
            width,
            height,
            has_color_table=has_color_table,
            depth=color_table_size,
            interlace=interlace,
        )
        if has_color_table:
            self.write_color_table(colors, depth)
        encoder = LZWEncoder(self.file, min_code_size=max(depth, 2))
        encoder.feed(pixels)
        encoder.finish()

    def write_image_descriptor(
        self,
        left,
        top,
        width,
        height,
        has_color_table=False,
        depth=1,
        interlace=False,
        colors_sorted=False,
        reserved=0,
    ):
        assert 0 <= width <= 65535
        assert 0 <= height <= 65535
        assert 0 <= left <= 65535
        assert 0 <= top <= 65535
        assert 1 <= depth <= 8
        assert 0 <= reserved <= 3

        flags = 0x00
        if has_color_table:
            flags |= 0x80
        flags |= depth - 1
        if interlace:
            flags |= 0x40
        if colors_sorted:
            flags |= 0x20
        flags |= reserved << 3
        self.file.write(
            struct.pack("<BHHHHB", BlockType.IMAGE, left, top, width, height, flags)
        )

    def write_extension(self, label, blocks):
        self.write_extension_header(label)
        for block in blocks:
            self.write_extension_block(block)
        self.write_extension_trailer()

    def write_extension_header(self, label):
        self.file.write(struct.pack("BB", BlockType.EXTENSION, label))

    def write_extension_block(self, block):
        assert len(block) < 256
        self.file.write(struct.pack("B", len(block)))
        self.file.write(block)

    def write_extension_trailer(self):
        self.file.write(b"\x00")

    def write_plain_text_extension(
        self,
        text,
        left,
        top,
        width,
        height,
        cell_width,
        cell_height,
        foreground_color,
        background_color,
    ):
        assert 0 <= left <= 65535
        assert 0 <= top <= 65535
        assert 0 <= width <= 65535
        assert 0 <= height <= 65535
        assert 0 <= cell_width <= 255
        assert 0 <= cell_height <= 255
        assert 0 <= foreground_color <= 255
        assert 0 <= background_color <= 255
        self.write_extension_header(ExtensionLabel.PLAIN_TEXT)
        self.write_extension_block(
            struct.pack(
                "<HHHHBBBB",
                left,
                top,
                width,
                height,
                cell_width,
                cell_height,
                foreground_color,
                background_color,
            )
        )
        while len(text) > 0:
            self.write_extension_block(bytes(text[:255], "ascii"))
            text = text[254:]
        self.write_extension_trailer()

    def write_graphic_control_extension(
        self,
        disposal_method=DisposalMethod.NONE,
        delay_time=0,
        user_input=False,
        has_transparent=False,
        transparent_color=0,
        reserved=0,
    ):
        assert 0 <= disposal_method <= 7
        assert 0 <= reserved <= 7
        assert 0 <= delay_time <= 65535
        flags = 0x00
        flags |= disposal_method << 2
        if user_input:
            flags |= 0x02
        if has_transparent:
            flags |= 0x01
        self.write_extension_header(ExtensionLabel.GRAPHIC_CONTROL)
        self.write_extension_block(
            struct.pack("<BHB", flags, delay_time, transparent_color)
        )
        self.write_extension_trailer()

    def write_comment_extension(self, text):
        self.write_extension_header(ExtensionLabel.COMMENT)
        while len(text) > 0:
            self.write_extension_block(bytes(text[:255], "utf-8"))
            text = text[255:]
        self.write_extension_trailer()

    def write_application_extension(
        self, application_identifier, application_authentication_code, blocks
    ):
        assert len(application_identifier) == 8
        assert len(application_authentication_code) == 3
        self.write_application_extension_header(
            application_identifier, application_authentication_code
        )
        for block in blocks:
            self.write_extension_block(block)
        self.write_extension_trailer()

    def write_application_extension_header(
        self, application_identifier, application_authentication_code
    ):
        self.write_extension_header(ExtensionLabel.APPLICATION)
        self.write_extension_block(
            bytes(application_identifier + application_authentication_code, "ascii")
        )

    def write_netscape_extension(self, loop_count=-1, buffer_size=-1):
        assert loop_count < 65536
        assert buffer_size < 4294967296
        self.write_application_extension_header("NETSCAPE", "2.0")
        if loop_count >= 0:
            self.write_extension_block(struct.pack("<BH", 1, loop_count))
        if buffer_size >= 0:
            self.write_extension_block(struct.pack("<BI", 2, buffer_size))
        self.write_extension_trailer()

    def write_animexts_extension(self, loop_count=-1, buffer_size=-1):
        assert loop_count < 65536
        self.write_application_extension_header("ANIMEXTS", "1.0")
        if loop_count >= 0:
            self.write_extension_block(struct.pack("<BH", 1, loop_count))
        if buffer_size >= 0:
            self.write_extension_block(struct.pack("<BI", 2, buffer_size))
        self.write_extension_trailer()

    def write_xmp_data_extension(self, metadata):
        self.write_application_extension_header("XMP Data", "XMP")
        # This extension uses a clever hack to put raw XML in the file - it uses
        # a magic suffix that turns the XML text into valid GIF blocks.
        self.file.write(bytes(metadata, "utf-8"))
        self.file.write(b"\x01")
        for i in range(256):
            self.file.write(struct.pack("B", 0xFF - i))
        self.file.write(b"\x00")

    def write_icc_color_profile_extension(self, icc_profile):
        self.write_application_extension_header("ICCRGBG1", "012")
        offset = 0
        while offset < len(icc_profile):
            length = min(len(icc_profile) - offset, 255)
            self.write_extension_block(icc_profile[offset : offset + length])
            offset += length
        self.write_extension_trailer()

    def write_trailer(self):
        self.file.write(struct.pack("B", BlockType.TRAILER))
