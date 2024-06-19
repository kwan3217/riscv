"""
Test the decode module

Created: 6/19/24
"""
from collections import namedtuple

import pytest

from riscv.decode import compiled_encoding_bitmask, decide, C_compiled_encodings, decode


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