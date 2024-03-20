##
## This file is part of the libsigrokdecode project.
##
## Copyright (C) 2016 Daniel Schulte <trilader@schroedingers-bit.net>
##
## This program is free software; you can redistribute it and/or modify
## it under the terms of the GNU General Public License as published by
## the Free Software Foundation; either version 2 of the License, or
## (at your option) any later version.
##
## This program is distributed in the hope that it will be useful,
## but WITHOUT ANY WARRANTY; without even the implied warranty of
## MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
## GNU General Public License for more details.
##
## You should have received a copy of the GNU General Public License
## along with this program; if not, see <http://www.gnu.org/licenses/>.
##

import sigrokdecode as srd
from collections import namedtuple

class Ann:
    BIT, START1, START2, DATA, WORD = range(5)

Bit = namedtuple('Bit', 'val ss es')

class Decoder(srd.Decoder):
    api_version = 3
    id = 'xt'
    name = 'XT'
    longname = 'XT'
    desc = 'XT keyboard interface.'
    license = 'gplv2+'
    inputs = ['logic']
    outputs = []
    tags = ['PC']
    channels = (
        {'id': 'clk', 'name': 'Clock', 'desc': 'Clock line'},
        {'id': 'data', 'name': 'Data', 'desc': 'Data line'},
    )
    annotations = (
        ('bit', 'Bit'),
        ('start-bit1', 'Start bit 1'),
        ('start-bit2', 'Start bit 2'),
        ('data-bit', 'Data bit'),
        ('word', 'Word'),
    )
    annotation_rows = (
        ('bits', 'Bits', (0,)),
        ('fields', 'Fields', (1, 2, 3, 4)),
    )
    options = (
        {'id': 'skip_ms', 'desc': 'Skip ms startup', 'default': 1000},
    )

    def __init__(self):
        self.reset()

    def reset(self):
        self.bits = []
        self.bitcount = 0

    def metadata(self, key, value):
        if key == srd.SRD_CONF_SAMPLERATE:
            self.samplerate = value

    def start(self):
        self.out_ann = self.register(srd.OUTPUT_ANN)

    def putb(self, bit, ann_idx):
        b = self.bits[bit]
        self.put(b.ss, b.es, self.out_ann, [ann_idx, [str(b.val)]])

    def putx(self, bit, ann):
        self.put(self.bits[bit].ss, self.bits[bit].es, self.out_ann, ann)

    def handle_bits(self, datapin):
        # Store individual bits and their start/end samplenumbers.
        self.bits.append(Bit(datapin, self.samplenum, self.samplenum))

        # Fix up end sample numbers of the bits.
        if self.bitcount > 0:
            b = self.bits[self.bitcount - 1]
            self.bits[self.bitcount - 1] = Bit(b.val, b.ss, self.samplenum)
        if self.bitcount == 10:
            self.bitwidth = self.bits[2].es - self.bits[3].es
            b = self.bits[-1]
            self.bits[-1] = Bit(b.val, b.ss, b.es + self.bitwidth)

        # Find all 11 bits. Start + 8 data + odd parity + stop.
        if self.bitcount < 10:
            self.bitcount += 1
            return

        # Extract data word.
        word = 0
        for i in range(8):
            word |= (self.bits[i + 2].val << i)

        # Emit annotations.
        for i in range(10):
            self.putb(i, Ann.BIT)
        self.putx(0, [Ann.START1, ['Start bit 1', 'Start1', 'S1']])
        self.putx(1, [Ann.START2, ['Start bit 2', 'Start2', 'S2']])
        self.put(self.bits[2].ss, self.bits[9].es, self.out_ann, [Ann.WORD,
                 ['Data: %02x' % word, 'D: %02x' % word, '%02x' % word]])

        self.bits, self.bitcount = [], 0

    def decode(self):
        self.wait({'skip': round((self.options['skip_ms']/1000) * self.samplerate)})
        while True:
            # Sample data bits on the falling clock edge (assume the device
            # is the transmitter). Expect the data byte transmission to end
            # at the rising clock edge. Cope with the absence of host activity.
            _, data_pin = self.wait({0: 'f'})
            self.handle_bits(data_pin)
            if self.bitcount == 1 + 1 + 8:
                _, data_pin = self.wait({0: 'r'})
                self.handle_bits(data_pin)
