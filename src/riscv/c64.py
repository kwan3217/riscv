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
from riscv.i import I
from riscv.c import C


class C64(InstructionSet):
    ins_exec={
        "+_|| 543 mmm 76 eee __": I.Load('C.LD',size=8,signed=False),
        "+||| 543 mmm 76 yyy __": I.Store('C.SD',size=8),
        "-__| 5 fffff 43210  _|":I.RegImmed("C.ADDIW", "i32(%s+%s)", lambda hart, rs1, imm: rs1 + imm,w=32),
        "+|__ 5 __ ggg 43210 _|": C.C_RegImmed("C.SRLI", ">L>", lambda hart, rs1, imm: rs1 >> imm),  # Bit 12 is nzimm5, which must be 0 for RV32C
        "+|__ 5 _| ggg 43210 _|": C.C_RegImmed("C.SRAI", ">A>", lambda hart, rs1, imm: hart.signed(rs1) >> imm),  # Bit 12 is nzimm5, which must be 0 for RV32C
        " |__ | || ggg __ yyy _|":I.RegReg("C.SUBW", "i32(%s-%s)", lambda hart, rs1, rs2: rs1 - rs2,w=32),
        " |__ | || ggg _| yyy _|":I.RegReg("C.ADDW", "i32(%s+%s)", lambda hart, rs1, rs2: rs1 + rs2,w=32),
        "+___ 5 fffff 43210 |_": C.C_RegImmed("C.SLLI", "<<", lambda hart, rs1, imm: rs1 << imm),  # Bit 12 is nzimm5, which must be 0 for C32I
        "+_|| 5 ddddd 43876 |_": C.C_LoadSP("C.LDSP",size=8),
        "+||| 543876 zzzzz |_": C.C_StoreSP("C.SDSP",size=8),

    }
    def get_decode_table(self):
        return self.ins_exec


