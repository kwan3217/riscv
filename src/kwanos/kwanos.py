"""

"""
from glob import glob
from os.path import basename, isfile

import pytest

from elf import read_elf, read_syms
from riscv.f import F
from riscv.hart import Hart
from riscv.i import I
from riscv.i64 import I64
from riscv.c import C
from riscv.c32 import C32
from riscv.c64 import C64
from riscv.m import M
from riscv.m64 import M64
from riscv.zifencei import Zifencei
from spike import spike_sig, check_sig
from riscv.zicsr import Zicsr


def main(max_cycles:int=100,breakpoints:set=None,sbreak:set=None):
    """
    Execute the riscof test cases

    :param testname:
    :param max_cycles:
    :return:
    """
    elffn=f"/home/jeppesen/workspace/kwanos/zig-out/bin/kwanos.elf"
    isas=(I(),        M(),        C(), C32(), Zicsr())
    hart = Hart(isas, XLEN=32, breakpoints=breakpoints,halts=None)
    if sbreak is not None:
        hart.mem.sbreak=sbreak
    hart.mem.stuff(read_elf(elffn))
    syms=read_syms(elffn)
    for sym,addr in syms.items():
        print(f"{sym:32s}0x{addr:08x}")
    hart.pc = 0
    cycles=0
    while cycles<max_cycles:
        #hart.dump()
        try:
            hart.exec_one()
        except StopIteration:
            print(f"Halt at pc=0x{hart.pc:08x}")
            break
        cycles+=1
    assert cycles<max_cycles,"Hit maximum cycles"


if __name__=="__main__":
    main()