"""
Implement the Risc-V 32-bit integer base instructions

Created: 6/11/24
"""
from dataclasses import dataclass
from struct import pack, unpack
from typing import Callable, Mapping

import numpy as np

from riscv.bits import read_bitfield, signed
from riscv.hart import InstructionSet, Hart, InstructionHandler, \
    IllegalInstruction, RVException, ExcCause
from riscv.memory import Memory, Misaligned


class FRegfile:
    # Register length --- the difference between RVF and RVD
    def __init__(self,FLEN=32):
        self._f=np.zeros((32,),dtype=np.float32 if FLEN==32 else np.float64)
        self.FLEN=FLEN
        self.intfmt="=I" if FLEN==32 else "=Q"
        self.fltfmt="=f" if FLEN==32 else "=d"
    def toint(self,v:float)->int:
        b = pack(self.fltfmt, v)
        v = unpack(self.intfmt, b)[0]
        return v
    def tofloat(self,v:int)->float:
        b = pack(self.intfmt, read_bitfield(v, self.FLEN - 1, 0))
        v = unpack(self.fltfmt, b)[0]
        return v
    def fmtfloat(self,v:float):
        return f"{float(v).hex()}, 0x{self.toint(v):0{self.FLEN//4}x}"
    def __getitem__(self,r):
        if type(r)==int:
            asint=False
        else:
            asint=r[1]
            r=r[0]
        v=self._f[r]
        print(f"   f{r:2}->{v:g} # ({self.fmtfloat(v)})")
        if asint:
            v=self.toint(v)
        return v
    def __setitem__(self,r,v):
        if type(v)==int:
            v=self.tofloat(v)
        print(f"   f{r:2}<-{v:g} # ({self.fmtfloat(v)})")
        #todo - Be careful about signed/unsigned, twos complement, sign extension, etc.
        self._f[r]=v


class F(InstructionSet):
    """

    """
    def add_state(self,hart:Hart):
        hart.f=FRegfile(FLEN=32)
    class Load(InstructionHandler):
        def __init__(self,name:str):
            self.name=name
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            addr = hart.x[p['rs1']]  # base
            addr += p['imm']
            try:
                val = hart.mem.load(4, addr,verbose=True,allow_misaligned=hart.allow_misaligned)
            except Misaligned:
                # Defer throwing the RVException to here, where the hart with its pc is available
                raise RVException(message=f"Misaligned load: Addr=0x{addr:08x}, width={self.size}",
                                  is_interrupt=False,
                                  cause=ExcCause.LOAD_ADDRESS_MISALIGNED,
                                  epc=hart.pc,
                                  tval=addr
                                  )
            hart.f[p['rd']] = val
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"{self.name:7s}x{p['rs1']:2},f{p['rd']:2},{p['imm']:12}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"f{p['rd']}=mem[{self.abi_regnames[p['rs1']][self.nameidx]}{'+' if p['imm'] >= 0 else ''}{p['imm']}]"
    class Store(InstructionHandler):
        def __init__(self,name:str):
            self.name=name
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            addr = hart.x[p['rs1']]  # base
            addr += p['imm']
            val=hart.f[p['rs2'],True]
            try:
                hart.mem.store(4, addr, val,allow_misaligned=hart.allow_misaligned)
            except Misaligned:
                # Defer throwing the RVException to here, where the hart with its pc is available
                raise RVException(message=f"Misaligned store: Addr=0x{addr:08x}, width=4",
                                  is_interrupt=False,
                                  cause=ExcCause.STORE_AMO_ADDRESS_MISALIGNED,
                                  epc=hart.pc,
                                  tval=addr
                                  )
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"{self.name:7s}x{p['rs1']:2},f{p['rs2']:2},{p['imm']:12}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"mem[{self.abi_regnames[p['rs1']][self.nameidx]}{'+' if p['imm'] >= 0 else ''}{p['imm']}]=f{p['rs2']}"
    class RegReg(InstructionHandler):
        def __init__(self, name: str, symbol: str, op: Callable[[Hart, float, float], float]):
            self.name = name
            self.symbol = symbol
            self.op = op
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            result = self.op(hart.f[p['rs1']], hart.f[p['rs2']])
            hart.f[p['rd']] = result
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"{self.name:7s}f{p['rd']:2},f{p['rs1']:2},f{p['rs2']:2}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"f{p['rd']}=f{p['rs1']}{self.symbol}f{p['rs2']}"
    ins_exec={
        '-BA9876543210   lllll _|_ ddddd ____|||':Load("FLW"),
        '-BA98765  zzzzz lllll _|_ 43210 _|__|||':Store("FSW"),
        ' sssss __ zzzzz lllll rrr ddddd |____||':'FMADD.S',
        ' sssss __ zzzzz lllll rrr ddddd |___|||':'FMSUB.S',
        ' sssss __ zzzzz lllll rrr ddddd |__|_||':'FNMSUB.S',
        ' sssss __ zzzzz lllll rrr ddddd |__||||':'FNMADD.S',
        ' _______  zzzzz lllll rrr ddddd |_|__||':RegReg('FADD.S','+',lambda rs1,rs2:rs1+rs2),
        ' ____|__  zzzzz lllll rrr ddddd |_|__||':'FSUB.S',
        ' ___|___  zzzzz lllll rrr ddddd |_|__||':'FMUL.S',
        ' ___||__  zzzzz lllll rrr ddddd |_|__||':'FDIV.S',

    }
    def get_decode_table(self):
        return self.ins_exec
