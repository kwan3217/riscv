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
Created: 6/12/24
"""
from dataclasses import dataclass
from typing import Callable, Mapping, Iterable

from riscv.hart import InstructionSet, Hart, read_bitfield, WrongInterpreter, InstructionInterpreter, Opcode, \
    read_bitfields, signed, bitmask


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

def op(ins):
    return read_bitfield(ins, 1, 0)


def CR(ins:int)->ParsedInstruction:
    """
    Parse instruction as if it's a CR-type (Compressed Register)
    :param ins: 16-bit number to parse as a RV32C CR instruction
    :return: ParsedInstruction with the valid fields set, and the other fields None
    """
    return ParsedInstruction(op=read_bitfield(ins, 1, 0),
                             rs2=read_bitfield(ins, 6, 2),
                             rd=read_bitfield(ins, 11, 7),
                             rs1=read_bitfield(ins, 11, 7),
                             funct=read_bitfield(ins, 15, 12))


def CI(ins:int,imm_bitfield:Iterable[tuple[int,int,int]],imm_signed:bool=True)->ParsedInstruction:
    """
    Parse instruction as if it's a CI-type (Compressed Immediate)
    :param ins: 16-bit number to parse as a RV32C CI instruction
    :param imm_signed: If True, sign-extend the immediate, otherwise zero-extend it.
    :return: ParsedInstruction with the valid fields set, and the other fields None
    """
    return ParsedInstruction(op=read_bitfield(ins, 1, 0),
                             imm=read_bitfields(ins, imm_bitfield,is_signed=imm_signed),
                             rs1=read_bitfield(ins,11,7),
                             rd =read_bitfield(ins,11,7),
                             funct=read_bitfield(ins, 15, 13))


def CSS(ins:int,imm_bitfield:Iterable[tuple[int,int,int]])-> ParsedInstruction:
    """
    Parse instruction as if it's a CSS-type (Compressed Stack-relative Store)
    :param ins: 16-bit number to parse as a RV32C CSS instruction
    :return: ParsedInstruction with the valid fields set, and the other fields None
    """
    return ParsedInstruction(op=read_bitfield(ins, 1, 0),
                             rs1=2,
                             rs2=read_bitfield(ins, 6, 2),
                             imm=read_bitfields(ins, imm_bitfield,is_signed=False),
                             funct=read_bitfield(ins, 15, 13))


def CIW(ins:int)-> ParsedInstruction:
    """
    Parse instruction as if it's a CIW-type (Compressed Wide Immediate)
    :param ins: 16-bit number to parse as a RV32C CSS instruction
    :return: ParsedInstruction with the valid fields set, and the other fields None
    """
    return ParsedInstruction(op=read_bitfield(ins, 1, 0),
                             rd=read_bitfield(ins, 4, 2) + 8,
                             imm=read_bitfield(ins, 12, 5),
                             funct=read_bitfield(ins, 15, 13))


def CL(ins:int,ofs_fields:Iterable[tuple[int,int,int]])-> ParsedInstruction:
    """
    Parse instruction as if it's a CL-type (Compressed Load)
    :param ins: 16-bit number to parse as a RV32C CSS instruction
    :return: ParsedInstruction with the valid fields set, and the other fields None
    """
    return ParsedInstruction(op=read_bitfield(ins, 1, 0),
                             rd=read_bitfield(ins, 4, 2) + 8,
                             imm=read_bitfields(ins, ofs_fields,is_signed=False),
                             rs1=read_bitfield(ins, 9, 7) + 8,
                             funct=read_bitfield(ins, 15, 13))


def CS(ins:int,ofs_fields:Iterable[tuple[int,int,int]],imm_signed:bool=True)-> ParsedInstruction:
    """
    Parse instruction as if it's a CS-type (Compressed Store)
    :param ins: 16-bit number to parse as a RV32C CSS instruction
    :return: ParsedInstruction with the valid fields set, and the other fields None
    """
    return ParsedInstruction(op=read_bitfield(ins, 1, 0),
                             rs2=read_bitfield(ins, 4, 2) + 8,
                             imm=read_bitfields(ins, ofs_fields,is_signed=False),
                             rs1=read_bitfield(ins, 9, 7) + 8,
                             funct=read_bitfield(ins, 15, 13))


def CA(ins:int)-> ParsedInstruction:
    """
    Parse instruction as if it's a CA-type (Compressed Arithmetic)
    :param ins: 16-bit number to parse as a RV32C CSS instruction
    :return: ParsedInstruction with the valid fields set, and the other fields None
    """
    return ParsedInstruction(op=read_bitfield(ins, 1, 0),
                             rs2=read_bitfield(ins, 4, 2) + 8,
                             rd=read_bitfield(ins, 9, 7) + 8,
                             rs1=read_bitfield(ins, 9, 7) + 8,
                             funct=read_bitfields(ins, ((15, 10,2),(6, 5,0))))


def CB(ins:int)-> ParsedInstruction:
    """
    Parse instruction as if it's a CB-type (Compressed Branch)
    :param ins: 16-bit number to parse as a RV32C CSS instruction
    :return: ParsedInstruction with the valid fields set, and the other fields None
    """
    return ParsedInstruction(op=read_bitfield(ins, 1, 0),
                             offset=read_bitfields(ins, ((12, 10,5),(6, 2,0))),
                             rs1=read_bitfield(ins, 9, 7) + 8,
                             funct=read_bitfield(ins, 15, 13))


def CJ(ins:int)-> ParsedInstruction:
    """
    Parse instruction as if it's a CJ-type (Compressed Jump)
    :param ins: 16-bit number to parse as a RV32C CSS instruction
    :return: ParsedInstruction with the valid fields set, and the other fields None
    """
    return ParsedInstruction(op=read_bitfield(ins, 1, 0),
                             target=read_bitfields(ins, ((12,12,11),
                                                         (11,11, 4),
                                                         (10, 9, 8),
                                                         ( 8, 8,10),
                                                         ( 7, 7, 6),
                                                         ( 6, 6, 7),
                                                         ( 5, 3, 1),
                                                         ( 2, 2, 5)),is_signed=True),
                             funct=read_bitfield(ins, 15, 13))


class RV32C(InstructionSet):
    def interpret(self, hart: Hart, ins: int):
        op=read_bitfield(ins,1,0)
        if op==0b11:
            raise WrongInterpreter("Not a compressed instruction, don't handle it here")
        funct=read_bitfield(ins,15,13)
        try:
            ins_type = self.ins_exec[op]
            if isinstance(ins_type,Mapping):
                ins_type = ins_type[funct]
                if isinstance(ins_type,Mapping):
                    b12=read_bitfield(ins,12,12)
                    ins_type=ins_type[b12]
        except KeyError:
            raise WrongInterpreter("Not found in RV32C instruction table")
        print(f"{hart.pc:08x} -- {ins:04x}      {ins_type.disasm(ins,hart.XLEN)}  # {ins_type.formula(ins,hart.XLEN)}")
        ins_type.execute(ins, hart)
    #        opcode  Funct3  Funct7
    class C_ADDI(InstructionInterpreter):
        """
        Execute C.ADDI, as well as C.NOP and C.HINT. The latter two
        are implemented by adding immediate 0 to a particular register.
        Since this is the right action for NOP, and since our emulator
        doesn't care about performance and therefore ignores hints,
        it is OK to interpret these as normal add-of-0.
        """

        def execute(self, ins: int, hart: 'Hart') -> None:
            p=CI(ins,imm_signed=True,imm_bitfield=((12,12,5),(6,2,0)))
            hart.x[p.rd]=hart.x[p.rs1]+p.imm
        def disasm(self, ins: int, XLEN: int) -> str:
            p=CI(ins,imm_signed=True,imm_bitfield=((12,12,5),(6,2,0)))
            if p.rd==0:
                return "C.NOP"
            elif p.imm==0:
                return f"C.HINT   0b{p.rd:05b}"
            else:
                return f"C.ADDI   x{p.rd:2},x{p.rd:2},{p.imm:12}"
        def formula(self, ins: int, XLEN: int):
            p=CI(ins,imm_signed=True,imm_bitfield=((12,12,5),(6,2,0)))
            if p.rd==0:
                return "No operation"
            elif p.imm==0:
                return f"Hint (No operation)"
            else:
                if p.imm>=0:
                    return f"{self.abi_regnames[p.rd][self.nameidx]}+={p.imm}"
                else:
                    return f"{self.abi_regnames[p.rd][self.nameidx]}-={-p.imm}"
    class C_SWSP(InstructionInterpreter):
        """
        Execute C.SWSP
        """
        def execute(self, ins: int, hart: Hart) -> None:
            p = CSS(ins,((12, 9,2),(8,7,6)))
            addr = hart.x[p.rs1]  # base
            addr += p.imm
            size = 4
            hart.mem.store(size, addr, hart.x[p.rs2])
        def disasm(self, ins: int, XLEN: int):
            p = CSS(ins,((12, 9,2),(8,7,6)))
            return f"C.SWSP   x{p.rs2:2},{p.imm:15}"
        def formula(self, ins: int, XLEN: int):
            p = CSS(ins,((12, 9,2),(8,7,6)))
            return f"mem[{self.abi_regnames[p.rs1][self.nameidx]}+{p.imm}]=b32({self.abi_regnames[p.rs2][self.nameidx]})"
    class C_LW(InstructionInterpreter):
        def execute(self, ins: int, hart: Hart) -> None:
            p = CL(ins,((12,10,3),(6,6,2),(5,5,6)))
            size = 4
            addr = hart.x[p.rs1]  # base
            addr += p.imm
            val = hart.mem.load(size, addr)
            # Note that this expands to an rv32i LW, not an rv64i LWU, so it always sign-extends.
            val = signed(val, size * 8 - 1)
            hart.x[p.rd] = val
        def disasm(self, ins: int, XLEN: int):
            p = CL(ins,((12,10,3),(6,6,2),(5,5,6)))
            return f"C.LW r{p.rs1:2},r{p.rd:2},{p.imm:12}"
        def formula(self, ins: int, XLEN: int):
            p = CL(ins,((12,10,3),(6,6,2),(5,5,6)))
            return f"{self.abi_regnames[p.rd][self.nameidx]}=i32(mem[{self.abi_regnames[p.rs1][self.nameidx]}{'+'+str(p.imm) if p.imm>0 else ''}])"
    class C_SW(InstructionInterpreter):
        def execute(self, ins: int, hart: Hart) -> None:
            p = CS(ins,((12,10,3),(6,6,2),(5,5,6)))
            size = 4
            addr = hart.x[p.rs1]  # base
            addr += p.imm
            hart.mem.store(size, addr,hart.x[p.rs2])
        def disasm(self, ins: int, XLEN: int):
            p = CS(ins,((12,10,3),(6,6,2),(5,5,6)))
            return f"C.SW r{p.rs1:2},r{p.rs2:2},{p.imm:12}"
        def formula(self, ins: int, XLEN: int):
            p = CS(ins,((12,10,3),(6,6,2),(5,5,6)))
            return f"b32(mem[{self.abi_regnames[p.rs1][self.nameidx]}{'+'+str(p.imm) if p.imm>0 else ''}])={self.abi_regnames[p.rs2][self.nameidx]}"
    class C_LWSP(InstructionInterpreter):
        def execute(self, ins: int, hart: Hart) -> None:
            p = CI(ins,imm_bitfield=((12,12,5),(6,4,2),(3,2,6)),imm_signed=False)
            size = 4
            addr = hart.x[2]  # base
            addr += p.imm
            val = hart.mem.load(size, addr)
            # Note that this expands to an rv32i LW, not an rv64i LWU, so it always sign-extends.
            val = signed(val, size * 8 - 1)
            hart.x[p.rd] = val
        def disasm(self, ins: int, XLEN: int):
            p = CI(ins,imm_bitfield=((12,12,5),(6,4,2),(3,2,6)),imm_signed=False)
            return f"C.LWSP   x{p.rd:2},{p.imm:15}"
        def formula(self, ins: int, XLEN: int):
            p = CI(ins,imm_bitfield=((12,12,5),(6,4,2),(3,2,6)),imm_signed=False)
            return f"{self.abi_regnames[p.rd][self.nameidx]}=i32(mem[{self.abi_regnames[2][self.nameidx]}{'+'+str(p.imm) if p.imm>0 else ''}])"
    class C_JR_MV(InstructionInterpreter):
        def execute(self, ins: int, hart: Hart) -> None:
            p = CR(ins)
            if p.rs2!=0 and p.rd!=0:
                # C.MV
                hart.x[p.rd]=hart.x[p.rs2]
            else:
                raise WrongInterpreter()
        def disasm(self, ins: int, XLEN: int):
            p = CR(ins)
            if p.rs2!=0 and p.rd!=0:
                # C.MV
                return f"C.MV    x{p.rd:2},x{p.rs2:2}"
            else:
                raise WrongInterpreter()
        def formula(self, ins: int, XLEN: int):
            p = CR(ins)
            if p.rs2!=0 and p.rd!=0:
                # C.MV
                return f"{self.abi_regnames[p.rd][self.nameidx]}={self.abi_regnames[p.rs2][self.nameidx]}"
            else:
                raise WrongInterpreter()
    class C_JAL(InstructionInterpreter):
        def execute(self, ins: int, hart: Hart) -> None:
            p = CJ(ins)
            hart.x[1] = hart.pc+2
            target = hart.pc
            target += p.target
            target &= bitmask(31, 1)
            hart.pc = target
        def disasm(self, ins: int, XLEN: int):
            p = CJ(ins)
            return f"C.JAL    {p.target:12}"
        def formula(self, ins: int, XLEN: int):
            p = CJ(ins)
            return f"{self.abi_regnames[1][self.nameidx]}=pc+2, pc=pc{'+' if p.target >= 0 else ''}{p.target}"
    class C_LI(InstructionInterpreter):
        """
        Execute C.LI, as well as C.HINT. The latter is
        implemented by loading the immediate to x0 which would discard it.
        Since this is the right action for NOP, and since our emulator
        doesn't care about performance and therefore ignores hints,
        it is OK to interpret this as normal write to x0.
        """

        def execute(self, ins: int, hart: 'Hart') -> None:
            p=CI(ins,imm_signed=True,imm_bitfield=((12,12,5),(6,2,0)))
            hart.x[p.rd]=p.imm
        def disasm(self, ins: int, XLEN: int) -> str:
            p=CI(ins,imm_signed=True,imm_bitfield=((12,12,5),(6,2,0)))
            if p.rd==0:
                return "C.HINT"
            else:
                return f"C.LI   x{p.rd:2},{p.imm:12}"
        def formula(self, ins: int, XLEN: int):
            p=CI(ins,imm_signed=True,imm_bitfield=((12,12,5),(6,2,0)))
            if p.rd==0:
                return f"Hint (No operation)"
            else:
                return f"{self.abi_regnames[p.rd][self.nameidx]}={p.imm}"
    class C_LUI_ADDI16SP(InstructionInterpreter):
        """
        Execute C.LUI and C.ADDI16SP. C.LUI has rd!=2, while
        C.ADDI16SP has rd==2. The bit order of the constants is
        different between the two instructions.
        """

        def execute(self, ins: int, hart: 'Hart') -> None:
            p=CI(ins,imm_signed=True,imm_bitfield=((12,12,17),(6,2,12)))
            if p.rd!=0 and p.rd!=2:
                # C.LUI
                hart.x[p.rd]=p.imm
            elif p.rd==2:
                # C.ADDI16SP - Add 16*immediate to Stack Pointer. Note
                # that the specified bitfield for the non-zero immediate
                # actually already does the *16, since the lowest bit
                # specified is bit 4 of the immediate.
                p=CI(ins,imm_signed=True,imm_bitfield=((12,12,9),(6,6,4),(5,5,6),(4,3,7),(2,2,5)))
                if p.imm==0:
                    raise WrongInterpreter("In C.ADDI16SP, have a zero immediate")
                hart.x[2]+=p.imm
        def disasm(self, ins: int, XLEN: int) -> str:
            p=CI(ins,imm_signed=True,imm_bitfield=((12,12,17),(6,2,12)))
            if p.rd!=0 and p.rd!=2:
                # C.LUI
                return f"C.LUI   x{p.rd:2},{p.imm:12d}"
            elif p.rd==2:
                # C.ADDI16SP
                p=CI(ins,imm_signed=True,imm_bitfield=((12,12,9),(6,6,4),(5,5,6),(4,3,7),(2,2,5)))
                return f"C.ADDI16SP {p.imm:12d}"
        def formula(self, ins: int, XLEN: int):
            p=CI(ins,imm_signed=True,imm_bitfield=((12,12,17),(6,2,12)))
            if p.rd!=0 and p.rd!=2:
                # C.LUI
                return f"{self.abi_regnames[p.rd][self.nameidx]}={p.imm}"
            elif p.rd==2:
                # C.ADDI16SP
                p=CI(ins,imm_signed=True,imm_bitfield=((12,12,9),(6,6,4),(5,5,6),(4,3,7),(2,2,5)))
                if p.imm>=0:
                    return f"{self.abi_regnames[2][self.nameidx]}+={p.imm}"
                else:
                    return f"{self.abi_regnames[2][self.nameidx]}-={-p.imm}"
    class C_EBREAK_JALR_ADD(InstructionInterpreter):
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
        def execute(self, ins: int, hart: 'Hart') -> None:
            p = CR(ins)
            if p.rd!=0 and p.rs2!=0:
                # C.ADD
                hart.x[p.rd]=hart.x[p.rs1]+hart.x[p.rs2]
            elif p.rd==0:
                pass # Hint, equivalent to NOP
            elif p.rs2==0:
                # C.JALR
                raise NotImplemented("C.JALR")
            else:
                # C.EBREAK
                raise StopIteration(f"C.EBREAK")
        def disasm(self, ins: int, XLEN: int) -> str:
            p=CR(ins)
            if p.rd!=0 and p.rs2!=0:
                # C.ADD
                return f"C.ADD  x{p.rd:2d},x{p.rs2:2d}"
            elif p.rd==0:
                return "C.HINT"
            elif p.rs2==0:
                return "C.JALR"
            else:
                return "C.EBREAK"
        def formula(self, ins: int, XLEN: int):
            p=CR(ins)
            if p.rd!=0 and p.rs2!=0:
                return f"{self.abi_regnames[p.rd][self.nameidx]}+={self.abi_regnames[p.rs2][self.nameidx]}"
            elif p.rd==0:
                return "C.HINT"
            elif p.rs2==0:
                return "C.JALR"
            else:
                return "C.EBREAK"
    ins_exec={
        0b00:{
            0b010:C_LW(),
            0b110:C_SW(),
        },
        0b01:{
            0b000:C_ADDI(),
            0b001:C_JAL(),
            0b010:C_LI(),
            0b011:C_LUI_ADDI16SP(),
        },
        0b10: {
            0b010: C_LWSP(),
            0b110: C_SWSP(),
            0b100: {
                0b0:C_JR_MV(),
                0b1:C_EBREAK_JALR_ADD(),
            }
        },
    }


