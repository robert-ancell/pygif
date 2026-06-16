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

class LZWEncoder:
    def __init__ (self, file, min_code_size = 2, max_code_size = 12, start_with_clear = True, clear_on_max_width = True):
        self.file = file
        self.min_code_size = max (min_code_size, 2)
        self.max_code_size = max_code_size
        self.clear_on_max_width = clear_on_max_width

        assert (self.min_code_size < self.max_code_size)

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

        self.file.write (struct.pack ('B', self.min_code_size))

        if start_with_clear:
            self._write_code (self.clear_code)

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

            self._write_code (self.code_table[self.code[:-1]])
            self.code = self.code[-1:]

            # Use enough bits to place the next code
            if self.next_code == 2 ** self.code_size + 1:
                self.code_size += 1

            # Clear when out of codes
            if self.next_code == 2 ** self.max_code_size and self.clear_on_max_width:
                self.clear ()

    def clear (self):
        self._write_code (self.clear_code)
        self.code_table = {}
        for i in range (2 ** self.min_code_size):
            self.code_table[(i,)] = i
        self.code_size = self.min_code_size + 1
        self.next_code = self.eoi_code + 1

    def finish (self, send_eoi = True, extra_data = None):
        # Write last code in progress
        self._write_code (self.code_table[self.code])
        if send_eoi:
            self._write_code (self.eoi_code)
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

    def _write_code (self, code):
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

class LZWDecoder:
    def __init__ (self, min_code_size = 2, max_code_size = 12):
        assert (min_code_size < max_code_size)

        self.min_code_size = min_code_size
        self.max_code_size = max_code_size

        # Codes and values to output
        self.codes = []
        self.values = []
        self.n_used = 0

        # Code table
        self.clear_code = 2 ** min_code_size
        self.eoi_code = self.clear_code + 1
        self.code_table = []
        for i in range (2 ** min_code_size):
            self.code_table.append ((i,))
        self.code_table.append (self.clear_code)
        self.code_table.append (self.eoi_code)

        # Code currently being decoded
        self.code = 0                           # Current bits of code
        self.code_bits = 0                      # Current number of bits
        self.code_size = self.min_code_size + 1 # Required number of bits
        self.last_code = self.clear_code        # Previous code processed

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
                    self.code_size = self.min_code_size + 1
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
