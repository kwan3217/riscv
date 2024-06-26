"""
Implement the Risc-V 64-bit multiplication and division instructions.
Any instructions in the M extention which work only on 64+ bit XLEN
go here.

Created: 6/26/24
"""
from dataclasses import dataclass
from typing import Callable, Mapping

from riscv.hart import InstructionSet
from riscv.bits import read_bitfield, signed
from riscv.i import I
from riscv.m import divrem


def divremw(hart:'Hart',rs1:int,rs2:int,is_signed:bool=False):
    """
    Perform the DIVW instruction

    From unprivileged 7.2:
    "DIVW and DIVUW are RV64 instructions that divide the lower 32 bits of rs1 by the lower 32
     bits of rs2, treating them as signed and unsigned integers respectively, placing the 32-bit quotient
     in rd, sign-extended to 64 bits. REMW and REMUW are RV64 instructions that provide the
     corresponding signed and unsigned remainder operations respectively. Both REMW and REMUW
     always sign-extend the 32-bit result to 64 bits, including on a divide by zero."

    This has just gotten too complicated to make a readable lambda, so it's getting broken out

    :param hart:
    :param rs1: Value of rs1 (numerator, dividend)  register
    :param rs2: Value of rs2 (denominator, divisor) register
    :return: tuple of quotient,remainder such that rs1=rs2*quotient+remainder, constrained to 32 bits.
    """
    rs1=read_bitfield(rs1,31,0)
    rs2=read_bitfield(rs2,31,0)
    if is_signed:
        rs1=signed(rs1,31)
        rs2=signed(rs2,31)
    # We tell divrem that the inputs are unsigned so it doesn't do its own conversion
    quo,rem=divrem(hart,rs1,rs2,signed=False)
    quo=hart.sign_extend(quo,31)
    rem=hart.sign_extend(rem,31)
    return quo,rem


class M64(InstructionSet):
    ins_exec={
        # From unpriv section 7.1
        # "MULW is an RV64 instruction that multiplies the lower 32 bits of the source registers, placing the
        #  sign-extension of the lower 32 bits of the result into the destination register.
        #  ---
        #  In RV64, MUL can be used to obtain the upper 32 bits of the 64-bit product, but signed arguments
        #  must be proper 32-bit signed values, whereas unsigned arguments must have their upper 32 bits
        #  clear. If the arguments are not known to be sign- or zero-extended, an alternative is to shift both
        #  arguments left by 32 bits, then use MULH[[S]U]."
        " ______| zzzzz lllll ___ ddddd _|||_||":I.RegReg('MULW','i32(i32(%s)*i32(%s))' ,lambda hart,rs1,rs2:signed(read_bitfield(rs1*rs2,31,0),31)),
        " ______| zzzzz lllll |__ ddddd _|||_||":I.RegReg('DIVW','i32(i32(%s)//i32(%s))',lambda hart,rs1,rs2:divremw(hart,rs1,rs2,is_signed=True)[0]),
        " ______| zzzzz lllll |_| ddddd _|||_||":I.RegReg('DIVUW','i32(u32(%s)//u32(%s))',lambda hart,rs1,rs2:divremw(hart,rs1,rs2,is_signed=False)[0]),
        " ______| zzzzz lllll ||_ ddddd _|||_||":I.RegReg('REMW','i32(i32(%s)%%i32(%s))' ,lambda hart,rs1,rs2:divremw(hart,rs1,rs2,is_signed=True)[1]),
        " ______| zzzzz lllll ||| ddddd _|||_||":I.RegReg('REMUW','i32(u32(%s)%%u32(%s))',lambda hart,rs1,rs2:divremw(hart,rs1,rs2,is_signed=False)[1]),
    }
    def get_decode_table(self):
        return self.ins_exec


