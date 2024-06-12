"""
Implement the Risc-V 32-bit integer base instructions

Created: 6/11/24
"""
from dataclasses import dataclass
from typing import Callable

from riscv.hart import read_bitfield, signed, read_bitfields, InstructionSet, Hart, Instruction, bitmask, Opcode


@dataclass
class ParsedInstruction:
    """
    Parsed instruction, with each field broken out as necessary. Fields
    which aren't used in any particular instruction format are set to None.
    Immediate field is not sign-extended here (must be done in the instruction)
    because we don't know at this point for instance if we are on a 32 or 64
    bit machine
    """
    opcode:int=None
    rd:int=None
    funct3:int=None
    rs1:int=None
    rs2:int=None
    funct7:int=None
    imm:int=None
    def __str__(self):
        params=[]
        if self.opcode is not None:
            params.append(f'opcode=0b{self.opcode:07b} ({Opcode(read_bitfield(self.opcode,6,2))})')
        if self.rd is not None:
            params.append(f'rd={self.rd}')
        if self.funct3 is not None:
            params.append(f'funct3=0b{self.funct3:03b}')
        if self.rs1 is not None:
            params.append(f'rs1={self.rs1}')
        if self.rs2 is not None:
            params.append(f'rs2={self.rs2}')
        if self.funct7 is not None:
            params.append(f'funct7=0b{self.funct7:07b}')
        if self.imm is not None:
            params.append(f'imm={self.imm}')
        return 'ParsedInstruction('+",".join(params)+")"


def R(ins:int,XLEN:int,signed:bool)->ParsedInstruction:
    return ParsedInstruction(opcode = read_bitfield(ins, 6, 0),
                             rd     = read_bitfield(ins,11, 7),
                             funct3 = read_bitfield(ins,14,12),
                             rs1    = read_bitfield(ins,19,15),
                             rs2    = read_bitfield(ins,24,20),
                             funct7 = read_bitfield(ins,31,25))


def I(ins:int,XLEN:int,signed:bool)->ParsedInstruction:
    # SYSTEM instructions use the 12-bit immediate as a funct12. We will
    # do an ugly hack here and assign imm to funct7 as well, so that the
    # instruction decode tables don't have to handle funct7 and funct12
    # differently.
    return ParsedInstruction(opcode = read_bitfield(ins,6,0),
                             rd     = read_bitfield(ins, 11, 7),
                             funct3 = read_bitfield(ins, 14, 12),
                             rs1    = read_bitfield(ins, 19, 15),
                             imm    = read_bitfields(ins,((31,20,0),),XLEN,signed),
                             funct7 = read_bitfields(ins,((31,20,0),),XLEN,signed))


def S(ins:int,XLEN:int,signed:bool)->ParsedInstruction:
    return ParsedInstruction(opcode = read_bitfield(ins, 6, 0),
                             funct3 = read_bitfield(ins,14,12),
                             rs1    = read_bitfield(ins,19,15),
                             rs2    = read_bitfield(ins,24,20),
                             imm    =read_bitfields(ins,((31,25, 5),
                                                         (11, 7, 0)),XLEN,signed))


def B(ins:int,XLEN:int,signed:bool)->ParsedInstruction:
    return ParsedInstruction(opcode = read_bitfield(ins, 6, 0),
                             funct3 = read_bitfield(ins,14,12),
                             rs1    = read_bitfield(ins,19,15),
                             rs2    = read_bitfield(ins,24,20),
                             imm    =read_bitfields(ins,((31,31,12),
                                                         (30,25, 5),
                                                         (11, 8, 1),
                                                         ( 7, 7,11)),XLEN,signed))


def U(ins:int,XLEN:int,signed:bool)->ParsedInstruction:
    return ParsedInstruction(opcode = read_bitfield(ins, 6, 0),
                             rd     = read_bitfield(ins,11, 7),
                             imm    =read_bitfields(ins,((31,12,12),),XLEN,signed))


def J(ins:int,XLEN:int,signed:bool)->ParsedInstruction:
    return ParsedInstruction(opcode = read_bitfield(ins, 6,0),
                             rd     = read_bitfield(ins,11, 7),
                             imm    =read_bitfields(ins,((31,31,20),
                                                         (30,21, 1),
                                                         (20,20,11),
                                                         (19,12,12)),XLEN,signed))


class RegImmed(Instruction):
    def __init__(self, name: str, symbol: str, op: Callable[[Hart, int, int], int]):
        self.name = name
        self.symbol = symbol
        self.op = op
    def execute(self, ins:int, hart: Hart)->None:
        p = I(ins, hart.XLEN, True)
        result = self.op(hart,hart.x[p.rs1],p.imm)
        hart.x[p.rd] = result
    def disasm(self,ins:int,XLEN:int):
        p = I(ins, XLEN, True)
        return f"{self.name:7s}x{p.rd:2},x{p.rs1:2},{p.imm:12}"
    def formula(self,ins:int,XLEN:int):
        p = I(ins, XLEN, True)
        if p.rs1==0:
            return f"{self.abi_regnames[p.rd][self.nameidx]}={p.imm}"
        if "ADD" in self.name and p.imm<0:
            this_symbol=""
        else:
            this_symbol=self.symbol
        if "%s" in self.symbol:
            return f"{self.abi_regnames[p.rd][self.nameidx]}={self.symbol % (self.abi_regnames[p.rs1][self.nameidx],p.imm)}"
        else:
            return f"{self.abi_regnames[p.rd][self.nameidx]}={self.abi_regnames[p.rs1][self.nameidx]}{this_symbol}{p.imm}"


ADDI=RegImmed("ADDI","+",lambda hart,rs1,imm: rs1+imm)
XORI=RegImmed("XORI","^",lambda hart,rs1,imm: rs1^imm)
ORI=RegImmed("ORI","|",lambda hart,rs1,imm: rs1|imm)
ANDI=RegImmed("ANDI","&",lambda hart,rs1,imm: rs1&imm)
SLLI=RegImmed("SLLI","<<",lambda hart,rs1,imm:rs1<<(imm & 0x1f))
SRLI=RegImmed("SRLI", ">L>", lambda hart,rs1, imm: rs1 >> (imm & 0x1f))
SRAI=RegImmed("SRAI",">A>", lambda hart,rs1,imm: hart.signed(rs1) >> read_bitfield(imm, 4, 0))
SLTI=RegImmed("SLTI","(signed(%s)<signed(%s))?1:0", lambda hart,rs1,rs2: 1 if hart.signed(rs1) < hart.signed(rs2) else 0)
SLTIU=RegImmed("SLTIU","(%s<%s)?1:0", lambda hart,rs1,rs2: 1 if rs1 < rs2 else 0)


class LUI(Instruction):
    format= U
    @classmethod
    def execute(cls, ins:int, hart: Hart)->None:
        p = cls.format(ins,hart.XLEN,False)
        hart.x[p.rd]=p.imm
    @classmethod
    def disasm(cls,ins:int,XLEN:int):
        p = cls.format(ins,XLEN,False)
        return f"LUI    r{p.rd:2},     {p.imm:12}"
    @classmethod
    def formula(cls,ins:int,XLEN:int):
        p = cls.format(ins,XLEN,False)
        return f"{cls.abi_regnames[p.rd][cls.nameidx]}=0x{p.imm:08x}"


class AUIPC(Instruction):
    format= U
    @classmethod
    def execute(cls, ins:int, hart: Hart)->None:
        p = cls.format(ins,hart.XLEN,True)
        hart.x[p.rd] = hart.pc + p.imm
    @classmethod
    def disasm(cls,ins:int,XLEN:int):
        p = cls.format(ins,XLEN,True)
        return f"AUIPC  r{p.rd:2},     {p.imm:12}"
    @classmethod
    def formula(cls,ins:int,XLEN:int):
        p = cls.format(ins,XLEN,True)
        return f"r{p.rd}=pc{'+' if p.imm>=0 else ''}{p.imm}"


class JAL(Instruction):
    format= J
    @classmethod
    def execute(cls, ins:int, hart: Hart)->None:
        p = cls.format(ins,hart.XLEN,True)
        hart.x[p.rd]=hart.pc
        target=hart.pc
        target+=p.imm
        target&= bitmask(31, 1)
        hart.pc=target
    @classmethod
    def disasm(cls,ins:int,XLEN:int):
        p = cls.format(ins,XLEN,True)
        return f"JAL    r{p.rd:2},     {p.imm:12}"
    @classmethod
    def formula(cls,ins:int,XLEN:int):
        p = cls.format(ins,XLEN,True)
        if p.rd==0:
            return f"pc=pc{'+' if p.imm >= 0 else ''}{p.imm}"
        else:
            return f"{cls.abi_regnames[p.rd][cls.nameidx]}=pc+4, pc=pc{'+' if p.imm>=0 else ''}{p.imm}"


class JALR(Instruction):
    format= I
    @classmethod
    def execute(cls, ins:int, hart: Hart)->None:
        p = cls.format(ins,hart.XLEN,True)
        hart.x[p.rd] = hart.pc
        target = hart.x[p.rs1]
        target += signed(p.imm, 12)
        target &= bitmask(31, 1)
        hart.pc = target
    @classmethod
    def disasm(cls,ins:int,XLEN:int):
        p = cls.format(ins,XLEN,True)
        return f"JALR   r{p.rd:2},r{p.rs1:2},{p.imm:12}"
    @classmethod
    def formula(cls, ins: int, XLEN: int):
        p = cls.format(ins, XLEN, True)
        result=""
        if p.rd!=0:
            result=f"{cls.abi_regnames[p.rd][cls.nameidx]}=pc+4, "
        result+=f"pc={cls.abi_regnames[p.rs1][cls.nameidx]}"
        if p.imm!=0:
            result+=f"{'+' if p.imm>=0 else ''}{p.imm}"
        return result


class STORE(Instruction):
    format= S
    @classmethod
    def execute(cls, ins:int, hart: Hart)->None:
        p = cls.format(ins,hart.XLEN,True)
        addr=hart.x[p.rs1] #base
        addr+=p.imm
        size= 1 << read_bitfield(p.funct3, 1, 0)
        unsigned= read_bitfield(p.funct3, 2, 2)
        if unsigned==1:
            Undefined(hart,p) # Because there is no such thing as a signed store
        if size>4:
            Undefined(hart,p)
        hart.mem.store(size,addr,hart.x[p.rs2])
    @classmethod
    def disasm(cls,ins:int,XLEN:int):
        p = cls.format(ins,XLEN,True)
        size= 1 << read_bitfield(p.funct3, 1, 0)
        mnemonic=[None,"SB    ","SH    ",None,"SW    "]
        return f"{mnemonic[size]} r{p.rs1:2},r{p.rs2:2},{p.imm:12}"
    @classmethod
    def formula(cls,ins:int,XLEN:int):
        p = cls.format(ins,XLEN,True)
        size= 1 << read_bitfield(p.funct3, 1, 0)
        cast=[None,"i8","i16",None,"i32"]
        return f"mem[{cls.abi_regnames[p.rs1][0]}{'+' if p.imm>=0 else ''}{p.imm}]={cast[size]}({cls.abi_regnames[p.rs2][0]})"


class LOAD(Instruction):
    format= I
    @classmethod
    def execute(cls, ins:int, hart: Hart)->None:
        p = cls.format(ins,hart.XLEN,True)
        addr = hart.x[p.rs1]  # base
        addr += signed(p.imm, 12)
        unsigned = read_bitfield(p.funct3, 2, 2)
        size = 1 << read_bitfield(p.funct3, 1, 0)
        if size > 4:
            Undefined(hart, p)
        val = hart.mem.load(size, addr)
        if unsigned == 0:
            val = signed(val, size * 8 - 1)
        hart.x[p.rd] = val
    @classmethod
    def disasm(cls,ins:int,XLEN:int):
        p = cls.format(ins,XLEN,True)
        mnemonic=["LB    ","LH    ","LW    ",None,"LBU   ","LHU   "]
        return f"{mnemonic[p.funct3]} r{p.rs1:2},r{p.rd:2},{p.imm:12}"
    @classmethod
    def formula(cls,ins:int,XLEN:int):
        p = cls.format(ins,XLEN,True)
        cast=["i8","i16","i32",None,"u8","u16"]
        return f"r{p.rd}={cast[p.funct3]}(mem[r{p.rs1}{'+' if p.imm>=0 else ''}{p.imm}])"


class BRANCH(Instruction):
    def __init__(self,name:str,symbol:str,condition:Callable[[int,int],bool]):
        self.name=name
        self.symbol=symbol
        self.condition=condition
    def execute(self, ins:int, hart: Hart)->None:
        p = B(ins, hart.XLEN, True)
        if p.imm==-20:
            print(p.imm)
        if self.condition(hart,hart.x[p.rs1],hart.x[p.rs2]):
            target = hart.pc
            target += signed(p.imm, 12)
            hart.pc = target
    def disasm(self,ins:int,XLEN:int):
        p = B(ins, XLEN, True)
        return f"{self.name:7s}x{p.rs1:2},x{p.rs2:2},{p.imm:12}"
    def formula(self,ins:int,XLEN:int):
        p = B(ins, XLEN, True)
        sym=self.symbol % (self.abi_regnames[p.rs1][self.nameidx],self.abi_regnames[p.rs2][self.nameidx])
        return f"if {sym} pc=pc{'+' if p.imm>=0 else ''}{p.imm}"


BEQ=BRANCH('BEQ','%s==%s',lambda hart,rs1,rs2:rs1==rs2)
BNE=BRANCH('BNE','%s!=%s',lambda hart,rs1,rs2:rs1!=rs2)
BLT=BRANCH('BLT','signed(%s)<signed(%s)', lambda hart,rs1,rs2: hart.signed(rs1) < hart.signed(rs2))
BGE=BRANCH('BGE','signed(%s)>=signed(%s)', lambda hart,rs1,rs2: hart.signed(rs1) >= hart.signed(rs2))
BGEU=BRANCH('BGEU','%s>=%s',lambda hart,rs1,rs2:rs1>=rs2)
BLTU=BRANCH('BLTU','%s<%s',lambda hart,rs1,rs2:rs1<rs2)


class RegReg(Instruction):
    def __init__(self, name: str, symbol: str, op: Callable[[Hart, int, int], int]):
        self.name = name
        self.symbol = symbol
        self.op = op
    def execute(self, ins:int, hart: Hart)->None:
        p = R(ins, hart.XLEN, True)
        result=self.op(hart,hart.x[p.rs1],hart.x[p.rs2])
        hart.x[p.rd] = result
    def disasm(self,ins:int,XLEN:int):
        p = R(ins, XLEN, True)
        return f"{self.name:7s}x{p.rd:2},x{p.rs1:2},x{p.rs2:2}"
    def formula(self,ins:int,XLEN:int):
        p = R(ins, XLEN, True)
        if "%s" in self.symbol:
            return f"{self.abi_regnames[p.rd][self.nameidx]}={self.symbol % (self.abi_regnames[p.rs1][self.nameidx],self.abi_regnames[p.rs2][self.nameidx])}"
        else:
            return f"{self.abi_regnames[p.rd][self.nameidx]}={self.abi_regnames[p.rs1][self.nameidx]}{self.symbol}{self.abi_regnames[p.rs2][self.nameidx]}"


ADD=RegReg("ADD","+",lambda hart,rs1,rs2:rs1+rs2)
AND=RegReg("AND","&",lambda hart,rs1,rs2:rs1&rs2)
OR=RegReg("OR","|",lambda hart,rs1,rs2:rs1|rs2)
XOR=RegReg("XOR","^",lambda hart,rs1,rs2:rs1^rs2)
SUB=RegReg("SUB","-",lambda hart,rs1,rs2:rs1-rs2)
SLL=RegReg("SLL","<<", lambda hart,rs1,rs2: rs1 << read_bitfield(rs2, 4, 0))
SRL=RegReg("SRL",">>", lambda hart,rs1,rs2: rs1 >> read_bitfield(rs2, 4, 0))
SRA=RegReg("SRA",">>>", lambda hart,rs1,rs2: hart.signed(rs1) >> read_bitfield(rs2, 4, 0))
SLT=RegReg("SLT","(signed(%s)<signed(%s))?1:0", lambda hart,rs1,rs2: 1 if hart.signed(rs1) < hart.signed(rs2) else 0)
SLTU=RegReg("SLTU","(%s<%s)?1:0", lambda hart,rs1,rs2: 1 if rs1 < rs2 else 0)


class SYSTEM(Instruction):
    def __init__(self,name:str="Undefined",comment:str=None,message:str=None):
        """

        :param name: Name of instruction
        :param formula:
        :param message:
        """
        if message is None:
            self.message="Undefined instruction"
        else:
            self.message=message
        self.name=name
        self.comment=comment
    def execute(self, ins:int, hart: Hart)->None:
        raise StopIteration(f"{self.message} -- parsed={I(ins,hart.XLEN,True)}")
    def disasm(self,ins:int,XLEN:int):
        return self.name
    def formula(self,ins:int,XLEN:int):
        return self.comment


EBREAK=SYSTEM("EBREAK","Break to debugger","Break to debugger")
ECALL=SYSTEM("ECALL","System call","System call")


class Nop(Instruction):
    def __init__(self,name:str="NOP",comment:str=None):
        """

        :param name: Name of instruction
        :param formula:
        :param message:
        """
        self.name=name
        self.comment=comment
    def execute(self, ins:int, hart: Hart)->None:
        pass
    def disasm(self,ins:int,XLEN:int):
        return self.name
    def formula(self,ins:int,XLEN:int):
        return self.comment


FENCE=Nop("FENCE","Memory Fence")


class RV32I(InstructionSet):
    def interpret(self, hart: Hart, ins: int)->bool:
        p=R(ins,hart.XLEN,None)
        if read_bitfield(p.opcode,1,0)!=0b11:
            return False # Compressed instruction, don't handle it here
        ins_type = self.ins_exec[read_bitfield(p.opcode, 6, 2)]
        if type(ins_type) == list:
            ins_type = ins_type[p.funct3]
            if type(ins_type) == list:
                ins_type = ins_type[p.funct7]
        if ins_type is None:
            return False
        print(f"{hart.pc:08x} -- {ins:08x}  {ins_type.disasm(ins,hart.XLEN)}  # {ins_type.formula(ins,hart.XLEN)}")
        ins_type.execute(ins, hart)
        return True
    ins_exec = [[[None for func7 in range(128)] for func3 in range(8)] for op in range(32)]
    ins_exec[0b01101] = LUI  # No function codes
    ins_exec[0b00101] = AUIPC
    ins_exec[0b11011] = JAL
    ins_exec[0b11001][0b000] = JALR
    ins_exec[0b11000][0b000] = BEQ
    ins_exec[0b11000][0b001] = BNE
    ins_exec[0b11000][0b100] = BLT
    ins_exec[0b11000][0b101] = BGE
    ins_exec[0b11000][0b110] = BLTU
    ins_exec[0b11000][0b111] = BGEU
    ins_exec[0b00000] = LOAD
    ins_exec[0b01000] = STORE
    ins_exec[0b00100][0b000] = ADDI
    ins_exec[0b00100][0b010] = SLTI
    ins_exec[0b00100][0b011] = SLTIU
    ins_exec[0b00100][0b100] = XORI
    ins_exec[0b00100][0b110] = ORI
    ins_exec[0b00100][0b111] = ANDI
    ins_exec[0b00100][0b001][0b0000000] = SLLI  # Funct3 and Funct7
    ins_exec[0b00100][0b101][0b0000000] = SRLI
    ins_exec[0b00100][0b101][0b0100000] = SRAI
    ins_exec[0b01100][0b000][0b0000000] = ADD
    ins_exec[0b01100][0b000][0b0100000] = SUB
    ins_exec[0b01100][0b001][0b0000000] = SLL
    ins_exec[0b01100][0b010][0b0000000] = SLT
    ins_exec[0b01100][0b011][0b0000000] = SLTU
    ins_exec[0b01100][0b100][0b0000000] = XOR
    ins_exec[0b01100][0b101][0b0000000] = SRL
    ins_exec[0b01100][0b101][0b0100000] = SRA
    ins_exec[0b01100][0b110][0b0000000] = OR
    ins_exec[0b01100][0b111][0b0000000] = AND
    ins_exec[0b00011][0b000] = FENCE
    ins_exec[0b11100][0b000][0b0] = ECALL
    ins_exec[0b11100][0b000][0b1] = EBREAK


