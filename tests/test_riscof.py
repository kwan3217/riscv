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

Set up the env files for the Spike emulator

```
riscof setup --dutname=spike
```

Change the config.ini so that both the reference and DUT
are Spike. The checked-in config.ini does this.

Get the architectural tests

```
riscof --verbose info arch-tests --clone
```

Generate the list of tests. We will generate as many tests
as possible, and select which ones we actually run at a
later time.


"""
from glob import glob
from os.path import basename, isfile

import pytest

from elf import read_elf, read_syms
from riscv.hart import Hart
from riscv.i import I
from riscv.i64 import I64
from riscv.c import C
from riscv.c32 import C32
from riscv.c64 import C64
from riscv.zifencei import Zifencei
from spike import spike_sig, check_sig
from riscv.zicsr import Zicsr


def get_test_name(ins:str):
    return ".".join(basename(ins).split(".")[0:-1])


def test_folder(XLEN:int,ext:str):
    return [(XLEN,ext,get_test_name(script)) for script in sorted(glob(f"riscof_work{XLEN}/rv{XLEN}i_m/{ext}/src/*.S"))]


alltests=(test_folder(32,"I")+
          test_folder(64,"I")+
          test_folder(32,"C")+
          test_folder(64,"C")+
          test_folder(32,"privilege")+
          test_folder(32,"Zifencei")+
          test_folder(64,"privilege")+
          test_folder(64,"Zifencei")
          )


@pytest.mark.parametrize(
    "XLEN,extname,testname",alltests
)
def test_riscof(XLEN:int,extname:str,testname:str,max_cycles:int=100000,breakpoints:set=None,sbreak:set=None):
    """
    Execute the riscof test cases

    See [https://github.com/riscv-ovpsim/imperas-riscv-tests]


    :param testname:
    :param max_cycles:
    :return:
    """
    elffn=f"riscof_work{XLEN}/rv{XLEN}i_m/{extname}/src/{testname}.S/dut/ref.elf"
    if XLEN==32:
        isas=(I(),        C(), C32(), Zicsr(), Zifencei())
    elif XLEN==64:
        isas=(I(), I64(), C(), C64(), Zicsr(), Zifencei())
    hart = Hart(isas, XLEN=XLEN, breakpoints=breakpoints)
    if sbreak is not None:
        hart.mem.sbreak=sbreak
    hart.mem.stuff(read_elf(elffn))
    syms=read_syms(elffn)
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
    sig=spike_sig(elffn,XLEN=XLEN)
    pass_sig=check_sig(hart.mem, sig, XLEN=XLEN)
    if not pass_sig:
        raise AssertionError("Bad signature")

