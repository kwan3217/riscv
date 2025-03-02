"""
Implement the Risc-V 32-bit integer base instructions

Created: 6/11/24
"""
from dataclasses import dataclass
from typing import Callable, Mapping

from riscv.hart import InstructionSet, Hart, InstructionHandler, \
    IllegalInstruction
from riscv.memory import Memory


class Zihpm(InstructionSet):
    """
    Implement the CSRs (Control and Status Registers). This is a separate 12-bit address
    space which may be sparse. Access to these registers is restricted:
        * Reading from a nonexistent CSR causes an Illegal Instruction exception
        * Writing to a nonexistent CSR causes an Illegal Instruction exception
        * Reading or writing to a CSR without enough privilege causes an Illegal Instruction exception
        * Writing to a read-only CSR causes an Illegal Instruction exception
        * If a register is partially writable and partially read-only, writes to read-only bits are
          ignored and do not cause an exception. Simultaneous writes to writable bits are successful.
    This emulator will enforce these restrictions.
    """
    # This is solely the registers not attached to any particular privilege mode. As it turns out, there aren't any.
    csrs = {
        #  User Counter/Timers
        0xC00 + x: ("URO", f"hpmcounter{x}", "Performance-monitoring counter") for x in range(3, 32)
    }
    csrs32={
        0xC80 + x: ("URO", f"hpmcounter{x}h", "Upper 32 bits of hpmcounter{x}, RV32I only") for x in
        range(3, 32)} | {
    }
    def add_state(self,hart:Hart):
        hart.csr.add_regs(self.csrs)
        if hart.MLEN==32:
            hart.csr.add_regs(self.csrs32)
    def get_decode_table(self):
        return {}