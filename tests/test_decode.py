"""
Test the decode module

Created: 6/19/24
"""
from collections import namedtuple

import pytest

from riscv.decode import decide, Handler, decode, compile_encodings

# Instructions in the RV32CI instruction set, those
# instructions that encode in the RV32I instruction
# set. This excludes:
#  * Floating point stuff
#  * Instructions which are not valid in RV32
# Reserved and Non-Standard extensions are defined as None,
# since they are usually more specific. The outer code
# will interpret finding a None as WrongExtension and
# look in the next one.
C32I_encodings={
    # Quadrant 0
    "___ ________ ___ __":"C.UNIM",  # Architecture-defined permanent illegal instruction
    "___ 549 876 23 eee __":Handler(name="C.ADDI4SPN",sign='+'), # Immediate is specified as zero-extended
    "__| 543 mmm 76 eee __":None, # C.FLD in C32/64F
    "__| 548 mmm 76 eee __":None, # C.LQ in C128I
    "_|_ 543 mmm 26 eee __":Handler(name="C.LW",sign='+'), # Immediate is specified as zero-extended
    "_|| 543 mmm 26 eee __":None,  # C.FLW in C32F
    "_|| 543 mmm 76 eee __":None,  # C.LD
    "|__ ... ... .. ... __":None,  # Reserved
    "|_| 543 mmm 76 yyy __":None,  # C.FSD in C32/64F
    "|_| 548 mmm 76 yyy __":None,  # C.SQ in C128I
    "||_ 543 mmm 26 yyy __":Handler(name="C.SW",sign='+'), # Likewise
    "||| 543 mmm 26 yyy __":None,  # C.FSW
    "||| 543 mmm 76 yyy __":None,  # C.SD
    # Quadrant 1
    "___ _ _____ _____ _|":"C.NOP",
    "___ 5 _____ 43210 _|":Handler(name="C.HINT1",sign='+'), #Treat it as unsigned zero-ext because it will be used as a bitfield
    "___ 5 fffff 43210 _|":Handler(name="C.ADDI"),  #Immediate must be nonzero and is sign-extended. Zero immediate is a hint.
    "___ _ 43210 _____ _|":Handler(name="C.HINT2",sign='+'),
    "__| B498A673215 _|":Handler(name="C.JAL"),     # Signed offset
    #"__| 5 fffff 43210 _|":None, # C.ADDIW in C64/128I
    "_|_ 5 ddddd 43210 _|":"C.LI",
    "_|_ 5 _____ 43210 _|":Handler("C.HINT3",sign='+'),
    "_|| 9 ___|_ 46875 _|":Handler("C.ADDI16SP"), #Nonzero sign-extended. Zero immediate is reserved.
    "_|| _ ___|_ _____ _|":None, # Reserved for future standard extensions, equivalent to C.ADDI16SP 0
    "_|| H ddddd GFEDC _|":Handler("C.LUI"),
    "_|| _ ddddd _____ _|":None, # Reserved
    "_|| 5 _____ 43210 _|":Handler(name="C.HINT4",sign='+'),
    "|__ _ __ ggg 43210 _|":"C.SRLI", # Bit 12 is nzimm5, which must be 0 for RV32C
    "|__ 5 __ ggg 43210 _|":None, #SRLI in C64/128I
    "|__ _ __ 210 _____ _|":Handler(name="C.HINT5",sign='+'), #C.SRLI64 in RV128C
    "|__ _ _| ggg 43210 _|":"C.SRAI", # Bit 12 is nzimm5, which must be 0 for RV32C
    "|__ 5 _| ggg 43210 _|":None,     # SRAI in C64/128I
    "|__ _ _| 210 _____ _|":Handler(name="C.HINT6",sign='+'),  # C.SRAI64 in RV128C
    "|__ 5 |_ ggg 43210 _|":Handler("C.ANDI"),
    "|__ _ || ggg __ yyy _|":Handler("C.SUB"),
    "|__ _ || ggg _| yyy _|":Handler("C.XOR"),
    "|__ _ || ggg |_ yyy _|":Handler("C.OR"),
    "|__ _ || ggg || yyy _|":Handler("C.AND"),
    "|__ | || ggg __ yyy _|":None, # C.SUBW
    "|__ | || ggg _| yyy _|":None, # C.ADDW
    "|__ | || ... |_ ... _|":None, # Reserved
    "|__ | || ... || ... _|":None, # Reserved
    "|_| B498A673215 _|":"C.J",
    "||_ 843 mmm 76215 _|":Handler(name="C.BEQZ"),
    "||| 843 mmm 76215 _|":Handler(name="C.BNEZ"),
    # Quadrant 2
    "___ _ fffff 43210 |_":Handler("C.SLLI",sign='+'), # Bit 12 is nzimm5, which must be 0 for C32I
    "___ 5 fffff 43210 |_":None, # C.SLLI on C64/128I, reserved for non-standard extensions on C32I
    "___ _ fffff _____ |_":Handler("C.HINT7",sign='+'), # C.SLLI rd,64 on C128I, hint on C32/64I
    "__| 5 ddddd 43876 |_":None, # C.FLDSP, C32/64F
    "__| 5 ddddd 49876 |_":None, # C.LQSP, C128I
    "_|_ 5 ddddd 43276 |_":Handler("C.LWSP",sign='+'),
    "_|_ 5 _____ 43276 |_":None, # Reserved, equivalent to C.LWSP x0,imm
    "_|| 5 ddddd 43276 |_":None, # C.FLWSP
    "_|| 5 ddddd 43876 |_":None, # C.LDSP, C64/128I
    "_|| 5 _____ 43876 |_":None, # Reserved, equivalent to C.LDSP x0,imm
    "|__ _ lllll _____ |_":Handler("C.JR"),  # Encoding that C.MV rd=x0 *would* have
    "|__ _ _____ _____ |_":None, # Reserved, equivalent to C.JR x0
    "|__ _ ddddd zzzzz |_":Handler("C.MV"),
    "|__ _ _____ zzzzz |_":Handler("C.HINT8"), # Equivalent to C.MV x0=rs2
    "|__ | _____ _____ |_":Handler("C.EBREAK"), # Encoding that C.ADD x0,x0 *would* have
    "|__ | lllll _____ |_":Handler("C.JALR"), # Encoding that C.ADD rs1/rd,x0 *would* have
    "|__ | fffff zzzzz |_":Handler("C.ADD"),
    "|__ | _____ zzzzz |_":Handler("C.HINT9"), # Encoding that C.ADD x0,rs2 *would* have
    "|_| 543876 zzzzz |_":None, # C.FSDSP, CF
    "|_| 549876 zzzzz |_":None, # C.SQSP, C128I
    "||_ 543276 zzzzz |_":Handler("C.SWSP"),
    "||| 543276 zzzzz |_":None, # C.FSWSP, C32F
    "||| 543876 zzzzz |_":None, # C.SDSP, C64/128F
}

C_encodings={}
C_encodings.update(C32I_encodings)


C_compiled_encodings=compile_encodings(C_encodings)


@pytest.mark.parametrize(
    'ins,decode_value',
    [
     (0b001_01010101010_01,'C.JAL'),
     (0b000_00000000_000_00,'C.UNIM'),
     (0b000_11100011_111_00,'C.ADDI4SPN'),
     (0b110_11100011_010_00,'C.SW'),
     (0b000_0_00000_00000_01,'C.NOP'),
     (0b000_1_00000_10101_01,'C.HINT1'),
     (0b000_0_00000_00001_01,'C.HINT1'),
     (0b000_0_10101_00001_01,'C.ADDI'),
     (0b000_0_10101_00000_01,'C.HINT2'),
     ]
)
def test_decide(ins:int,decode_value:str|None):
    decode_masks=None
    for masks,(fields,handler) in C_compiled_encodings.items():
        if handler is None:
            if decode_value is None:
                decode_masks=masks
                break
        elif type(handler) is str:
            if handler==decode_value:
                decode_masks=masks
                break
        elif handler.name==decode_value:
            decode_masks=masks
            break
    assert decide(ins,C_compiled_encodings)==decode_masks


@pytest.mark.parametrize(
    'ins,decode_value,ref_fields',
    [
           #B498A673215                   # BA9876543210
     (0b001_01010101010_01,'C.JAL',{'imm':0b000101011010}),
     (0b000_00000000_000_00,'C.UNIM',{}),
           #54987623                                     # 9876543210
     (0b000_11100011_111_00,'C.ADDI4SPN',{'rd':7+8,'imm':0b1000111100}),
           #543mmm26 yyy                                     #  6543210
     (0b110_11100011_010_00,'C.SW',{'rs1':0+8,'rs2':2+8,'imm':0b1111100}),
     (0b000_0_00000_00000_01,'C.NOP',{}),
           #5       43210                    #  543210
     (0b000_1_00000_10101_01,'C.HINT1',{'imm':0b110101}),
     (0b000_0_00000_00001_01,'C.HINT1',{'imm':0b000001}),
           #5 rs1rd 43210                                                # 543210
     (0b000_0_10101_00001_01,'C.ADDI' ,{'rs1':0b10101,'rd':0b10101,'imm':0b000001}),
           #  43210                           # 43210
     (0b000_0_10101_00000_01,'C.HINT2',{'imm':0b10101}),
     ]
)
def test_decode(ins:int,decode_value:str|None,ref_fields:dict[str,int]):
    test_fields,handler=decode(ins,C_compiled_encodings)
    if type(handler)==str:
        assert handler==decode_value
    else:
        assert handler[0]==decode_value
    for test_name,test_value in test_fields.items():
        assert test_name in ref_fields,f"Found field {test_name} that is in test_fields but not ref_fields"
    for ref_name,ref_value in ref_fields.items():
        assert ref_name in test_fields,f"Found field {ref_name} that is in ref_fields but not test_fields"
    for test_name,test_value in test_fields.items():
        assert test_value==ref_fields[test_name],f"Found field {test_name} that didn't match, {test_value=:016b}, ref_value={ref_fields[test_name]:016b}"