"""
Implement the Risc-V 32-bit integer base instructions

Created: 6/11/24
"""
from dataclasses import dataclass
from typing import Callable, Mapping

from riscv.hart import InstructionSet, Hart, InstructionHandler, \
    IllegalInstruction
from riscv.memory import Memory


class Zicntr(InstructionSet):
    csrs = {
        #  User Counter/Timers
        0xC00: ("URO", "cycle", "Cycle counter for RDCYCLE instruction"),
        0xC01: ("URO", "time", "Timer for RDTIME instruction",None,None,lambda hart,val:val+1),
        0xC02: ("URO", "instret", "Instructions-retired counter for RDINSTRET instruction")
    }
    csrs32={
        0xC80: ("URO", "cycleh", "Upper 32 bits of cycle, RV32I only"),
        0xC81: ("URO", "timeh", "Upper 32 bits of time, RV32I only"),
        0xC82: ("URO", "instreth", "Upper 32 bits of instret, RV32I only"),
    }
    def add_state(self,hart:Hart):
        hart.csr.add_regs(self.csrs)
        if hart.XLEN==32:
            hart.csr.add_regs(self.csrs32)
    def get_decode_table(self):
        return {}