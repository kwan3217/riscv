"""
Implement the Risc-V 64-bit compressed instructions.
Any instructions in the C extention which work on more than 32 bits,
or only for 64 bits, go here. Anything which works only on longer
than 64 bits goes in c128.

Created: 6/24/24
"""
from dataclasses import dataclass
from typing import Callable, Mapping

from riscv.hart import InstructionSet
from riscv.bits import read_bitfield, signed
from riscv.i import I


class C64(InstructionSet):
    ins_exec={
        "+||| 543 mmm 76 yyy __": I.Store('C.SD',size=8),
    }
    def get_decode_table(self):
        return self.ins_exec


