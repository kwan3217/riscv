"""
Implement the Risc-V 32-bit integer base instructions

Created: 6/11/24
"""
from dataclasses import dataclass
from typing import Callable, Mapping

import riscv.bits
from riscv.hart import InstructionSet, Hart, InstructionHandler, Opcode, WrongInterpreter
from riscv.bits import bitmask, read_bitfield, signed, read_bitfields


class RV32I(InstructionSet):
    class LUI(InstructionHandler):
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            hart.x[p["rd"]] = p["imm"]
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"LUI    r{p['rd']:2},     {p['imm']:12}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"{self.abi_regnames[p['rd']][self.nameidx]}=0x{p['imm']:08x}"
    class AUIPC(InstructionHandler):
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            hart.x[p["rd"]] = hart.pc + p["imm"]
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"AUIPC  r{p['rd']:2},     {p['imm']:12}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"r{p['rd']}=pc{'+' if p['imm'] >= 0 else ''}0x{p['imm']:08x}"
    class JAL(InstructionHandler):
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            retaddr=hart.pc+4
            target = hart.pc
            target += p['imm']
            target &= bitmask(31, 1)
            hart.x[p['rd']] = retaddr
            hart.pc = target
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"JAL    r{p['rd']:2},     {p['imm']:12}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            if p['rd'] == 0:
                return f"pc=pc{'+' if p['imm'] >= 0 else ''}{p['imm']}"
            else:
                return f"{self.abi_regnames[p['rd']][self.nameidx]}=pc+4, pc=pc{'+' if p['imm'] >= 0 else ''}{p['imm']}"
    class JALR(InstructionHandler):
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            target = hart.x[p['rs1']]
            target += signed(p['imm'], 12)
            target &= bitmask(31, 1)
            retaddr=hart.pc+4
            hart.x[p['rd']] = retaddr
            hart.pc = target
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"JALR   r{p['rd']:2},r{p['rs1']:2},{p['imm']:12}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            result = ""
            if p['rd'] != 0:
                result = f"{self.abi_regnames[p['rd']][self.nameidx]}=pc+4, "
            result += f"pc={self.abi_regnames[p['rs1']][self.nameidx]}"
            if p['imm'] != 0:
                result += f"{'+' if p['imm'] >= 0 else ''}{p['imm']}"
            return result
    class Load(InstructionHandler):
        def __init__(self,name:str,size:int,signed:bool):
            self.name=name
            self.size=size
            self.signed=signed
            if self.signed:
                self.cast=(None,"i8","i16",None,"i32")[self.size]
            else:
                self.cast=(None,"u8","u16",None,"u32")[self.size]
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            addr = hart.x[p['rs1']]  # base
            addr += signed(p['imm'], 12)
            val = hart.mem.load(self.size, addr)
            if self.signed:
                val = signed(val, self.size * 8 - 1)
            hart.x[p['rd']] = val
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"{self.name:7s}x{p['rs1']:2},x{p['rd']:2},{p['imm']:12}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"{self.abi_regnames[p['rd']][self.nameidx]}={self.cast}(mem[{self.abi_regnames[p['rs1']][self.nameidx]}{'+' if p['imm'] >= 0 else ''}{p['imm']}])"
    class Store(InstructionHandler):
        def __init__(self,name:str,size:int):
            self.name=name
            self.size=size
            self.cast=(None,"b8","b16",None,"b32")[self.size]
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            addr = hart.x[p['rs1']]  # base
            addr += p['imm']
            val=hart.x[p['rs2']]
            hart.mem.store(self.size, addr, val)
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"{self.name:7s}x{p['rs1']:2},x{p['rs2']:2},{p['imm']:12}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"mem[{self.abi_regnames[p['rs1']][self.nameidx]}{'+' if p['imm'] >= 0 else ''}{p['imm']}]={self.cast}({self.abi_regnames[p['rs2']][self.nameidx]})"
    class Branch(InstructionHandler):
        def __init__(self, name: str, symbol: str, condition: Callable[['Hart',int, int], bool]):
            self.name = name
            self.symbol = symbol
            self.condition = condition
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            if self.condition(hart, hart.x[p['rs1']], hart.x[p['rs2']]):
                target = hart.pc
                target += signed(p['imm'], 12)
                hart.pc = target
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"{self.name:7s}x{p['rs1']:2},x{p['rs2']:2},{p['imm']:12}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            if "%s" in self.symbol:
                sym = self.symbol
            else:
                sym = f"%s{self.symbol}%s"
            sym = sym % (self.abi_regnames[p['rs1']][self.nameidx], self.abi_regnames[p['rs2']][self.nameidx])
            return f"if {sym} pc{'+' if p['imm'] >= 0 else '+'}={p['imm'] if p['imm']>=0 else -p['imm']}"
    class Nop(InstructionHandler):
        def __init__(self, name: str = "NOP", comment: str = None):
            """

            :param name: Name of instruction
            :param formula:
            :param message:
            """
            self.name = name
            self.comment = comment
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            pass
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return self.name
        def formula(self, p: Mapping[str,int], XLEN: int):
            return self.comment
    class RegImmed(InstructionHandler):
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
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            result = self.op(hart, hart.x[p['rs1']], p['imm'])
            hart.x[p['rd']] = result
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"{self.name:7s}x{p['rd']:2},x{p['rs1']:2},{p['imm']:12}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            if p['rs1'] == 0:
                return f"{self.abi_regnames[p['rd']][self.nameidx]}={p['imm']}"
            if "ADD" in self.name and p['imm'] < 0:
                this_symbol = ""
            else:
                this_symbol = self.symbol
            if "%s" in self.symbol:
                return f"{self.abi_regnames[p['rd']][self.nameidx]}={self.symbol % (self.abi_regnames[p['rs1']][self.nameidx], p['imm'])}"
            else:
                return f"{self.abi_regnames[p['rd']][self.nameidx]}={self.abi_regnames[p['rs1']][self.nameidx]}{this_symbol}{p['imm']}"
    class RegReg(InstructionHandler):
        def __init__(self, name: str, symbol: str, op: Callable[[Hart, int, int], int]):
            self.name = name
            self.symbol = symbol
            self.op = op
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            result = self.op(hart, hart.x[p['rs1']], hart.x[p['rs2']])
            hart.x[p['rd']] = result
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"{self.name:7s}x{p['rd']:2},x{p['rs1']:2},x{p['rs2']:2}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            if "%s" in self.symbol:
                return f"{self.abi_regnames[p['rd']][self.nameidx]}={self.symbol % (self.abi_regnames[p['rs1']][self.nameidx], self.abi_regnames[p['rs2']][self.nameidx])}"
            else:
                return f"{self.abi_regnames[p['rd']][self.nameidx]}={self.abi_regnames[p['rs1']][self.nameidx]}{self.symbol}{self.abi_regnames[p['rs2']][self.nameidx]}"
    class SYSTEM(InstructionHandler):
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
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            raise StopIteration(f"{self.message} -- parsed={p}")
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return self.name
        def formula(self, p: Mapping[str,int], XLEN: int):
            return self.comment
    #        opcode  Funct3  Funct7
    ins_exec={
        "xVUTSRQPONMLKJIHGFEDC    ddddd _||_|||":LUI(),
        "-VUTSRQPONMLKJIHGFEDC    ddddd __|_|||":AUIPC(),
        "-KA987654321BJIHGFEDC    ddddd ||_||||":JAL(),
        " BA9876543210  lllll ___ ddddd ||__|||":JALR(),
        " CA98765 zzzzz lllll ___ 4321B ||___||":Branch('BEQ','==',lambda hart, rs1, rs2: rs1 == rs2),
        " CA98765 zzzzz lllll __| 4321B ||___||":Branch('BNE','!=',lambda hart, rs1, rs2: rs1 != rs2),
        " CA98765 zzzzz lllll |__ 4321B ||___||":Branch('BLT','signed(%s)<signed(%s)', lambda hart, rs1, rs2: hart.signed(rs1) < hart.signed(rs2)),
        " CA98765 zzzzz lllll |_| 4321B ||___||":Branch('BGE','signed(%s)>=signed(%s)', lambda hart, rs1, rs2: hart.signed(rs1) >= hart.signed(rs2)),
        " CA98765 zzzzz lllll ||_ 4321B ||___||":Branch('BLTU','<',lambda hart, rs1, rs2: rs1 < rs2),
        " CA98765 zzzzz lllll ||| 4321B ||___||":Branch('BGEU','>=',lambda hart, rs1, rs2: rs1 >= rs2),
        " BA9876543210  lllll ___ ddddd _____||":Load('LB',size=1,signed=True),
        " BA9876543210  lllll __| ddddd _____||":Load('LH',size=2,signed=True),
        " BA9876543210  lllll _|_ ddddd _____||":Load('LW',size=4,signed=True),
        " BA9876543210  lllll |__ ddddd _____||":Load('LBU',size=1,signed=False),
        " BA9876543210  lllll |_| ddddd _____||":Load('LHU',size=2,signed=False),
        " BA98765 zzzzz lllll ___ 43210 _|___||":Store('SB',size=1),
        " BA98765 zzzzz lllll __| 43210 _|___||":Store('SH',size=2),
        " BA98765 zzzzz lllll _|_ 43210 _|___||":Store('SW',size=4),
        "-BA9876543210  lllll ___ ddddd __|__||":RegImmed("ADDI", "+", lambda hart, rs1, imm: rs1 + imm),
        "-BA9876543210  lllll _|_ ddddd __|__||":RegImmed("SLTI", "(signed(%s)<signed(%s))?1:0",lambda hart, rs1, rs2: 1 if hart.signed(rs1) < hart.signed(rs2) else 0),
        "xBA9876543210  lllll _|| ddddd __|__||":RegImmed("SLTIU","(%s<%s)?1:0", lambda hart, rs1, rs2: 1 if rs1 < rs2 else 0),
        "xBA9876543210  lllll |__ ddddd __|__||":RegImmed("XORI", "^", lambda hart, rs1, imm: rs1 ^ imm),
        "xBA9876543210  lllll ||_ ddddd __|__||":RegImmed("ORI", "|", lambda hart, rs1, imm: rs1 | imm),
        "xBA9876543210  lllll ||| ddddd __|__||":RegImmed("ANDI", "&", lambda hart, rs1, imm: rs1 & imm),
        "+_______ 43210 lllll __| ddddd __|__||":RegImmed("SLLI", "<<", lambda hart, rs1, imm: rs1 << (imm & 0x1f)),
                # I can never remember whether which of >> or >>> is logical and
                # which is arithmetic, so I stick a letter in the middle of the
                # symbol instead.
        "+_______ 43210 lllll |_| ddddd __|__||":RegImmed("SRLI", ">L>", lambda hart, rs1, imm: rs1 >> (imm & 0x1f)),
        "+_|_____ 43210 lllll |_| ddddd __|__||":RegImmed("SRAI", ">A>", lambda hart, rs1, imm: hart.signed(rs1) >> read_bitfield(imm, 4, 0)),
        " _______ zzzzz lllll ___ ddddd _||__||":RegReg("ADD", "+", lambda hart, rs1, rs2: rs1 + rs2),
        " _|_____ zzzzz lllll ___ ddddd _||__||":RegReg("SUB", "-", lambda hart, rs1, rs2: rs1 - rs2),
        " _______ zzzzz lllll __| ddddd _||__||":RegReg("SLL", "<<", lambda hart, rs1, rs2: rs1 << read_bitfield(rs2, 4, 0)),
        " _______ zzzzz lllll _|_ ddddd _||__||":RegReg("SLT", "(signed(%s)<signed(%s))?1:0",lambda hart, rs1, rs2: 1 if hart.signed(rs1) < hart.signed(rs2) else 0),
        " _______ zzzzz lllll _|| ddddd _||__||":RegReg("SLTU", "(%s<%s)?1:0", lambda hart, rs1, rs2: 1 if rs1 < rs2 else 0),
        " _______ zzzzz lllll |__ ddddd _||__||":RegReg("XOR", "^", lambda hart, rs1, rs2: rs1 ^ rs2),
        " _______ zzzzz lllll |_| ddddd _||__||":RegReg("SRL", ">L>", lambda hart, rs1, rs2: rs1 >> read_bitfield(rs2, 4, 0)),
        " _|_____ zzzzz lllll |_| ddddd _||__||":RegReg("SRA", ">A>", lambda hart, rs1, rs2: hart.signed(rs1) >> read_bitfield(rs2, 4, 0)),
        " _______ zzzzz lllll ||_ ddddd _||__||":RegReg("OR", "|", lambda hart, rs1, rs2: rs1 | rs2),
        " _______ zzzzz lllll ||| ddddd _||__||":RegReg("AND", "&", lambda hart, rs1, rs2: rs1 & rs2),
        "+BA9876543210  lllll ___ ddddd ___||||":Nop("FENCE", "Memory Fence"),
        " ____________  _____ ___ _____ |||__||":SYSTEM("EBREAK", "Break to debugger", "Break to debugger"),
        " ___________|  _____ ___ _____ |||__||":SYSTEM("ECALL", "System call", "System call"),
    }
    def get_decode_table(self):
        return self.ins_exec


