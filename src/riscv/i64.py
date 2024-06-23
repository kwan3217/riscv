"""
Implement the Risc-V 64-bit integer base instructions.
Any instructions in the I extention which work on more than 32 bits,
or only for 64 bits, go here. Anything which works only on longer
than 64 bits goes in i128.

Created: 6/22/24
"""
from dataclasses import dataclass
from typing import Callable, Mapping

import riscv.bits
from riscv.hart import InstructionSet, Hart, InstructionHandler
from riscv.bits import bitmask, read_bitfield, signed
from riscv.i import I


class I64(I):
    ins_exec={
        "-BA9876543210  lllll ||_ ddddd _____||":I.Load('LWU',size=4,signed=False),
        "-BA9876543210  lllll _|| ddddd _____||":I.Load('LD',size=8,signed=True),
        "-BA98765 zzzzz lllll _|| 43210 _|___||":I.Store('SD',size=8),
        "+______5 43210 lllll __| ddddd __|__||":I.RegImmed("SLLI", "<<", lambda hart, rs1, imm: rs1 << imm),
        "+______5 43210 lllll |_| ddddd __|__||":I.RegImmed("SRLI", ">L>", lambda hart, rs1, imm: rs1 >> imm),
        "+_|____5 43210 lllll |_| ddddd __|__||":I.RegImmed("SRAI", ">A>", lambda hart, rs1, imm: hart.signed(rs1) >> imm),
        "-BA9876543210  lllll ___ ddddd __||_||":I.RegImmed("ADDIW", "i32(%s+%s)", lambda hart, rs1, imm: rs1 + imm,w=32),
        "+_______ 43210 lllll __| ddddd __||_||":I.RegImmed("SLLIW", "u32(b32(%s)<<%s)", lambda hart, rs1, imm: (rs1&0xFFFFFFFF) << imm,w=32),
        "+_______ 43210 lllll |_| ddddd __||_||":I.RegImmed("SRLIW", "u32(b32(%s)>L>%s)", lambda hart, rs1, imm: (rs1&0xFFFFFFFF) >> imm,w=32),
        "+_|_____ 43210 lllll |_| ddddd __||_||":I.RegImmed("SRAIW", "i32(i32(%s)>A>%s)", lambda hart, rs1, imm: signed(rs1&0xFFFFFFFF,31) >> imm,w=32),
        " _______ zzzzz lllll ___ ddddd _|||_||":I.RegReg("ADDW", "i32(%s+%s)", lambda hart, rs1, rs2: rs1 + rs2,w=32),

    }
    def get_decode_table(self):
        return self.ins_exec


