"""

"""

from dataclasses import dataclass
from subprocess import run

from riscv.hart import read_bitfield, InstructionSet, Hart, Memory

from riscv.rv32i import RV32I, R, ParsedInstruction
from riscv.zicsr import Zicsr


class RV32C(InstructionSet):
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
        @staticmethod
        def op(ins):
            return read_bitfield(ins, 1, 0)
        @staticmethod
        def CR(ins:int)-> ParsedInstruction:
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
        @staticmethod
        def CI(ins:int)-> ParsedInstruction:
            """
            Parse instruction as if it's a CI-type (Compressed Immediate)
            :param ins: 16-bit number to parse as a RV32C CI instruction
            :return: ParsedInstruction with the valid fields set, and the other fields None
            """
            return ParsedInstruction(op=read_bitfield(ins, 1, 0),
                                     imm=read_bitfield(ins, 12, 12) << 5 | read_bitfield(ins, 6, 2),
                                     rd=read_bitfield(ins, 11, 7),
                                     rs1=read_bitfield(ins, 11, 7),
                                     funct=read_bitfield(ins, 15, 12))
        @staticmethod
        def CSS(ins:int)-> ParsedInstruction:
            """
            Parse instruction as if it's a CSS-type (Compressed Stack-relative Store)
            :param ins: 16-bit number to parse as a RV32C CSS instruction
            :return: ParsedInstruction with the valid fields set, and the other fields None
            """
            return ParsedInstruction(op=read_bitfield(ins, 1, 0),
                                     rs2=read_bitfield(ins, 6, 2),
                                     imm=read_bitfield(ins, 12, 7),
                                     funct=read_bitfield(ins, 15, 13))
        @staticmethod
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
        @staticmethod
        def CL(ins:int)-> ParsedInstruction:
            """
            Parse instruction as if it's a CL-type (Compressed Load)
            :param ins: 16-bit number to parse as a RV32C CSS instruction
            :return: ParsedInstruction with the valid fields set, and the other fields None
            """
            return ParsedInstruction(op=read_bitfield(ins, 1, 0),
                                     rd=read_bitfield(ins, 4, 2) + 8,
                                     imm=read_bitfield(ins, 12, 10) << 2 | read_bitfield(ins, 6, 5),
                                     rs1=read_bitfield(ins, 9, 7) + 8,
                                     funct=read_bitfield(ins, 15, 13))
        @staticmethod
        def CS(ins:int)-> ParsedInstruction:
            """
            Parse instruction as if it's a CS-type (Compressed Store)
            :param ins: 16-bit number to parse as a RV32C CSS instruction
            :return: ParsedInstruction with the valid fields set, and the other fields None
            """
            return ParsedInstruction(op=read_bitfield(ins, 1, 0),
                                     rs2=read_bitfield(ins, 4, 2) + 8,
                                     imm=read_bitfield(ins, 12, 10) << 2 | read_bitfield(ins, 6, 5),
                                     rs1=read_bitfield(ins, 9, 7) + 8,
                                     funct=read_bitfield(ins, 15, 13))
        @staticmethod
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
                                     funct=read_bitfield(ins, 15, 10) << 2 | read_bitfield(ins, 6, 5))
        @staticmethod
        def CB(ins:int)-> ParsedInstruction:
            """
            Parse instruction as if it's a CB-type (Compressed Branch)
            :param ins: 16-bit number to parse as a RV32C CSS instruction
            :return: ParsedInstruction with the valid fields set, and the other fields None
            """
            return ParsedInstruction(op=read_bitfield(ins, 1, 0),
                                     offset=read_bitfield(ins, 12, 10) << 5 | read_bitfield(ins, 6, 2),
                                     rs1=read_bitfield(ins, 9, 7) + 8,
                                     funct=read_bitfield(ins, 15, 13))
        @staticmethod
        def CJ(ins:int)-> ParsedInstruction:
            """
            Parse instruction as if it's a CJ-type (Compressed Jump)
            :param ins: 16-bit number to parse as a RV32C CSS instruction
            :return: ParsedInstruction with the valid fields set, and the other fields None
            """
            return ParsedInstruction(op=read_bitfield(ins, 1, 0),
                                     target=read_bitfield(ins, 12, 2),
                                     funct=read_bitfield(ins, 15, 13))
    @staticmethod
    def C_LWSP(hart: Hart, ins:int):
        p=RV32C.CI(ins)



# Note that Python ONLY does arithmetic shifts. However,
# arithmetic and logical shifts are the same if the number
# is positive, and all registers are positive unless
# explicitly cast to signed (which we won't do here)

# For this, we explicitly cast to signed, then do the right
# shift and cast back to unsigned by ANDing with the right
# bit mask.


def main():
    from test_riscv import test_imperas
    test_imperas("SB")


if __name__ == "__main__":
    main()