"""
Implement the Risc-V 32-bit compressed instructions.
Any instructions in the C extention which work specifically on
32 bits, go here.

Created: 6/24/24
"""
from dataclasses import dataclass
from typing import Callable, Mapping

from riscv.hart import InstructionSet, InstructionHandler, Hart
from riscv.bits import read_bitfield, signed, bitmask
from riscv.i import I
from riscv.c import C


class C32(InstructionSet):
    class C_JAL(InstructionHandler):
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            hart.x[1] = hart.pc+2
            target = hart.pc
            target += p['imm']
            target &= bitmask(31, 1)
            hart.pc = target
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"C.JAL    {p['imm']:12}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"{self.abi_regnames[1][self.nameidx]}=pc+2, pc=pc{'+' if p['imm'] >= 0 else ''}{p['imm']}"
    ins_exec={
        "-__| B498A673215 _|": C_JAL(),  # Note that this overlaps C.ADDIW in C64.
    }
    def get_decode_table(self):
        return self.ins_exec


