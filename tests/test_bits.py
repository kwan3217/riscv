"""
Test bit-manipulation stuff_hex. Split from test_riscv.py (which itself was renamed test_imperas.py)

Created: 6/14/24
"""
import pytest

from riscv.hart import signed, sign_extend


@pytest.mark.parametrize(
    "val,width,ref",
    [ (0x8,3,-8),
      (0x0001,15, 1),
      (0x1234,15,0x1234),
      (0x8000,15,-32768),
      (0xffff,15,-1),
      (0xffffffff,31,-1),
      (0xffffffffffffffff, 63, -1),
      (0xffffffffffffffffffffffffffffffff, 127, -1),
      ]
)
def test_signed(val,width,ref):
    assert signed(val,width)==ref


@pytest.mark.parametrize(
    "val,sign_bit,width,ref",
    [(0b11,1,4,0b1111),
     (0b1101,3,32,   0b11111111111111111111111111111101),
     (0b1101, 4, 32, 0b00000000000000000000000000001101)
]
)
def test_sign_extend(val,sign_bit,width,ref):
    assert sign_extend(val,sign_bit,width)==ref


