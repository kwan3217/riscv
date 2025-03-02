"""
Sstc extension for supervisor-mode timer interrupts (priv ch19)

Created: 6/11/24
"""
from dataclasses import dataclass
from typing import Callable, Mapping

from riscv.hart import InstructionSet, Hart, InstructionHandler, \
    IllegalInstruction
from riscv.memory import Memory


class Sstc(InstructionSet):
    csrs = {
        #  User Counter/Timers
        0x14d: ("SRW", "stimecmp", "Supervisor timer register") for x in range(3, 32)
    }
    csrs32={
        0x15d: ("SRW", "stimecmph", "Upper 32 bits of stimecmp, RV32 only")
    }
    def add_state(self,hart:Hart):
        hart.csr.add_regs(self.csrs)
        if hart.XLEN==32:
            hart.csr.add_regs(self.csrs32)
    def get_decode_table(self):
        return {}