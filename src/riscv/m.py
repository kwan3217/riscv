"""
Implement the Risc-V 32-bit multiplication and division instructions.
Any instructions in the M extention which work on any XLEN go here.

Created: 6/22/24
"""
from dataclasses import dataclass
from typing import Callable, Mapping

from riscv.hart import InstructionSet
from riscv.bits import read_bitfield, signed
from riscv.i import I


def divrem(hart:'Hart',rs1:int,rs2:int,signed:bool):
    if signed:
        rs1=hart.signed(rs1) # dividend (numerator)
        rs2=hart.signed(rs2) # divisor  (denominator)
    if rs2==0:
        return -1,rs1
    div=rs1//rs2
    rem=rs1%rs2
    if rem*rs1<0:
        #result and dividend are required to have the same sign. if not, fix it.
        div+=1
        rem-=rs2
    return div,rem


class M(InstructionSet):
    ins_exec={
        " ______| zzzzz lllll ___ ddddd _||__||":I.RegReg('MUL','*' ,lambda hart,rs1,rs2:hart.signed(rs1)*hart.signed(rs2)),
        " ______| zzzzz lllll __| ddddd _||__||":I.RegReg('MULH','(signed(%s)*signed(%s))>A>XLEN' ,lambda hart,rs1,rs2:(hart.signed(rs1)*hart.signed(rs2))>>hart.XLEN),
        " ______| zzzzz lllll _|_ ddddd _||__||":I.RegReg('MULHSU','(signed(%s)*%s)>A>XLEN' ,lambda hart,rs1,rs2:(hart.signed(rs1)*rs2)>>hart.XLEN),
        " ______| zzzzz lllll _|| ddddd _||__||":I.RegReg('MULHU','(%s*%s)>A>XLEN' ,lambda hart,rs1,rs2:(rs1*rs2)>>hart.XLEN),
        " ______| zzzzz lllll |__ ddddd _||__||":I.RegReg('DIV','signed(%s)//signed(%s)',lambda hart,rs1,rs2:divrem(hart,rs1,rs2,True)[0]),
        " ______| zzzzz lllll |_| ddddd _||__||":I.RegReg('DIVU','//',lambda hart,rs1,rs2:divrem(hart,rs1,rs2,False)[0]),
        " ______| zzzzz lllll ||_ ddddd _||__||":I.RegReg('REM','signed(%s)%%signed(%s)' ,lambda hart,rs1,rs2:divrem(hart,rs1,rs2,True)[1]),
        " ______| zzzzz lllll ||| ddddd _||__||":I.RegReg('REMU','%',lambda hart,rs1,rs2:divrem(hart,rs1,rs2,False)[1]),
    }
    def get_decode_table(self):
        return self.ins_exec


