"""

"""

from dataclasses import dataclass
from enum import Enum

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


def sign_extend(val, sign_bit, new_width):
    """
    Sign extend a number of a given bit-length
    :param val: value to extend
    :param sign_bit: bit position of sign bit
    :param new_width: width of new number in bits
    :return: *positive* number with the sign bit repeated as many times as necessary to fill out the rest of the number

    This is a bit weird because of how Python handles ints as having
    an unlimited bit length.
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
    :param val:
    :param bit: position of the sign bit, so for instance will be 11 to interpret a 12-bit signed number
    :return:
    """
    if read_bitfield(val,bit,bit)==1:
        min_negative=1<<bit
        negative_value=min_negative-read_bitfield(val,bit-1,0)
        return -negative_value
    return val

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
        self._x[r]=v & bitmask(self.XLEN-1,0)

class Memory:
    def __init__(self):
        self.mem={}
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
                b=self.mem[baseaddr+ofs]
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
            self.mem[baseaddr+ofs]=read_bitfield(value,ofs*8+7,ofs*8)
    def dump(self,addr0,addr1):
        for i in range(0,addr1-addr0,16):
            print(f"{addr0+i:08x}  ",end='')
            for j in range(16):
                if addr0+i+j<addr1:
                    print(f"{self.mem[addr0+i+j]:02x}",end='')
                else:
                    print('  ',end='')
                if j%4==3:
                    print(" ",end='')
            print(" ",end='')
            for j in range(16):
                if addr0+i+j<addr1:
                    if self.mem[addr0+i+j]>=32 and self.mem[addr0+i+j]<=127:
                        print(chr(self.mem[addr0+i+j]),end='')
                    else:
                        print('.', end='')
                else:
                    print(' ',end='')
            print()



class Hart:
    """
    Represent a (Har)dware (t)hread.
    """
    def __init__(self,mem=None,XLEN=32):
        if mem is None:
            mem=Memory()
        self.XLEN=XLEN
        self.mem=mem
        self.pc=0
        self.x=Regfile(XLEN=XLEN)
    def sign_extend(self,v,bit):
        return sign_extend(v,bit,self.XLEN)

@dataclass
class ParsedInstruction:
    opcode:int=None
    rd:int=None
    funct3:int=None
    rs1:int=None
    rs2:int=None
    funct7:int=None
    imm:int=None
    def __str__(self):
        result='ParsedInstruction('
        result+=f'opcode='+(f'0b{self.opcode:07b},' if self.opcode is not None else "None,")
        result+=f'rd='+(f'{self.rd},' if self.rd is not None else "None,")
        result+=f'funct3='+(f'0b{self.funct3:03b},' if self.funct3 is not None else "None,")
        result+=f'rs1='+(f'{self.rs1},' if self.rs1 is not None else "None,")
        result+=f'rs2='+(f'{self.rs2},' if self.rs2 is not None else "None,")
        result+=f'funct7='+(f'0b{self.funct7:07b},' if self.funct7 is not None else "None,")
        result+=f'imm='+(f'{self.imm})' if self.imm is not None else "None)")
        return result
    def R(self,ins):
        """
        Parse instruction as if it's an R-type
        :param ins:
        :return:
        """
        self.opcode=read_bitfield(ins,6,0)
        self.rd = read_bitfield(ins, 11, 7)
        self.funct3 = read_bitfield(ins, 14, 12)
        self.rs1 = read_bitfield(ins, 19, 15)
        self.rs2 = read_bitfield(ins, 24, 20)
        self.funct7 = read_bitfield(ins, 31, 25)
    def I(self):
        self.imm=self.funct7<<5 |self.rs2
        self.funct7=None
        self.rs2=None
    def S(self):
        self.imm=self.funct7<<5 |self.rd
        self.funct7=None
        self.rd=None
    def U(self):
        self.imm=self.funct7<<25 |self.rs2<<20|self.rs1<<15|self.funct3<<12
        self.funct7=None
        self.rs2=None
        self.rs1=None
        self.funct3=None
    def B(self):
        self.imm=(read_bitfield(self.funct7,6,6)<<12 | #imm[12]
                  read_bitfield(self.rd,0,0)<<11 |     #imm[11]
                  read_bitfield(self.funct7,5,0)<<5 |  #imm[10:5]
                  read_bitfield(self.rd,4,1)<<1)       #imm[4:1]
    def J(self):
        self.imm=(read_bitfield(self.funct7,6,6)<<20 | #imm[20]
                  (self.rs1<<3 | self.funct3)<<12 |     #imm[19:12]
                  read_bitfield(self.rs2,0,0)<<11 |  #imm[11]
                  ((read_bitfield(self.funct7,5,0)<<4) | read_bitfield(self.rs2,4,1))<<1)       #imm[10:1]



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

    BRANCH   =0b10000
    JALR     =0b10001
    reserved1=0b10010
    JAL      =0b10011
    SYSTEM   =0b10100
    reserved2=0b10101
    custom3  =0b10110
    b80      =0b10111

def Undefined(hart:Hart,parsed_ins:ParsedInstruction)->None:
    raise ValueError(f"Undefined instruction {parsed_ins}")

LUI=Undefined
AUIPC=Undefined
JAL=Undefined
def JALR(hart:Hart,p:ParsedInstruction)->None:
    p.I()
    hart.x[p.rd]=hart.pc
    target=hart.x[p.rs1]
    target+=signed(p.imm,12)
    target&=bitmask(31,1)
    hart.pc=target
BEQ=Undefined
BNE=Undefined
BLT=Undefined
BGE=Undefined
BLTU=Undefined
BGEU=Undefined
def LOAD(hart:Hart,p:ParsedInstruction)->None:
    p.I()
    addr=hart.x[p.rs1] #base
    addr+=signed(p.imm,12)
    unsigned=read_bitfield(p.funct3,2,2)
    size=1<<read_bitfield(p.funct3,1,0)
    if size>4:
        Undefined(hart,p)
    val=hart.mem.load(size,addr)
    if unsigned==0:
        val=signed(val,size*8-1)
    hart.x[p.rd]=val
def STORE(hart:Hart,p:ParsedInstruction)->None:
    p.S()
    addr=hart.x[p.rs1] #base
    addr+=signed(p.imm,12)
    size=1<<read_bitfield(p.funct3,1,0)
    unsigned=read_bitfield(p.funct3,2,2)
    if unsigned==1:
        Undefined(hart,p)
    if size>4:
        Undefined(hart,p)
    hart.mem.store(size,addr,hart.x[p.rs2])
def ADDI(hart:Hart,parsed_ins:ParsedInstruction)->None:
    parsed_ins.I() #Convert instruction to I-type
    result=hart.x[parsed_ins.rs1]+signed(parsed_ins.imm,11)
    hart.x[parsed_ins.rd]=result
def SLTI(hart:Hart,parsed_ins:ParsedInstruction)->None:
    parsed_ins.I()
    hart.x[parsed_ins.rd]=1 if hart.signed(hart.x[parsed_ins.rs1])<signed(parsed_ins.imm,11) else 0
def SLTIU(hart:Hart,parsed_ins:ParsedInstruction)->None:
    parsed_ins.I()
    hart.x[parsed_ins.rd]=1 if hart.x[parsed_ins.rs1]<parsed_ins.imm else 0
def XORI(hart:Hart,parsed_ins:ParsedInstruction)->None:
    parsed_ins.I()
    hart.x[parsed_ins.rd]=hart.x[parsed_ins.rs1]^parsed_ins.imm
def ORI(hart:Hart,parsed_ins:ParsedInstruction)->None:
    parsed_ins.I()
    hart.x[parsed_ins.rd]=hart.x[parsed_ins.rs1]|parsed_ins.imm
def ANDI(hart:Hart,parsed_ins:ParsedInstruction)->None:
    parsed_ins.I()
    hart.x[parsed_ins.rd]=hart.x[parsed_ins.rs1]&parsed_ins.imm
SLLI=Undefined
SRLI=Undefined
SRAI=Undefined
ADD=Undefined
SUB=Undefined
SLL=Undefined
SLT=Undefined
SLTU=Undefined
XOR=Undefined
SRL=Undefined
SRA=Undefined
OR=Undefined
AND=Undefined
FENCE=Undefined
ECALLBREAK=Undefined

ins_exec=[[[Undefined]*128 for _ in range(8)] for _ in range(32)]

ins_exec[0b01101]=LUI #No function codes
ins_exec[0b00101]=AUIPC
ins_exec[0b11011]=JAL
ins_exec[0b11001][0b000]=JALR
ins_exec[0b11000][0b000]=BEQ
ins_exec[0b11000][0b001]=BNE
ins_exec[0b11000][0b100]=BLT
ins_exec[0b11000][0b101]=BGE
ins_exec[0b11000][0b110]=BLTU
ins_exec[0b11000][0b111]=BGEU
ins_exec[0b00000]=LOAD
ins_exec[0b01000]=STORE
ins_exec[0b00100][0b000]=ADDI
ins_exec[0b00100][0b010]=SLTI
ins_exec[0b00100][0b011]=SLTIU
ins_exec[0b00100][0b100]=XORI
ins_exec[0b00100][0b110]=ORI
ins_exec[0b00100][0b111]=ANDI
ins_exec[0b00100][0b001][0b0000000]=SLLI #Funct3 and Funct7
ins_exec[0b00100][0b001][0b0000000]=SRLI
ins_exec[0b00100][0b001][0b0100000]=SRAI
ins_exec[0b01100][0b000][0b0000000]=ADD
ins_exec[0b01100][0b000][0b0100000]=SUB
ins_exec[0b01100][0b001][0b0000000]=SLL
ins_exec[0b01100][0b010][0b0000000]=SLT
ins_exec[0b01100][0b011][0b0000000]=SLTU
ins_exec[0b01100][0b100][0b0000000]=XOR
ins_exec[0b01100][0b101][0b0000000]=SRL
ins_exec[0b01100][0b101][0b0100000]=SRA
ins_exec[0b01100][0b110][0b0000000]=OR
ins_exec[0b01100][0b111][0b0000000]=AND
ins_exec[0b00011][0b000]=FENCE
ins_exec[0b11100][0b000]=ECALLBREAK

def interpret(hart:Hart,p:ParsedInstruction):
    ins=ins_exec[read_bitfield(p.opcode,6,2)]
    if type(ins)==list:
        ins=ins[p.funct3]
        if type(ins)==list:
            ins=ins[p.funct7]
    ins(hart,p)

def main():
    hart=Hart()
    hart.mem.store(4,0x00,0xff010113)          #	addi	sp,sp,-16
    hart.mem.store(4,0x04,0x00812623)          #	sw	s0,12(sp)
    hart.mem.store(4,0x08,0x01010413)          #	addi	s0,sp,16
    hart.mem.store(4,0x0c,0x02a00793)          #	li	a5,42
    hart.mem.store(4,0x10,0x00078513)          #	mv	a0,a5
    hart.mem.store(4,0x14,0x00c12403)          #	lw	s0,12(sp)
    hart.mem.store(4,0x18,0x01010113)          #	addi	sp,sp,16
    hart.mem.store(4,0x1c,0x00008067)          #	ret
    hart.mem.dump(0,0x20)
    # 0     2     a     0     0     5     1     3
    # 0000  0010  1010  0000  0000  0101  0001  0011
    #   imm[11:0]    rs1  f3    rd    opcode
    # 000000101010  00000 000  01010 0010011
    # f7      rs2    rs1    f3  rd      opcode
    # 0000001 01010  00000 000  01010 0010011
    p=ParsedInstruction()
    while True:
        ins=hart.mem.load(4,hart.pc)
        p.R(ins)
        hart.pc+=4
        interpret(hart,p)
        print(p)

if __name__ == "__main__":
    main()