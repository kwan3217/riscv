"""
Test all the Foos! (And the Bars!)
"""
from subprocess import run

import pytest
from riscv.hart import sign_extend, signed, Hart, Memory, read_bitfield
from riscv.rv32i import RV32I
from riscv.zicsr import Zicsr


@pytest.mark.parametrize(
    "val,width,ref",
    [ (0x8,3,-8),
      (0x0001,15, 1),
      (0x1234,15,0x1234),
      (0x8000,15,-32768),
      (0xffff,15,-1),
      (0xffffffff,31,-1),
      (0xffffffffffffffff, 63, -1),
      (0xffffffffffffffffffffffffffffffff, 127, -1),
      ]
)
def test_signed(val,width,ref):
    assert signed(val,width)==ref

@pytest.mark.parametrize(
    "val,sign_bit,width,ref",
    [(0b11,1,4,0b1111),
     (0b1101,3,32,   0b11111111111111111111111111111101),
     (0b1101, 4, 32, 0b00000000000000000000000000001101)
]
)
def test_sign_extend(val,sign_bit,width,ref):
    assert sign_extend(val,sign_bit,width)==ref


class CheckSigMem(Memory):
    def __init__(self,infn:str,startaddr:int):
        self.startaddr=startaddr
        self.reference=[]
        with open(infn,"rt") as inf:
            for line in inf:
                self.reference.append(int(line.strip(),16))
    def store(self,width,baseaddr,value):
        """
        Stores a little-endian value of arbitrary width from the memory
        :param baseaddr:
        :param width:
        :return:
        """
        super().store(width,baseaddr,value)
        if baseaddr>=self.startaddr and value!=0:
            value=read_bitfield(value,width*8-1,0)
            index=(baseaddr-self.startaddr)//4
            print(f"Write to address 0x{baseaddr:08x}, value 0x{value:08x}, reference 0x{self.reference[index]:08x}")
            if value!=self.reference[index]:
                raise ValueError("Write doesn't match reference")


@pytest.mark.parametrize(
    "testname",
    ["ADD",
     "ADDI",
     "AND",
     "ANDI",
     "AUIPC",
     "BEQ",
     "BGE",
     "BGEU",
     "BLT",
     "BLTU",
     "BNE",
     "I-DELAY_SLOTS", # This one checks if the instruction *after* a jump is executed.
                      #  This can be an issue for pipelined processors, but this emulator
                      #  doesn't do anything pipelined. It should still pass.
     "I-ECALL",       #This tests ECALL by setting up a trap handler with a known side effect
                      #  and making sure that it gets executed. This emulator treats ECALL and
                      #  EBREAK as halt conditions, so the test will end (and pass) when the
                      #  first ECALL is hit. It doesn't really test the handler.
     "I-EBREAK",      # Same as above
     "I-ENDIANESS",   # Test endianess is as expected by reading whole words, half-words, and
                      # individual bytes, then writing each as a whole word to see if the upper
                      # bits got filled in as expected.
     "I-IO",          #Apparently a segment of memory is treated as memory-mapped IO to the "host".
                      # There is no such concept in this emulator, but the test passes anyway.
     pytest.param("I-MISALIGN_JMP",marks=pytest.mark.xfail(reason=
                        "This one fails because the misaligned jump is *not* trapped, but the misaligned "
                        " read doesn't result in a valid instruction.")),
     pytest.param("I-MISALIGN_LDST",marks=pytest.mark.xfail(reason=
                        "This one is failing, but it looks to me like the reference is bad. The code is "
                        " doing misaligned reads just fine, but the reference implies that the lower bits "
                        " of the misaligned read should be ignored IE alignment should be forced. ")),
     "I-NOP",           #Check that NOP doesn't interfere with the registers
     "I-RF_size",     # Verify that the register file is the correct size by exercising all 32 regs
     "I-RF_width",    # Verify that the register file is the correct width by storing 1-bits in both ends
     "I-RF_x0",       # Verify that x0 is hard-wired to 0 by using every opcode to try to change it
     "JAL",
     "JALR",
     "LB",
     "LBU",
     "LH",
     "LHU",
     "LUI",
     "LW",
     "OR",
     "ORI",
     "SB",
     "SH",
     "SLL",
     "SLLI",
     "SLT",
     "SLTIU",
     "SLTU",
     "SRA",
     "SRAI",
     "SRL",
     "SRLI",
     "SUB",
     "SW",
     "XOR",
     "XORI"
     ]
)
def test_imperas(testname:str,max_cycles:int=100000):
    """
    Execute the Imperas test cases

    See [https://github.com/riscv-ovpsim/imperas-riscv-tests]

    This is a collection of (presumably) carefully tested assembly programs,
    each of which exercises one of the instructions in several different ways.
    The test cases are chosen to maximize the chance of detecting a flaw in
    a hardware processor, so its cases would fail in such cases as stuck bits,
    broken wires, etc.

    Each test case consists of a .S file, which is compiled into a .elf, dumped
    into a .hex, then loaded into the emulator and executed. Each test writes its
    results to a block of emulated memory known as the "signature". Each test
    comes with a reference result of what should be in the signature block.

    The tests run by using an instrumented memory -- the memory loads the reference
    signature, then checks each time that the emulated program writes to the
    signature block and verifies that the block is the same as the signature.
    :param testname:
    :param max_cycles:
    :return:
    """
    # Run objdump to get the begin_signature symbol address
    result = run(
        f"riscv-none-embed-objdump -x imperas-riscv-tests/work/rv32i_m/I/{testname}-01.elf | grep '0 begin_signature'",
        capture_output=True, shell=True)
    assert len(result.stderr)==0,result.stderr
    sigstart = int(str(result.stdout, encoding='utf8')[0:8], 16)
    hart = Hart((RV32I(), Zicsr()), mem=CheckSigMem(
        f"imperas-riscv-tests/riscv-test-suite/rv32i_m/I/references/{testname}-01.reference_output", sigstart),
                breakpoints={0x8000_0198})
    hart.mem.stuff(f"imperas-riscv-tests/work/rv32i_m/I/{testname}-01.hex")
    hart.pc = 0x8000_0000
    cycles=0
    while cycles<max_cycles:
        hart.dump()
        try:
            hart.exec_one()
        except StopIteration:
            import traceback
            traceback.print_exc()
            break
        cycles+=1
    assert cycles<max_cycles,"Hit maximum cycles"

