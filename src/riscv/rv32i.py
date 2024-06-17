"""
Implement the Risc-V 32-bit integer base instructions

Created: 6/11/24
"""
from dataclasses import dataclass
from typing import Callable, Mapping

import riscv.bits
from riscv.hart import InstructionSet, Hart, InstructionInterpreter, Opcode, WrongInterpreter
from riscv.bits import bitmask, read_bitfield, signed, read_bitfields


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


# Instruction decoders for the various formats of instructions,
# following the naming convention in unpriviledged 2.2
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


class RV32I(InstructionSet):
    def interpret(self, hart: Hart, ins: int):
        p=R(ins,hart.XLEN,None)
        if read_bitfield(p.opcode,1,0)!=0b11:
            raise WrongInterpreter("Compressed instruction, don't handle it here")
        try:
            ins_type = self.ins_exec[Opcode(read_bitfield(p.opcode, 6, 2))]
            if isinstance(ins_type,Mapping):
                ins_type = ins_type[p.funct3]
                if isinstance(ins_type,Mapping):
                    ins_type = ins_type[p.funct7]
        except KeyError:
            raise WrongInterpreter("Not found in RV32I instruction table")
        print(f"{hart.pc:08x} -- {ins:08x}  {ins_type.disasm(ins,hart.XLEN)}  # {ins_type.formula(ins,hart.XLEN)}")
        ins_type.execute(ins, hart)
    class LUI(InstructionInterpreter):
        def execute(self, ins: int, hart: Hart) -> None:
            p = U(ins, hart.XLEN, False)
            hart.x[p.rd] = p.imm
        def disasm(self, ins: int, XLEN: int):
            p = U(ins, XLEN, False)
            return f"LUI    r{p.rd:2},     {p.imm:12}"
        def formula(self, ins: int, XLEN: int):
            p = U(ins, XLEN, False)
            return f"{self.abi_regnames[p.rd][self.nameidx]}=0x{p.imm:08x}"
    class AUIPC(InstructionInterpreter):
        def execute(self, ins: int, hart: Hart) -> None:
            p = U(ins, hart.XLEN, True)
            hart.x[p.rd] = hart.pc + p.imm

        def disasm(self, ins: int, XLEN: int):
            p = U(ins, XLEN, True)
            return f"AUIPC  r{p.rd:2},     {p.imm:12}"

        def formula(self, ins: int, XLEN: int):
            p = U(ins, XLEN, True)
            return f"r{p.rd}=pc{'+' if p.imm >= 0 else ''}{p.imm}"
    class JAL(InstructionInterpreter):
        def execute(self, ins: int, hart: Hart) -> None:
            p = J(ins, hart.XLEN, True)
            hart.x[p.rd] = hart.pc
            target = hart.pc
            target += p.imm
            target &= bitmask(31, 1)
            hart.pc = target
        def disasm(self, ins: int, XLEN: int):
            p = J(ins, XLEN, True)
            return f"JAL    r{p.rd:2},     {p.imm:12}"
        def formula(self, ins: int, XLEN: int):
            p = J(ins, XLEN, True)
            if p.rd == 0:
                return f"pc=pc{'+' if p.imm >= 0 else ''}{p.imm}"
            else:
                return f"{self.abi_regnames[p.rd][self.nameidx]}=pc+4, pc=pc{'+' if p.imm >= 0 else ''}{p.imm}"
    class JALR(InstructionInterpreter):
        def execute(self, ins: int, hart: Hart) -> None:
            p = I(ins, hart.XLEN, True)
            target = hart.x[p.rs1]
            target += signed(p.imm, 12)
            target &= bitmask(31, 1)
            retaddr=hart.pc+4
            hart.x[p.rd] = retaddr
            hart.pc = target
        def disasm(self, ins: int, XLEN: int):
            p = I(ins, XLEN, True)
            return f"JALR   r{p.rd:2},r{p.rs1:2},{p.imm:12}"
        def formula(self, ins: int, XLEN: int):
            p = I(ins, XLEN, True)
            result = ""
            if p.rd != 0:
                result = f"{self.abi_regnames[p.rd][self.nameidx]}=pc+4, "
            result += f"pc={self.abi_regnames[p.rs1][self.nameidx]}"
            if p.imm != 0:
                result += f"{'+' if p.imm >= 0 else ''}{p.imm}"
            return result
    class LOAD(InstructionInterpreter):
        def execute(self, ins: int, hart: Hart) -> None:
            p = I(ins, hart.XLEN, True)
            unsigned = read_bitfield(p.funct3, 2, 2)
            size = 1 << read_bitfield(p.funct3, 1, 0)
            if size > 4:
                raise WrongInterpreter(f"Unsupported size {size}")
            if size==4 and unsigned:
                raise WrongInterpreter(f"Unsigned 32-bit load not supported in RV32I -- should be handled by RV64I")
            addr = hart.x[p.rs1]  # base
            addr += signed(p.imm, 12)
            val = hart.mem.load(size, addr)
            if unsigned == 0:
                val = signed(val, size * 8 - 1)
            hart.x[p.rd] = val
        def disasm(self, ins: int, XLEN: int):
            p = I(ins, XLEN, True)
            mnemonic = ["LB    ", "LH    ", "LW    ", None, "LBU   ", "LHU   "]
            return f"{mnemonic[p.funct3]} r{p.rs1:2},r{p.rd:2},{p.imm:12}"
        def formula(self, ins: int, XLEN: int):
            p = I(ins, XLEN, True)
            cast = ["i8", "i16", "i32", None, "u8", "u16"]
            return f"r{p.rd}={cast[p.funct3]}(mem[r{p.rs1}{'+' if p.imm >= 0 else ''}{p.imm}])"
    class STORE(InstructionInterpreter):
        def execute(self, ins: int, hart: Hart) -> None:
            p = S(ins, hart.XLEN, True)
            addr = hart.x[p.rs1]  # base
            addr += p.imm
            size = 1 << read_bitfield(p.funct3, 1, 0)
            unsigned = read_bitfield(p.funct3, 2, 2)
            if unsigned == 1:
                raise WrongInterpreter("No such thing as a signed store")
            if size > 4:
                raise WrongInterpreter(f"Unsupported size {size}")
            hart.mem.store(size, addr, hart.x[p.rs2])
        def disasm(self, ins: int, XLEN: int):
            p = S(ins, XLEN, True)
            size = 1 << read_bitfield(p.funct3, 1, 0)
            mnemonic = [None, "SB    ", "SH    ", None, "SW    "]
            return f"{mnemonic[size]} r{p.rs1:2},r{p.rs2:2},{p.imm:12}"
        def formula(self, ins: int, XLEN: int):
            p = S(ins, XLEN, True)
            size = 1 << read_bitfield(p.funct3, 1, 0)
            cast = [None, "b8", "b16", None, "b32"]
            return f"mem[{self.abi_regnames[p.rs1][0]}{'+' if p.imm >= 0 else ''}{p.imm}]={cast[size]}({self.abi_regnames[p.rs2][0]})"
    class Branch(InstructionInterpreter):
        def __init__(self, name: str, symbol: str, condition: Callable[[int, int], bool]):
            self.name = name
            self.symbol = symbol
            self.condition = condition
        def execute(self, ins: int, hart: Hart) -> None:
            p = B(ins, hart.XLEN, True)
            if p.imm == -20:
                print(p.imm)
            if self.condition(hart, hart.x[p.rs1], hart.x[p.rs2]):
                target = hart.pc
                target += signed(p.imm, 12)
                hart.pc = target
        def disasm(self, ins: int, XLEN: int):
            p = B(ins, XLEN, True)
            return f"{self.name:7s}x{p.rs1:2},x{p.rs2:2},{p.imm:12}"
        def formula(self, ins: int, XLEN: int):
            p = B(ins, XLEN, True)
            if "%s" in self.symbol:
                sym = self.symbol
            else:
                sym = f"%s{self.symbol}%s"
            sym = sym % (self.abi_regnames[p.rs1][self.nameidx], self.abi_regnames[p.rs2][self.nameidx])
            return f"if {sym} pc=pc{'+' if p.imm >= 0 else ''}{p.imm}"
    class Nop(InstructionInterpreter):
        def __init__(self, name: str = "NOP", comment: str = None):
            """

            :param name: Name of instruction
            :param formula:
            :param message:
            """
            self.name = name
            self.comment = comment
        def execute(self, ins: int, hart: Hart) -> None:
            pass
        def disasm(self, ins: int, XLEN: int):
            return self.name
        def formula(self, ins: int, XLEN: int):
            return self.comment
    class RegImmed(InstructionInterpreter):
        """
        An instruction which acts on a register and an immediate.
        """

        def __init__(self, name: str, symbol: str, op: Callable[[Hart, int, int], int]):
            """
            Define a specific instruction

            :param name: Name, following the RISC-V book for the canonical name of this
                         instruction in all uppercase
            :param symbol: Symbol of this instruction, approximating the symbol that would
                           be used in C/C++ to describe the same operation. If the symbol
                           does *not* have the substring %s, it is considered to be an infix
                           operator such as `+`. If it *does* have the substring %s, then it
                           is considered to be a complete expression, and must have exactly
                           two %s placeholders. An example is `(signed(%s)<signed(%s))?1:0` for
                           SLTI.
            :param op: Callable which is handed two integer operands and returns the result
                       of the operation. It's often convenient to use a lambda here. It is
                       passed the hart in question, but that is usually just used to get the
                       current XLEN. Note that it is passed *values*, not register references.
                       The values are passed as unsigned integers, but can be converted to
                       signed using the XLEN from the hart.
            """
            self.name = name
            self.symbol = symbol
            self.op = op

        def execute(self, ins: int, hart: Hart) -> None:
            p = I(ins, hart.XLEN, True)
            result = self.op(hart, hart.x[p.rs1], p.imm)
            hart.x[p.rd] = result

        def disasm(self, ins: int, XLEN: int):
            p = I(ins, XLEN, True)
            return f"{self.name:7s}x{p.rd:2},x{p.rs1:2},{p.imm:12}"

        def formula(self, ins: int, XLEN: int):
            p = I(ins, XLEN, True)
            if p.rs1 == 0:
                return f"{self.abi_regnames[p.rd][self.nameidx]}={p.imm}"
            if "ADD" in self.name and p.imm < 0:
                this_symbol = ""
            else:
                this_symbol = self.symbol
            if "%s" in self.symbol:
                return f"{self.abi_regnames[p.rd][self.nameidx]}={self.symbol % (self.abi_regnames[p.rs1][self.nameidx], p.imm)}"
            else:
                return f"{self.abi_regnames[p.rd][self.nameidx]}={self.abi_regnames[p.rs1][self.nameidx]}{this_symbol}{p.imm}"
    class RegReg(InstructionInterpreter):
        def __init__(self, name: str, symbol: str, op: Callable[[Hart, int, int], int]):
            self.name = name
            self.symbol = symbol
            self.op = op
        def execute(self, ins: int, hart: Hart) -> None:
            p = R(ins, hart.XLEN, True)
            result = self.op(hart, hart.x[p.rs1], hart.x[p.rs2])
            hart.x[p.rd] = result
        def disasm(self, ins: int, XLEN: int):
            p = R(ins, XLEN, True)
            return f"{self.name:7s}x{p.rd:2},x{p.rs1:2},x{p.rs2:2}"
        def formula(self, ins: int, XLEN: int):
            p = R(ins, XLEN, True)
            if "%s" in self.symbol:
                return f"{self.abi_regnames[p.rd][self.nameidx]}={self.symbol % (self.abi_regnames[p.rs1][self.nameidx], self.abi_regnames[p.rs2][self.nameidx])}"
            else:
                return f"{self.abi_regnames[p.rd][self.nameidx]}={self.abi_regnames[p.rs1][self.nameidx]}{self.symbol}{self.abi_regnames[p.rs2][self.nameidx]}"
    class SYSTEM(InstructionInterpreter):
        def __init__(self, name: str = "Undefined", comment: str = None, message: str = None):
            """

            :param name: Name of instruction
            :param formula:
            :param message:
            """
            if message is None:
                self.message = "Undefined instruction"
            else:
                self.message = message
            self.name = name
            self.comment = comment
        def execute(self, ins: int, hart: Hart) -> None:
            raise StopIteration(f"{self.message} -- parsed={I(ins, hart.XLEN, True)}")
        def disasm(self, ins: int, XLEN: int):
            return self.name
        def formula(self, ins: int, XLEN: int):
            return self.comment
    #        opcode  Funct3  Funct7
    ins_exec={
        Opcode.LUI  :LUI(),
        Opcode.AUIPC:AUIPC(),
        Opcode.JAL  :JAL(),
        Opcode.JALR :{
            0b000:JALR()
        },
        Opcode.BRANCH:{
            0b000:Branch('BEQ', '==', lambda hart, rs1, rs2: rs1 == rs2),
            0b001:Branch('BNE', '!=', lambda hart, rs1, rs2: rs1 != rs2),
            0b100:Branch('BLT', 'signed(%s)<signed(%s)', lambda hart, rs1, rs2: hart.signed(rs1) < hart.signed(rs2)),
            0b101:Branch('BGE', 'signed(%s)>=signed(%s)', lambda hart, rs1, rs2: hart.signed(rs1) >= hart.signed(rs2)),
            0b110:Branch('BLTU', '<', lambda hart, rs1, rs2: rs1 < rs2),
            0b111:Branch('BGEU', '>=', lambda hart, rs1, rs2: rs1 >= rs2)
        },
        Opcode.LOAD: LOAD(),
        Opcode.STORE: STORE(),
        Opcode.OP_IMM:{
            0b000:RegImmed("ADDI", "+", lambda hart, rs1, imm: rs1 + imm),
            0b010:RegImmed("SLTI", "(signed(%s)<signed(%s))?1:0",
                    lambda hart, rs1, rs2: 1 if hart.signed(rs1) < hart.signed(rs2) else 0),
            0b011:RegImmed("SLTIU", "(%s<%s)?1:0", lambda hart, rs1, rs2: 1 if rs1 < rs2 else 0),
            0b100:RegImmed("XORI", "^", lambda hart, rs1, imm: rs1 ^ imm),
            0b110:RegImmed("ORI", "|", lambda hart, rs1, imm: rs1 | imm),
            0b111:RegImmed("ANDI", "&", lambda hart, rs1, imm: rs1 & imm),
            0b001:{
                0b0000000:RegImmed("SLLI", "<<", lambda hart, rs1, imm: rs1 << (imm & 0x1f))
            },
            0b101:{
                # I can never remember whether which of >> or >>> is logical and
                # which is arithmetic, so I stick a letter in the middle of the
                # symbol instead.
                0b0000000:RegImmed("SRLI", ">L>", lambda hart, rs1, imm: rs1 >> (imm & 0x1f)),
                0b0100000:RegImmed("SRAI", ">A>", lambda hart, rs1, imm: hart.signed(rs1) >> read_bitfield(imm, 4, 0))
            }
        },
        Opcode.OP:{
            0b000:{
                0b0000000:RegReg("ADD", "+", lambda hart, rs1, rs2: rs1 + rs2),
                0b0100000:RegReg("SUB", "-", lambda hart, rs1, rs2: rs1 - rs2)
            },
            0b001:{
                0b0000000:RegReg("SLL", "<<", lambda hart, rs1, rs2: rs1 << read_bitfield(rs2, 4, 0))
            },
            0b010:{
                0b0000000:RegReg("SLT", "(signed(%s)<signed(%s))?1:0",
                 lambda hart, rs1, rs2: 1 if hart.signed(rs1) < hart.signed(rs2) else 0)
            },
            0b011:{
                0b0000000:RegReg("SLTU", "(%s<%s)?1:0", lambda hart, rs1, rs2: 1 if rs1 < rs2 else 0)
            },
            0b100:{
                 0b0000000:RegReg("XOR", "^", lambda hart, rs1, rs2: rs1 ^ rs2),
            },
            0b101:{
                 0b0000000:RegReg("SRL", ">L>", lambda hart, rs1, rs2: rs1 >> read_bitfield(rs2, 4, 0)),
                 0b0100000:RegReg("SRA", ">A>", lambda hart, rs1, rs2: hart.signed(rs1) >> read_bitfield(rs2, 4, 0)),
            },
            0b110:{
                0b0000000:RegReg("OR", "|", lambda hart, rs1, rs2: rs1 | rs2)
            },
            0b111:{
                0b0000000:RegReg("AND", "&", lambda hart, rs1, rs2: rs1 & rs2)
            }
        },
        Opcode.MISC_MEM:{
            0b000:Nop("FENCE", "Memory Fence")
        },
        Opcode.SYSTEM:{
            0b000:{
                0b0:SYSTEM("EBREAK", "Break to debugger", "Break to debugger"),
                0b1:SYSTEM("ECALL", "System call", "System call")
            }
        }
    }


