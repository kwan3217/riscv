"""
Describe purpose of this script here

Created: 6/12/24
"""
from enum import Enum
from typing import Iterable, Mapping

from riscv.bits import bitmask, read_bitfield, sign_extend, signed
from riscv.decode import compile_encodings, decode
from riscv.memory import Memory


def main():
    from test_riscof import test_riscof
    test_riscof("C","cjalr")


if __name__ == "__main__":
    main()


class Opcode(Enum):
    LOAD     =0b00000
    LOAD_FP  =0b00001
    custom0  =0b00010
    MISC_MEM =0b00011
    OP_IMM   =0b00100
    AUIPC    =0b00101
    OP_IMM_32=0b00110
    b48      =0b00111

    STORE    =0b01000
    STORE_FP =0b01001
    custom1  =0b01010
    AMO      =0b01011
    OP       =0b01100
    LUI      =0b01101
    OP_32    =0b01110
    b64      =0b01111

    MADD     =0b10000
    MSUB     =0b10001
    NMSUB    =0b10010
    NMADD    =0b10011
    OP_FP    =0b10100
    reserved0=0b10101
    custom2  =0b10110
    b48_     =0b10111

    BRANCH   =0b11000
    JALR     =0b11001
    reserved1=0b11010
    JAL      =0b11011
    SYSTEM   =0b11100
    reserved2=0b11101
    custom3  =0b11110
    b80      =0b11111


class WrongInterpreter(ValueError):
    """
    Raise this if the given bit pattern reaches an interpreter,
    but doesn't match this interpreter. If it's raised, no other
    instruction in the same instruction set extension is given
    a chance, but other extensions will be given a chance. Raise
    this before any changes to the hart or memory state are made.
    Usually, we will do this for "reserved" instruction encodings
    to give another instruction set a chance to use that encoding.
    """
    pass


class IntCause(Enum):
    # Software interrupts. Trigger this by writing the "software interrupt pending"
    # (xSIP) bit in the correct CSR (see privileged section 4.1.5)
    USER_SOFTWARE_INTERRUPT = 0
    SUPERVISOR_SOFTWARE_INTERRUPT = 1
    # HYPERVISOR_SOFTWARE_INTERRUPT=2  #Seem to be leaving slots for a layer in between M and S
    MACHINE_SOFTWARE_INTERRUPT = 3
    # Timer interrupts. These are intended to be triggered on a regular time basis
    # as described in privileged section 3.1.10
    USER_TIMER_INTERRUPT=4
    SUPERVISOR_TIMER_INTERRUPT=5
    #HYPERVISOR_TIMER_INTERRUPT=6
    MACHINE_TIMER_INTERRUPT=7
    # External interrupts, triggered by an external source like an interrupt pin
    USER_EXTERNAL_INTERRUPT=8
    SUPERVISOR_EXTERNAL_INTERRUPT=9
    #HYPERVISOR_EXTERNAL_INTERRUPT=10
    MACHINE_EXTERNAL_INTERRUPT=11
    # 12-15 are reserved for future standard use
    # >=16 are reserved for plaform use (IE won't be used by future standards)


class ExcCause(Enum):
    INSTRUCTION_ADDRESS_MISALIGNED=0
    INSTRUCTION_ACCESS_FAULT=1
    ILLEGAL_INSTRUCTION=2
    BREAKPOINT=3
    LOAD_ADDRESS_MISALIGNED=4
    LOAD_ACCESS_FAULT=5
    STORE_AMO_ADDRESS_MISALIGNED=6
    STORE_AMO_ACCESS_FAULT=7
    ECALL_FROM_U_MODE=8
    ECALL_FROM_S_MODE=9
    #ECALL_FROM_H_MODE=10
    ECALL_FROM_M_MODE=11
    INSTRUCTION_PAGE_FAULT=12
    LOAD_PAGE_FAULT=13
    #14 is reserved for future standard use
    STORE_AMO_PAGE_FAULT=15
    #16-23 reserved for future standard use
    #24-31 reserved for custom use
    #32-47 reserved for future standard use
    #48-63 reserved for custom use
    #>=64 reserved for future standard use


class RVException(Exception):
    """
    This is an architecture exception as defined in the architecture
    manuals. If an instruction raises this exception, it must do so
    *before* causing any observable state change to the hart, IE
    register write, CSR read/write, or memory read/write.

    The Python code around the emulator is the execution environment.
    When it catches this exception, it should do everything that an EEI
    should do, like set CSRs with current pc, set cause registers, etc
    and then stuff the pc with the value from the correct CSR. It can
    then let the emulated hart continue to run.
    """
    def __init__(self,*,message:str=None,is_interrupt:bool,cause:int,epc:int,mtval:int=0):
        super().__init__(message)
        self.is_interrupt=is_interrupt
        self.cause=cause
        self.epc=epc
        self.mtval=mtval
    def __str__(self):
        try:
            if self.is_interrupt:
                cause=repr(IntCause(self.cause))
            else:
                cause=repr(ExcCause(self.cause))
        except Exception:
            cause=f"Unknown cause {self.cause}"
        return f"{self.args[0]} at pc=0x{self.epc:08x}, {'interrupt' if self.is_interrupt else 'exception'} {cause=}"


class IllegalInstruction(RVException):
    """
    Raise this if the given bit pattern is resolved to the correct
    instruction, but either the encoding will never be valid (for
    instance an all-zero instruction is specified to be illegal)
    or something goes wrong while executing the instruction. Eventually
    an illegal instruction will do whatever exception is specified
    in the privileged architecture manual. For now we will just
    not handle the exception and let Python handle the failure.
    """
    def __init(self,message:str=None):
        super().__init__(message=message,is_interrupt=False,cause=int(ExcCause.ILLEGAL_INSTRUCTION))


class InstructionHandler:
    """
    This class represents code which interprets an instruction.
    """
    def execute(self, p: Mapping[str,int], hart: 'Hart')->None:
        """
        Execute an instruction by computing how it changes a hart's state
        and then making that change to the given hart.

        :param p: Variable fields of the instruction, such as rs1, rd, imm,
                  etc. Bits which are purely needed to decode the instruction
                  such as opcode have already been used, and are not included.
        :param hart: Hart to affect
        :raises: ValueError if the passed instruction isn't really handled
                 by this handler. Sometimes a table-driven instruction decoder
                 can't distinguish between two interpreters bases solely on
                 the bitfields it is looking at. In this case, it should
                 try one that matches, and if it raises a ValueError, then
                 it should go on to the next one etc.
        """
        raise NotImplementedError()
    def disasm(self, p: Mapping[str,int], XLEN: int)->str:
        """
        Disassemble an instruction into one assembly-language statement

        :param ins: Coded instruction, in a single (unsigned) integer
        :param XLEN: bit length to sign-extend immediates to
        :return: One line of assembly language. Intended to be compatible
                 with the GCC assembler.
        """
        raise NotImplementedError()
    def formula(self, p: Mapping[str,int], XLEN: int):
        """
        Disassemble an instruction into a line of C-like code. This is
        easier for a human to interpret since we don't have to remember
        what each mnemonic means or the order of the operands.

        :param ins: Coded instruction, in a single (unsigned) integer
        :param XLEN: bit length to sign-extend immediates to
        :return: One line of C-like pseudocode. Intended for human
                 intepretation, so not required to be machine-readable.
        """
        raise NotImplementedError()
    nameidx=1
    abi_regnames=[
        # ABI            longer ABI  Use by convention                         Preserved?    Register
        ("zero"        , "zero"     , "hardwired to 0, ignores writes"        , None       ), #x0
        ("ra"          , "retaddr"  , "return address for jumps"              , False      ), #x1
        ("sp"          , "stackptr" , "stack pointer"                         , True       ), #x2
        ("gp"          , "globalptr", "global pointer"                        , None       ), #x3
        ("tp"          , "threadptr", "thread pointer"                        , None       ), #x4
        ("t0"          , "temp0"    , "temporary register 0"                  , False      ), #x5
        ("t1"          , "temp1"    , "temporary register 1"                  , False      ), #x6
        ("t2"          , "temp2"    , "temporary register 2"                  , False      ), #x7
        ("fp"          , "frameptr" , "saved register 0 _or_ frame pointer"   , True       ), #x8
        ("s1"          , "saved1"   , "saved register 1"                      , True       ), #x9
        ("a0"          , "arg0"     , "return value _or_ function argument 0" , False      ), #x10
        ("a1"          , "arg1"     , "return value _or_ function argument 1" , False      ), #x11
        ("a2"          , "arg2"     , "function argument 2"                   , False      ), #x12
        ("a3"          , "arg3"     , "function argument 3"                   , False      ), #x13
        ("a4"          , "arg4"     , "function argument 4"                   , False      ), #x14
        ("a5"          , "arg5"     , "function argument 5"                   , False      ), #x15
        ("a6"          , "arg6"     , "function argument 6"                   , False      ), #x16
        ("a7"          , "arg7"     , "function argument 7"                   , False      ), #x17
        ("s2"          , "saved2"   , "saved register 2"                      , True       ), #x18
        ("s3"          , "saved3"   , "saved register 3"                      , True       ), #x19
        ("s4"          , "saved4"   , "saved register 4"                      , True       ), #x20
        ("s5"          , "saved5"   , "saved register 5"                      , True       ), #x21
        ("s6"          , "saved6"   , "saved register 6"                      , True       ), #x22
        ("s7"          , "saved7"   , "saved register 7"                      , True       ), #x23
        ("s8"          , "saved8"   , "saved register 8"                      , True       ), #x24
        ("s9"          , "saved9"   , "saved register 9"                      , True       ), #x25
        ("s10"         , "saved10"  , "saved register 10"                     , True       ), #x26
        ("s11"         , "saved11"  , "saved register 11"                     , True       ), #x27
        ("t3"          , "temp3"    , "temporary register 3"                  , False      ), #x28
        ("t4"          , "temp4"    , "temporary register 4"                  , False      ), #x29
        ("t5"          , "temp5"    , "temporary register 5"                  , False      ), #x30
        ("t6"          , "temp6"    , "temporary register 6"                  , False      ), #x31
        ("pc"          , "program counter"                       , None       ), #pc
]


class Hart:
    """
    Represent a (Har)dware (t)hread.
    """
    def __init__(self,exts:Iterable['InstructionSet'],mem=None,XLEN=32,breakpoints:set=None,halts:set=None):
        self.exts=exts
        if mem is None:
            mem=Memory()
        if breakpoints is None:
            breakpoints=set()
        self.breakpoints=breakpoints
        if halts is None:
            halts=set()
        self.halts=halts
        self.XLEN=XLEN
        self.mem=mem
        self._pc=0
        self._pc_changed=False
        self.x=Regfile(XLEN=XLEN)
        self.decode_table={}
        for ext in self.exts:
            ext_decode_table=ext.get_decode_table()
            self.decode_table.update(ext_decode_table)
            ext.add_state(self)
        self.decode_table=compile_encodings(self.decode_table)
    def sign_extend(self,v,bit):
        return sign_extend(v, bit, self.XLEN)
    def signed(self,v):
        return signed(v, self.XLEN - 1)
    def set_pc(self,v):
        self._pc= read_bitfield(v, self.XLEN - 1, 0)
        self._pc_changed=True
    def get_pc(self):
        return self._pc
    def dump(self):
        for i,x in enumerate(self.x._x):
            print(f"x%02d({InstructionHandler.abi_regnames[i][0]:4s}):0x%0{self.XLEN // 4}x   " % (i, x), end='')
            if i%4==3:
                print()
    pc=property(get_pc,set_pc)
    def fetch(self):
        """
        Fetch one instruction. We can tell how many bytes long the instruction is
        purely from the first few bits of the instruction, as shown in figure 1.1
        :return: tuple of length of instruction and unsigned int with the entire
                 instruction. This is Python, so we get an int with an unlimited
                 bit-length, enough for any instruction.
        """
        # Read the first 16-bit parcel of the instruction, and figure out length from it
        parcel=self.mem.load(2,self.pc)
        if aa:= read_bitfield(parcel, 1, 0) != 0b11:
            # Compressed instruction, 16 bits only
            return 2,parcel
        elif bbb:= read_bitfield(parcel, 4, 2) != 0b111:
            # 32-bit instruction
            return 4,self.mem.load(4,self.pc)
        else:
            # There is a proposal for instructions longer than 32-bits,
            # but it is not considered frozen and no instructions use it.
            raise IllegalInstruction("Instruction is longer than 32-bits, spec is not frozen")
    def exec_one(self):
        self._pc_changed=False
        if self.pc in self.breakpoints:
            print(f"Breakpoint at pc=0x{self.pc:08x}")
        if self.pc in self.halts:
            raise StopIteration(f"Hit halt at pc=0x{self.pc:08x}")
        length,ins=self.fetch()
        fields,handler=decode(ins, self.decode_table)
        if handler is not None:
            if type(handler) is str:
                raise ValueError(f"Unimplemented instruction {handler}")
            print(f"{self.pc:08x} -- {ins:0{length*2}x}      {handler.disasm(fields, self.XLEN)}  # {handler.formula(fields, self.XLEN)}")
            handler.execute(fields,self)
            if not self._pc_changed:
                self.pc += length
        else:
            if read_bitfield(ins, 1, 0)==0b11:
                from riscv.rv32i import I
                raise IllegalInstruction(f"At pc=0x{self.pc:08x}, unhandled instruction {I(ins, self.XLEN, True)}")
            else:
                raise IllegalInstruction(f"At pc=0x{self.pc:08x}, unhandled compressed instruction "
                                 f"0b{read_bitfield(ins, 15, 13):03b}_{read_bitfield(ins, 12, 12):01b}_{read_bitfield(ins, 11, 7):05b}_{read_bitfield(ins, 6, 2):05b}_{read_bitfield(ins, 1, 0):02b}")


class StateUpdate:
    def __init__(self):
        self.dx={}
        self.dm={}
    def commit(self,hart:Hart):
        for (i,val) in self.dx.items():
            hart.x[i]=val


class InstructionSet:
    def add_state(self,hart:Hart):
        pass
    def interpret(self,hart:Hart,ins:int)->bool:
        return False


class Regfile:
    # Register length --- the difference between RV32I and RV64I
    def __init__(self,XLEN=32):
        self._x=[0]*32
        self.XLEN=XLEN
    def __getitem__(self,r):
        if r==0:
            return 0
        return self._x[r]
    def __setitem__(self,r,v):
        if r==0:
            return
        #todo - Be careful about signed/unsigned, twos complement, sign extension, etc.
        self._x[r]= v & bitmask(self.XLEN - 1, 0)


