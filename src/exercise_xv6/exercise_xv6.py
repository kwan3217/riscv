"""
Run XV6 on the Python RISC-V emulator

Created: 2025-02-26

"""
from glob import glob
from os.path import basename, isfile

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import ticker

from elf import read_elf, read_syms, invert_syms, symbolic_addr
from riscv.a import A
from riscv.f import F
from riscv.hart import Hart
from riscv.i import I
from riscv.i64 import I64
from riscv.c import C
from riscv.c32 import C32
from riscv.c64 import C64
from riscv.m import M
from riscv.m64 import M64
from riscv.memory import Bus, Memory, NumpyMemory
from riscv.modeM import ModeM
from riscv.modeS import ModeS
from riscv.sstc import Sstc
from riscv.uart import UART16550
from riscv.zicntr import Zicntr
from riscv.zifencei import Zifencei
from riscv.zicsr import Zicsr


def exercise_xv6():
    """
    Execute the riscof test cases

    :param testname:
    :param max_cycles:
    :return:
    """
    elffn=f"xv6/kernel/kernel"
    isas=(Zicsr(verbose=False), # Has to be before any other extensions define a CSR
          I(), I64(),
          M(), M64(),
          A(),
          F(),
          C(), C64(),
          Zicntr(),
          ModeM(),
          ModeS(),
          Sstc(),
          Zifencei())
    phys_mem_size=1*1024*1024
    memory=Bus({
        (0x8000_0000,0x8000_0000+phys_mem_size):NumpyMemory(size=phys_mem_size),
        (0x1000_0000,0x1000_0010):UART16550()
    },verbose=False)
    syms=read_syms(elffn)
    inv_syms=invert_syms(syms)
    hart = Hart(isas, XLEN=64, mem=memory, breakpoints={0x0000_0000},halts={0x0000_0000})
    sbreak=None
    #sbreak={0x1000_0000}
    if sbreak is not None:
        hart.mem.sbreak=sbreak
    hart.mem.stuff(read_elf(elffn))
    #hart.halts.add(syms["exit_cleanup"])
    print_syms=False
    hart.mem.fill(syms[".bss"],syms["end"],0)
    if print_syms:
        for sym,addr in sorted(syms.items(),key=lambda x:x[1]):
            print(f"{sym:32s}0x{addr:08x}")
    hart.pc = syms["_entry"]
    cycles=0
    pc_hist=[]
    hart.dverbose=False
    hart.step=False
    while True:
        try:
            hart.exec_one(inv_syms=inv_syms)
        except StopIteration:
            print(f"Halt at pc=0x{hart.pc:08x}")
            break
        cycles+=1
        if hart.step:
            pass
        if cycles%1000==0:
            print('.',end='')
            if cycles%10_000==0:
                print(' ',end='')
                if cycles%100_000==0:
                    print(f"{cycles:10d} pc=0x{hart.pc:08x}{symbolic_addr(hart.pc,inv_syms)}")
        pc_hist.append(hart.pc)
    plt.plot(np.array(pc_hist,dtype=np.int64)-0x8000_0000)
    axes = plt.gca()
    axes.get_yaxis().set_major_formatter(ticker.FuncFormatter(lambda x,pos:f"{int(x):04x}"))
    plt.show()


if __name__=="__main__":
    exercise_xv6()
