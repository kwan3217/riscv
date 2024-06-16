"""
Describe purpose of this script here

Created: 6/12/24
"""
import io
from enum import Enum
from subprocess import run
from typing import Iterable


def main():
    pass


if __name__ == "__main__":
    main()


def bitmask(bit1,bit0):
    """
    Make a bitmask.
    :param bit1: Highest bit to be set to 1. Note that this is
                 inclusive, unlike most other places like this
                 in Python.
    :param bit0: Lowest bit to be set to 1
    :return: Integer with all bits between bit0 and bit1 set to 1

    example:
       print("%b"%bitmask(6,0))
         1111111
       print("%b"%bitmask(11,7))
         0000111110000000

    """
    maskwidth=(bit1-bit0+1)
    return ((1<<maskwidth)-1)<<bit0


def read_bitfield(x, bit1, bit0):
    """
    Parse a bitfield out of a larger number
    :param bit1: Highest bit to be set to 1. Note that this is
                 inclusive, unlike most other places like this
                 in Python.
    :param bit0: Lowest bit to be set to 1
    :return: bits in the bit field, shifted right so that the
            least significant bit of the field falls on 0
    """
    return (x & bitmask(bit1,bit0))>>bit0


# Signed numbers
# Python's native int format is a signed number of effectively unlimited bits. This
# is in contrast to hardware ints, which are always a fixed number of bits. The bits
# have an implied encoding, either unsigned or twos-complement signed, depending
# on context. Unsigned values are the natural choice for bitfields and for values
# which are known to be positive. If negative values are in range, twos-complement
# encoding enables the same addition hardware to be used without caring whether the
# inputs are signed or unsigned.
#
# We therefore have two related but independent concepts:
# * Sign extension: To encode a twos-complement number of a given shorter bit length
#   as a number with a longer bit-length, use the MSb of the shorter number to fill
#   in the longer number. For instance, -2 is encoded in 4 bits as 0b1110, since
#   0b1110+0b0010=0b1_0000 and since the carry-out bit is dropped, we end up with
#   0b0000 as expected for -2+2=0. To sign-extend this value to a higher bit length,
#   we put the old number in the lower bits of a new value, then duplicate the highest
#   bit of the old number in all the higher bits. So for example, to sign-extend a
#   4-bit value encoding -2 to 8 bits, we initially have the number 0bxxxx_1110, where
#   the lower bits are from the original value, and the new bits are undetermined as
#   yet. The highest bit of -2=0b1110 is 0b1, so the new bits are *all* 0b1 and we end
#   up with 0b1111_1110. If the original was encoding a positive number such as
#   +2=0b0010, its highest bit would be 0 and the 8-bit equivalent would be
#   0b0000_0010.
# * Sign interpretation:
#   In Python, there is no such thing as a highest bit. Any twos-complement encoding
#   *can* be represented as a positive integer, including the encoding of negative
#   numbers. In order for an encoded value to be "imported" to Python so that its
#   normal arithmetic operations can be used, the twos-complement values must be
#   interpreted. In order to do this, we need to know where the sign bit is. For
#   hardware ints, this is always the MSb, but for Python we need to know which
#   bit is intended to be the MSb. To do sign interpretation, we then do a
#   twos-complement *decoding* and if the sign bit in the bitfield was lit, we
#   return a native Python number which is negative and matches the encoded
#   negative number.
def sign_extend(val, sign_bit, new_width):
    """
    Sign extend a number of a given bit-length
    :param val: twos-complement value to extend. This will be a
                *positive* number in Python even when a negative
                value is encoded.
    :param sign_bit: bit position of sign bit
    :param new_width: width of new number in bits
    :return: *positive* number with the sign bit repeated as many
             times as necessary to fill out the rest of the number
    """
    if read_bitfield(val, sign_bit, sign_bit) == 1:
        result=val
        for bit_pos in range(sign_bit+1,new_width):
            result|=1<<bit_pos
        return result
    else:
        return val


def signed(val,bit):
    """
    Interpret a twos-complement number of given length as a Python signed integer
    :param val: *positive* Python integer carrying the twos-complement
                encoding of a value
    :param bit: position of the sign bit, so for instance will be 11 to
                interpret a 12-bit signed number
    :return: Python integer of correct sign, IE the twos-complement encoding
             of a negative number (which is positive) will be interpreted as
             a negative number.
    """
    if read_bitfield(val,bit,bit)==1:
        min_negative=1<<bit
        negative_value=min_negative-read_bitfield(val,bit-1,0)
        return -negative_value
    return val


def read_bitfields(ins:int,fields:Iterable[tuple[int,int,int]],XLEN:int=None,is_signed:bool=False):
    """
    Read a value from multiple separate fields of a number

    :param ins: Instruction or other bitfield value
    :param fields: List of tuples, one for each field to extract. The tuple consists of (b1,b0,shift):
      * b1 is the MSb in the original bitfield
      * b0 is the LSb in the original bitfield
      * shift is the LSb in the final value, IE b0 of where this field will land.
    :param XLEN: If passed, sign-extend the number to this many bits.
    :param is_signed: If True, interpret the number as signed
    :return:

    """
    result=0
    signbit=0
    for b1,b0,shift in fields:
        result|=read_bitfield(ins,b1,b0)<<shift
        this_signbit=shift+(b1-b0)
        if this_signbit>signbit:
            signbit=this_signbit
    if XLEN is not None:
        result=sign_extend(result,signbit,XLEN)
        signbit=XLEN-1
    if is_signed:
        result=signed(result,signbit)
    return result


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
    pass


class InstructionInterpreter:
    """
    This class represents code which interprets an instruction.
    """
    def execute(self, ins:int, hart: 'Hart')->None:
        """
        Execute an instruction by computing how it changes a hart's state
        and then making that change to the given hart.

        :param ins: Coded instruction, in a single (unsigned) integer.
        :param hart: Hart to affect
        :raises: ValueError if the passed instruction isn't really handled
                 by this handler. Sometimes a table-driven instruction decoder
                 can't distinguish between two interpreters bases solely on
                 the bitfields it is looking at. In this case, it should
                 try one that matches, and if it raises a ValueError, then
                 it should go on to the next one etc.
        """
        raise NotImplementedError()
    def disasm(self, ins: int, XLEN: int)->str:
        """
        Disassemble an instruction into one assembly-language statement

        :param ins: Coded instruction, in a single (unsigned) integer
        :param XLEN: bit length to sign-extend immediates to
        :return: One line of assembly language. Intended to be compatible
                 with the GCC assembler.
        """
        raise NotImplementedError()
    def formula(self, ins: int, XLEN: int):
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
        ("s1"          , "saved0"   , "saved register 1"                      , True       ), #x9
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
        self.halts=halts
        self.XLEN=XLEN
        self.mem=mem
        self._pc=0
        self._pc_changed=False
        self.x=Regfile(XLEN=XLEN)
        self.ext={}
        for ext in self.exts:
            ext.add_state(self)
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
            print(f"x%02d({InstructionInterpreter.abi_regnames[i][0]:4s}):0x%0{self.XLEN//4}x   "%(i,x),end='')
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
        if aa:=read_bitfield(parcel,1,0)!=0b11:
            # Compressed instruction, 16 bits only
            return 2,parcel
        elif bbb:=read_bitfield(parcel,4,2)!=0b111:
            # 32-bit instruction
            return 4,self.mem.load(4,self.pc)
        else:
            # There is a proposal for instructions longer than 32-bits,
            # but it is not considered frozen and no instructions use it.
            raise ValueError("Instruction is longer than 32-bits, spec is not frozen")
    def exec_one(self):
        length,ins=self.fetch()
        handled=False
        self._pc_changed=False
        if self.pc in self.breakpoints:
            print(f"Breakpoint at pc=0x{self.pc:08x}")
        if self.pc in self.halts:
            raise StopIteration(f"Hit halt at pc=0x{self.pc:08x}")
        for i,ext in enumerate(self.exts):
            try:
                ext.interpret(self,ins)
                handled=True
                break
            except WrongInterpreter:
                continue
        if not handled:
            if read_bitfield(ins,1,0)==0b11:
                from riscv.rv32i import I
                raise ValueError(f"At pc=0x{self.pc:08x}, unhandled instruction {I(ins, self.XLEN, True)}")
            else:
                raise ValueError(f"At pc=0x{self.pc:08x}, unhandled compressed instruction "
                                 f"0b{read_bitfield(ins,15,13):03b}_{read_bitfield(ins,12,12):01b}_{read_bitfield(ins,11,7):05b}_{read_bitfield(ins,6,2):05b}_{read_bitfield(ins,1,0):02b}")
        else:
            if not self._pc_changed:
                self.pc += length


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


class Memory(dict):
    def __missing__(self,k):
        return 0
    def load(self,width,baseaddr):
        """
        Loads a little-endian value of arbitrary width from the memory
        :param baseaddr:
        :param width:
        :return:
        """
        result=0
        for ofs in range(width):
            try:
                b=self[baseaddr+ofs]
            except KeyError:
                b=0
            result |= b<<(ofs*8)
        return result
    def store(self,width,baseaddr,value):
        """
        Stores a little-endian value of arbitrary width from the memory
        :param baseaddr:
        :param width:
        :return:
        """
        for ofs in range(width):
            self[baseaddr+ofs]= read_bitfield(value, ofs * 8 + 7, ofs * 8)
    def stuff_hex(self, hexfn:str=None, hexf: io.TextIOBase =None):
        """
        Load an Intel Hex file into memory

        :param hexfn: Name of file to load
        :return:
        """
        hiaddr=0
        if hexf is None:
            hexf=open(hexfn,"rt")
            needs_close=True
        else:
            needs_close=False
        try:
            for line in hexf:
                line=line.strip()
                bytecount=int(line[1:3],16)
                loaddr=int(line[3:7],16)
                rtype=int(line[7:9],16)
                stored_cksum=int(line[bytecount*2+9:bytecount*2+9+2],16)
                if rtype==0:
                    data = bytes([int(line[i * 2 + 9:i * 2 + 9 + 2], 16) for i in range(bytecount)])
                    # Data, stuff into memory at given addr
                    for i,b in enumerate(data):
                        addr=loaddr+hiaddr*0x10000+i
                        self[addr]=b
                elif rtype==1:
                    # End of file record
                    break
                elif rtype==4:
                    # Extended linear address (upper 16 bits of 32-bit address)
                    hiaddr=int(line[9:13],16)
        finally:
            if needs_close:
                hexf.close()
    def stuff_elf(self,elffn:str)->dict[str,int]:
        """
        Load an ELF image into memory

        :param elffn:
        :return: dict of symbols. Key is string name of symbol, val is parsed address
        """
        result = run(
            f"riscv64-unknown-elf-objcopy -O ihex {elffn} /dev/stdout",
            capture_output=True, shell=True)
        if len(result.stderr)!=0:
            raise RuntimeError(result.stderr)
        with io.TextIOWrapper(io.BytesIO(result.stdout)) as hexf:
            self.stuff_hex(hexf=hexf)
    def dump(self,addr0,addr1):
        for i in range(0,addr1-addr0,16):
            print(f"{addr0+i:08x}  ",end='')
            for j in range(16):
                if addr0+i+j in self:
                    val=f"{self[addr0+i+j]:02x}"
                else:
                    val="xx"
                if addr0+i+j<addr1:
                    print(val,end='')
                else:
                    print('  ',end='')
                if j%4==3:
                    print(" ",end='')
            print(" ",end='')
            for j in range(16):
                if addr0+i+j<addr1:
                    if addr0 + i + j not in self:
                        val = '_'
                    elif self[addr0+i+j]>=32 and self[addr0+i+j]<=127:
                        val=chr(self[addr0+i+j])
                    else:
                        val='.'
                    print(val, end='')
                else:
                    print(' ',end='')
            print()
