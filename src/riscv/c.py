"""
Define the RV32C instruction set. This is a set of 16-bit instructions
which fills a similar niche to the Thumb instruction set on ARM -- it
allows certain commonly used instructions to be encoded in a smaller
number of bits, to improve code density (for embedded devices with
limited memory) and/or cache efficiency (for large devices with cache).

On ARM, the Thumb is a completely separate mode, and has to be manually
switched into and out of. Thumb is basically complete, so that your
entire program may be in Thumb. Some devices, like Cortex-M, only
support Thumb mode. Since if everything could be done straightforward
with no compromises, no one would even use 32-bit instructions, then
there must be some compromises. In the Thumb case, the compromise
is that some operations which can be described in one 32-bit ARM
instructions require multiple instructions to be encoded in 16-bit
Thumb mode.

Thumb was basically an afterthought, which is why it is a separate
mode. In principle an ARM 32-bit processor doesn't have to implement
it, but in practice only older obsolete models did.

The designers of Risc-V saw how effective Thumb was, and designed
a 16-bit instruction set inspired by its best features, while aiming
to improve its deficiencies. RVxxC is therefore not a separate mode.
No one writes a program intending to be purely RV32C, the way you
have to decide if your compiler is targeting 16-bit Thumb or
32-bit ARM.

It encodes 16-bit instructions in a way such that the decoder can
immediately decide if it is a C instruction or some other longer
one. The compromise is that not all 32-bit instructions can be
encoded, and frequently there is *no* way to encode a particular
instruction in 16-bit mode. In this case, the programmer (or
compiler) just uses a normal 32-bit instruction. Every 16-bit
instruction is the encoding of a 32-bit I instruction, so there
is no additional "power" in the C instruction set. For each instruction,
the compiler or assembler decides whether the instruction *can* be
encoded in 16 bits and does so, or *can't* be and is encoded in
32 bits.

In principle, only the instructions which are most common are encoded
as 16-bit. In practice, this has to be decided (years) beforehand,
so the designers of RV32C made their best guesses as to what actually
*is* most common, and we all just run with that. Those designers
claim that something like 50% of instructions can be encoded in RV32C,
saving 25% of the code memory usage.

RV32C is *optional*. It is easier to design a core that doesn't implement
it, becasue while (C) is for (C)ompressed, it might also be for
(C)omplicated. Two things make it so:
* In order to squeeze the largest number of instructions into the set,
  we use complicated encodings. An encoding might be a register operation
  except for if the register is x0. In this context the instruction
  probably would be a no-op, but instead we steal the encoding to
  do something completely different.
* Compressed instructions with immediate values have those values'
  bits scrambled, seemingly at random. The given reason is to put
  the same bit value at the same encoding bit as often as possible,
  to make hardware decoding easier (where it's just routing), but
  it does make software decoding much more difficult.
These two things put together make the instruction encoding much more
complicated, and in some cases impossible to put into a single or
nested Mapping, in contrast to RV32I which is very orthogonal and
goes easily into a table. It seems like the coding is more amenable to
such things as a decoding ROM (like the 6502) with its required high,
required low, or don't care states for each bit in the encoding. It
might be a good use case for Python structural match statement.

This module contains those that don't care about XLEN. Those that
only apply to 32bit are in c32.py. Those for 64 or greater are in
c64.py, while those for only 128 are in c128.

Created: 6/12/24
"""
from dataclasses import dataclass
from typing import Callable, Mapping, Iterable

from riscv.hart import InstructionSet, Hart, WrongInterpreter, InstructionHandler, \
    IllegalInstruction, ExcCause, RVException
from riscv.bits import bitmask, read_bitfield, signed, read_bitfields


@dataclass
class ParsedInstruction:
    op:int=None
    funct:int=None
    rs2:int=None
    rd:int=None
    rs1:int=None
    imm:int=None
    offset:int=None
    target:int=None


class C(InstructionSet):
    class C_NOP(InstructionHandler):
        """
        NOPs and Hints. All hints are no-ops, but we want to see everything about it when we disassemble.
        """
        def __init__(self,name:str):
            self.name=name
        def execute(self, p: Mapping[str, int], hart: 'Hart') -> None:
            pass
        def disasm(self, p: Mapping[str, int], XLEN: int) -> str:
            return f"{self.name:7s} {p}"
        def formula(self, p: Mapping[str, int], XLEN: int):
            return f"(No operation)"
    class C_ANDI(InstructionHandler):
        def execute(self, p: Mapping[str,int], hart: 'Hart') -> None:
            hart.x[p['rd']]=hart.x[p['rs1']]&p['imm']
        def disasm(self, p: Mapping[str,int], XLEN: int) -> str:
            return f"C.ANDI   x{p['rd']:2d},0x{p['imm']:08x}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"{self.abi_regnames[p['rd']][self.nameidx]}&=0x{p['imm']:08x}"
    class C_StoreSP(InstructionHandler):
        """
        "C.SWSP stores a 32-bit value in register rs2 to memory. It
        computes an effective address by adding the zero-extended offset,
        scaled by 4 [scaled by the decoder, so don't do it here], to the
        stack pointer, x2. It expands to `sw rs2, offset[7:2](x2)`.
        """
        def __init__(self,name:str,*,size:int=4):
            self.name=name
            self.size=size
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            addr = hart.x[2]  # base
            addr += p['imm']
            hart.mem.store(self.size, addr, hart.x[p['rs2']])
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"{self.name:9s}x{p['rs2']:2},{p['imm']:15}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"mem[{self.abi_regnames[2][self.nameidx]}{'+'+str(p['imm']) if p['imm']!=0 else ''}]=b{self.size*8}({self.abi_regnames[p['rs2']][self.nameidx]})"
    class C_LW(InstructionHandler):
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            size = 4
            addr = hart.x[p['rs1']]  # base
            addr += p['imm']
            val = hart.mem.load(size, addr)
            # Note that this expands to an rv32i LW, not an rv64i LWU, so it always sign-extends.
            val = signed(val, size * 8 - 1)
            hart.x[p['rd']] = val
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"C.LW r{p['rs1']:2},r{p['rd']:2},{p['imm']:12}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"{self.abi_regnames[p['rd']][self.nameidx]}=i32(mem[{self.abi_regnames[p['rs1']][self.nameidx]}{'+'+str(p['imm']) if p['imm']>0 else ''}])"
    class C_SW(InstructionHandler):
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            size = 4
            addr = hart.x[p['rs1']]  # base
            addr += p['imm']
            hart.mem.store(size, addr,hart.x[p['rs2']])
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"C.SW r{p['rs1']:2},r{p['rs2']:2},{p['imm']:12}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"b32(mem[{self.abi_regnames[p['rs1']][self.nameidx]}{'+'+str(p['imm']) if p['imm']>0 else ''}])={self.abi_regnames[p['rs2']][self.nameidx]}"
    class C_LoadSP(InstructionHandler):
        def __init__(self,name:str,*,size:int=4):
            self.name=name
            self.size=size
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            addr = hart.x[2]  # base
            addr += p['imm']
            val = hart.mem.load(self.size, addr)
            val = signed(val, self.size * 8 - 1)
            hart.x[p['rd']] = val
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"{self.name:9s}x{p['rd']:2},{p['imm']:15}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"{self.abi_regnames[p['rd']][self.nameidx]}=i32(mem[{self.abi_regnames[2][self.nameidx]}{'+'+str(p['imm']) if p['imm']>0 else ''}])"
    class C_MV(InstructionHandler):
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            hart.x[p['rd']]=hart.x[p['rs2']]
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"C.MV    x{p['rd']:2},x{p['rs2']:2}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"{self.abi_regnames[p['rd']][self.nameidx]}={self.abi_regnames[p['rs2']][self.nameidx]}"
    class C_JR(InstructionHandler):
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            hart.pc=hart.x[p['rs1']]
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"C.JR   x{p['rs1']:2}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"pc={self.abi_regnames[p['rs1']][self.nameidx]}"
    class C_LI(InstructionHandler):
        """
        Execute C.LI, as well as C.HINT. The latter is
        implemented by loading the immediate to x0 which would discard it.
        Since this is the right action for NOP, and since our emulator
        doesn't care about performance and therefore ignores hints,
        it is OK to interpret this as normal write to x0.
        """

        def execute(self, p: Mapping[str,int], hart: 'Hart') -> None:
            hart.x[p['rd']]=p['imm']
        def disasm(self, p: Mapping[str,int], XLEN: int) -> str:
            if p['rd']==0:
                raise ValueError("C.HINT")
            else:
                return f"C.LI   x{p['rd']:2},{p['imm']:12}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            if p['rd']==0:
                return f"Hint (No operation)"
            else:
                return f"{self.abi_regnames[p['rd']][self.nameidx]}={p['imm']}"
    class C_LUI(InstructionHandler):
        """
        Execute C.LUI and C.ADDI16SP. C.LUI has rd!=2, while
        C.ADDI16SP has rd==2. The bit order of the constants is
        different between the two instructions.
        """
        def execute(self, p: Mapping[str,int], hart: 'Hart') -> None:
            hart.x[p['rd']]=p['imm']
        def disasm(self, p: Mapping[str,int], XLEN: int) -> str:
            return f"C.LUI   x{p['rd']:2},{p['imm']:12d}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"{self.abi_regnames[p['rd']][self.nameidx]}={p['imm']}"
    class C_ADDI16SP(InstructionHandler):
        """
        Execute C.ADDI16SP. Add immediate to Stack Pointer. I16 means
           multiply the immediate by 16 before adding, but the decoder
           already does this for us.
        """
        def execute(self, p: Mapping[str,int], hart: 'Hart') -> None:
            if p['imm']==0:
                raise WrongInterpreter("In C.ADDI16SP, have a zero immediate")
            hart.x[2]+=p['imm']
        def disasm(self, p: Mapping[str,int], XLEN: int) -> str:
            return f"C.ADDI16SP {p['imm']:12d}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            if p['imm']>=0:
                return f"{self.abi_regnames[2][self.nameidx]}+={p['imm']}"
            else:
                return f"{self.abi_regnames[2][self.nameidx]}-={-p['imm']}"
    class C_ADDI4SPN(InstructionHandler):
        """
        Execute C.ADDI4SPN.
        """
        def execute(self, p: Mapping[str,int], hart: 'Hart') -> None:
            if p['imm']==0:
                if p['rd']==0:
                    raise WrongInterpreter("All zero instruction, permanently illegal")
                raise WrongInterpreter("In C.ADDI4SPN, have a zero immediate")
            hart.x[p['rd']]=hart.x[2]+p['imm']
        def disasm(self, p: Mapping[str,int], XLEN: int) -> str:
            return f"C.ADDI4SPN x{p['rd']:2d},{p['imm']:12d}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"{self.abi_regnames[p['rd']][self.nameidx]}=stackptr+{p['imm']}"
    class C_ADD(InstructionHandler):
        """
        Execute C.EBREAK, C.JALR, or C.ADD. These all
        have the same opcode and funct bits, so they
        are only distinguishable by their register operands:
        * C.ADD - rs1/rd!=0, rs2!=0. IE don't use x0 as either
          a source or a destination. This would be a NOP, so
          we steal those bits for something else. If rs1/rd==0,
          this is a hint as it would be a NOP.
        * C.JALR - rs1/rd!=0, rs2==0. If we would source an add
          from x0, then this is a JALR instead
        * C.EBREAK - If this would both source and write to x0,
          then this is an EBREAK instead.
        """
        def execute(self, p: Mapping[str,int], hart: 'Hart') -> None:
            hart.x[p['rd']]=hart.x[p['rs1']]+hart.x[p['rs2']]
        def disasm(self, p: Mapping[str,int], XLEN: int) -> str:
            return f"C.ADD  x{p['rd']:2d},x{p['rs2']:2d}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"{self.abi_regnames[p['rd']][self.nameidx]}+={self.abi_regnames[p['rs2']][self.nameidx]}"
    class C_EBREAK(InstructionHandler):
        def execute(self, p: Mapping[str,int], hart: 'Hart') -> None:
            raise RVException(message=f"C.EBREAK",epc=hart.pc,is_interrupt=False,cause=ExcCause.BREAKPOINT.value,mtval=hart.pc)
        def disasm(self, p: Mapping[str,int], XLEN: int) -> str:
            return "C.EBREAK"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return "Breakpoint"
    class C_JALR(InstructionHandler):
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            # Make sure to do a swap in case rs1=x1
            saveaddr=hart.pc+2
            newpc=hart.x[p['rs1']]
            hart.x[1] = saveaddr
            hart.pc=newpc
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"C.JALR   {p['rs1']:12}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"{self.abi_regnames[1][self.nameidx]}=pc+2, pc={self.abi_regnames[p['rs1']][self.nameidx]}"
    class C_RpRp(InstructionHandler):
        def __init__(self, name: str, symbol: str, op: Callable[[Hart, int, int], int]):
            self.name = name
            self.symbol = symbol
            self.op = op
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            result = self.op(hart, hart.x[p['rs1']], hart.x[p['rs2']])
            hart.x[p['rd']] = result
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"{self.name:7s}x{p['rs1']:2},x{p['rs2']:2}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            if "%s" in self.symbol:
                return f"{self.abi_regnames[p['rd']][self.nameidx]}={self.symbol % (self.abi_regnames[p['rs1']][self.nameidx], self.abi_regnames[p['rs2']][self.nameidx])}"
            else:
                return f"{self.abi_regnames[p['rd']][self.nameidx]}{self.symbol}={self.abi_regnames[p['rs2']][self.nameidx]}"
    class C_J(InstructionHandler):
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            target = hart.pc
            target += p['imm']
            target &= bitmask(31, 1)
            hart.pc = target
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"C.J    {p['imm']:12}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            if p['imm']>0:
                return f"pc+={p['imm']}"
            else:
                return f"pc-={-p['imm']}"
    class C_Branch(InstructionHandler):
        def __init__(self, name: str, symbol: str, condition: Callable[[int, int], bool]):
            self.name = name
            self.symbol = symbol
            self.condition = condition
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            if self.condition(hart.x[p['rs1']], 0):
                target = hart.pc
                target += signed(p['imm'], 12)
                hart.pc = target
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"{self.name:7s}x{p['rs1']:2},{p['imm']:12}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            return f"if {self.abi_regnames[p['rs1']][self.nameidx]}{self.symbol}0 pc=pc{'+' if p['imm'] >= 0 else ''}{p['imm']}"
    class C_RegImmed(InstructionHandler):
        """
        An instruction which acts on a register and an immediate.
        """

        def __init__(self, name: str, symbol: str, op: Callable[[Hart, int, int], int],immfmt:str='d',immprefix:str=''):
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
            self.immfmt=immfmt
            self.immprefix=immprefix
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            result = self.op(hart, hart.x[p['rs1']], p['imm'])
            hart.x[p['rd']] = result
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"{self.name:7s}x{p['rd']:2},x{p['rs1']:2},{p['imm']:12}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            if p['rs1'] == 0:
                return f"{self.abi_regnames[p['rd']][self.nameidx]}={p['imm']}"
            else:
                return f"{self.abi_regnames[p['rd']][self.nameidx]}{self.symbol}={self.immprefix}{p['imm']:{self.immfmt}}"
    def get_decode_table(self):
        return self.ins_exec
    ins_exec = {
        # Quadrant 0
        " ___ ________ ___ __": "C.UNIM",  # Architecture-defined permanent illegal instruction
        "+___ 549 876 23 eee __": C_ADDI4SPN(),  # Immediate is specified as zero-extended
        " __| 543 mmm 76 eee __": None,  # C.FLD in C32/64F
        " __| 548 mmm 76 eee __": None,  # C.LQ in C128I
        "+_|_ 543 mmm 26 eee __": C_LW(),  # Immediate is specified as zero-extended
        " _|| 543 mmm 26 eee __": None,  # C.FLW in C32F
        " _|| 543 mmm 76 eee __": None,  # C.LD
        " |__ ... ... .. ... __": None,  # Reserved
        " |_| 543 mmm 76 yyy __": None,  # C.FSD in C32/64F
        " |_| 548 mmm 76 yyy __": None,  # C.SQ in C128I
        "+||_ 543 mmm 26 yyy __": C_SW(),  # Likewise
        " ||| 543 mmm 26 yyy __": None,  # C.FSW
        # Quadrant 1
        " ___ _ _____ _____ _|": C_NOP("C.NOP"),
        "+___ 5 _____ 43210 _|": C_NOP("C.HINT_NOP rd=0"),
        # Treat it as unsigned zero-ext because it will be used as a bitfield
        " ___ 5 fffff 43210 _|": C_RegImmed("C.ADDI","+",lambda hart,rs1,imm:rs1+imm),
        # Immediate must be nonzero and is sign-extended. Zero immediate is a hint.
        "+___ _ fffff _____ _|": C_NOP("C.HINT_ADDI imm=0"),
        # "__| 5 fffff 43210 _|":None, # C.ADDIW in C64/128I
        " _|_ 5 ddddd 43210 _|": C_LI(),
        "+_|_ 5 _____ 43210 _|": C_NOP("C.HINT_LI rd=x0"),
        " _|| 9 ___|_ 46875 _|": C_ADDI16SP(),  # Nonzero sign-extended. Zero immediate is reserved.
        " _|| _ ___|_ _____ _|": None,  # Reserved for future standard extensions, equivalent to C.ADDI16SP 0
        " _|| H ddddd GFEDC _|": C_LUI(),
        " _|| _ ddddd _____ _|": None,  # Reserved
        "+_|| 5 _____ 43210 _|": C_NOP("C.HINT_LUI rd=x0"),
        "+|__ _ __ ggg 43210 _|": C_RegImmed("C.SRLI", ">L>", lambda hart, rs1, imm: rs1 >> imm),  # Bit 12 is nzimm5, which must be 0 for RV32C
        "+|__ 5 __ ggg 43210 _|": None,  # SRLI in C64/128I
        "+|__ _ __ 210 _____ _|": C_NOP("C.HINT_SRLI 64"),  # C.SRLI64 in RV128C
        "+|__ _ _| ggg 43210 _|": C_RegImmed("C.SRAI", ">A>", lambda hart, rs1, imm: hart.signed(rs1) >> imm),  # Bit 12 is nzimm5, which must be 0 for RV32C
        "+|__ 5 _| ggg 43210 _|": None,  # SRAI in C64/128I
        "+|__ _ _| 210 _____ _|": C_NOP("C.HINT_SRAI 64"),  # C.SRAI64 in RV128C
        "x|__ 5 |_ ggg 43210 _|": C_RegImmed("C_ANDI","&",lambda hart,rs1,imm:rs1 & imm,immfmt='08x',immprefix='0x'),
        " |__ _ || ggg __ yyy _|": C_RpRp('C.SUB','-',lambda hart,a,b:a-b),
        " |__ _ || ggg _| yyy _|": C_RpRp('C.XOR','^',lambda hart,a,b:a^b),
        " |__ _ || ggg |_ yyy _|": C_RpRp('C.OR' ,'|',lambda hart,a,b:a|b),
        " |__ _ || ggg || yyy _|": C_RpRp('C.AND','&',lambda hart,a,b:a&b),
        " |__ | || ggg __ yyy _|": None,  # C.SUBW
        " |__ | || ggg _| yyy _|": None,  # C.ADDW
        " |__ | || ... |_ ... _|": None,  # Reserved
        " |__ | || ... || ... _|": None,  # Reserved
        " |_| B498A673215 _|": C_J(),
        " ||_ 843 mmm 76215 _|":C_Branch("C.BEQZ","==",lambda a,b:a==b),
        " ||| 843 mmm 76215 _|":C_Branch("C.BNEZ","!=",lambda a,b:a!=b),
        # Quadrant 2
        "+___ _ fffff 43210 |_": C_RegImmed("C.SLLI", "<<", lambda hart, rs1, imm: rs1 << imm),  # Bit 12 is nzimm5, which must be 0 for C32I
        " ___ 5 fffff 43210 |_": None,  # C.SLLI on C64/128I, reserved for non-standard extensions on C32I
        "+___ _ fffff _____ |_": C_NOP("C.HINT_SLLI 64"),  # C.SLLI rd,64 on C128I, hint on C32/64I
        "+__| 5 ddddd 43876 |_": None,  # C.FLDSP, C32/64F
        "+__| 5 ddddd 49876 |_": None,  # C.LQSP, C128I
        "+_|_ 5 ddddd 43276 |_": C_LoadSP("C.LWSP",size=4),
        " _|_ 5 _____ 43276 |_": None,  # Reserved, equivalent to C.LWSP x0,imm
        "+_|| 5 ddddd 43276 |_": None,  # C.FLWSP
        " _|| 5 _____ 43876 |_": None,  # Reserved, equivalent to C.LDSP x0,imm
        " |__ _ lllll _____ |_": C_JR(),  # Encoding that C.MV rd=x0 *would* have
        " |__ _ _____ _____ |_": None,  # Reserved, equivalent to C.JR x0
        " |__ _ ddddd zzzzz |_": C_MV(),
        " |__ _ _____ zzzzz |_": C_NOP("C.HINT_MV rd=x0"),  # Equivalent to C.MV x0=rs2
        " |__ | _____ _____ |_": C_EBREAK(),  # Encoding that C.ADD x0,x0 *would* have
        " |__ | lllll _____ |_": C_JALR(),  # Encoding that C.ADD rs1/rd,x0 *would* have
        " |__ | fffff zzzzz |_": C_ADD(),
        " |__ | _____ zzzzz |_": C_NOP("C.HINT_ADD rd=x0"),  # Encoding that C.ADD x0,rs2 *would* have
        "+|_| 543876 zzzzz |_": None,  # C.FSDSP, CF
        "+|_| 549876 zzzzz |_": None,  # C.SQSP, C128I
        "+||_ 543276 zzzzz |_": C_StoreSP("C.SWSP",size=4), # Zero-extended immediate
        "+||| 543276 zzzzz |_": None,  # C.FSWSP, C32F
    }



