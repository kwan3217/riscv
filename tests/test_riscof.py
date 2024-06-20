"""
Use the riscof test cases

Created: 6/14/24

Instructions on getting riscof are from https://riscof.readthedocs.io/en/stable/installation.html

To get riscof:

Make sure there is a virtual environment, python 3.6 or greater. Either
use the Pycharm interpreter features, or do the following on cmdline.

We need the following packages:
* riscof # this pulls in *many* dependencies

```
cd riscv
python3 -m venv venv
source venv
pip install --upgrade pip
pip install riscof
```

Next, install the toolchain. We will install it in riscv/riscv-gnu-toolchain.
You need the following packages in Ubuntu:
* autoconf
* automake
* autotools-dev
* curl
* python3
* libmpc-dev
* libmpfr-dev
* libgmp-dev
* gawk
* build-essential
* bison
* flex
* texinfo
* gperf
* libtool
* patchutils
* bc
* zlib1g-dev
* libexpat-dev

```
cd riscv
sudo apt-get install autoconf automake autotools-dev curl python3 libmpc-dev \
      libmpfr-dev libgmp-dev gawk build-essential bison flex texinfo gperf libtool \
      patchutils bc zlib1g-dev libexpat-dev
```

Get the toolchain. We will have a riscv-gnu-toolchain folder and riscv-opcodes
folder. This will take quite a while as GCC is a *large* codebase. Even downloading
it will take some time, and compiling it will take more. We will use the multilib
instructions from https://github.com/riscv-collab/riscv-gnu-toolchain to enable
both 32-bit and 64-bit stuff. The compiler will be able to handle rv32gc and rv64gc,
which includes the following extensions:
 * (I)nteger
 * integer (M)ultiplication and division
 * (A)tomic operations
 * single-precision (F)loating point
 * (D)ouble-precision floating point
 * (C)ompressed instructions
It can compile binaries with any given subset of those extensions. It will
also support ABIs:
 * ilp32 - 32-bit soft-float, for use when F is excluded
 * ilp32d - 32-bit hard-float, so using the F registers
            for single and double precision
 * ilp32f - 32-bit single-precision hard-float but
            double-precision in memory, I think for when
            we are using F but not D and D is emulated
            in software
 * lp64 - (same as ilp32 but with 64-bit pointers)
 * lp64f - (same as ilp32f but with 64-bit pointers)
 * lp64d - (same as ilp32d but with 64-bit pointers)
```
git clone --recursive https://github.com/riscv/riscv-gnu-toolchain riscv-gnu-toolchain_src
git clone --recursive https://github.com/riscv/riscv-opcodes.git
cd riscv-gnu-toolchain_src
./configure --prefix=/full/path/to/riscv-gnu-toolchain --enable-multilib # This enables both rv32 and rv64
make -j25   # build using newlib, not linux. This is better for bare-metal, and the emulator acts like bare metal.
export PATH=$PATH:/full/path/to/riscv-gnu-toolchain/bin
```

Install a reference emulator. I think this is to generate reference signatures.
The choices are the SAIL emulator, which I haven't been able to get to work,
or Spike, which I am trying now. Spike appears to depend on the host toolchain,
not the riscv64-unknown-elf toolchain we just built.

```
sudo apt-get install device-tree-compiler
git clone https://github.com/riscv-software-src/riscv-isa-sim.git riscv-isa-sim_src
cd riscv-isa-sim_src
mkdir build
cd build
../configure --prefix=/full/path/to/riscv-isa-sim
make
make install # Don't need sudo since installing locally
export PATH=$PATH:/full/path/to/riscv-isa-sim
```


"""
from glob import glob
from os.path import basename

import pytest

from riscv.hart import Hart
from riscv.rv32c import RV32C
from riscv.rv32i import RV32I
from riscv.spike import spike_sig, check_sig


@pytest.mark.parametrize(
    "extname,testname",
    [("C","-".join(basename(ins).split("-")[0:-1])) for ins in sorted(glob("riscof_work/rv32i_m/C/src/*.S"))]+
    [("I","-".join(basename(ins).split("-")[0:-1])) for ins in sorted(glob("riscof_work/rv32i_m/I/src/*.S"))]
)
def test_riscof(extname:str,testname:str,max_cycles:int=100000):
    """
    Execute the riscof test cases

    See [https://github.com/riscv-ovpsim/imperas-riscv-tests]


    :param testname:
    :param max_cycles:
    :return:
    """
    elffn=f"riscof_work/rv32i_m/{extname}/src/{testname}-01.S/ref/ref.elf"
    #hart = Hart((RV32I(), Zicsr(),RV32C()))
    hart = Hart((RV32I(), ))
    syms=hart.mem.stuff_elf(elffn)
    hart.halts.add(syms["exit_cleanup"])
    for sym,addr in syms.items():
        print(f"{sym:32s}0x{addr:08x}")
    hart.pc = syms["rvtest_entry_point"]
    cycles=0
    while cycles<max_cycles:
        hart.dump()
        try:
            hart.exec_one()
        except StopIteration:
            print(f"Halt at pc=0x{hart.pc:08x}")
            break
        cycles+=1
    assert cycles<max_cycles,"Hit maximum cycles"
    # Check signature
    sig=spike_sig(elffn)
    assert check_sig(hart.mem, sig),"Bad signature"

