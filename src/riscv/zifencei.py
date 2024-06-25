"""
Implement the Risc-V 32-bit integer base instructions

Created: 6/11/24
"""
from dataclasses import dataclass
from typing import Callable, Mapping

from riscv.hart import InstructionSet, Hart, InstructionHandler, \
    IllegalInstruction
from riscv.i import I
from riscv.memory import Memory


class Zifencei(InstructionSet):
    ins_exec={
        '+BA9876543210 lllll __| ddddd ___||||':I.Nop("FENCE.I","Instruction fence -- changes to data memory become executable"),
    }
    def get_decode_table(self):
        return self.ins_exec
