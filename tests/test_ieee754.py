"""
Describe purpose of this script here

Created: 6/26/24
"""

import pytest

from ieee754.softfloat import softfloat, packfloat


def test_softfloat_add():
    num1=softfloat(q=2-24,significand=0x80_00_00)
    print(f"{num1=}, {float(num1)=}")
    num2=softfloat(q=-1-24,significand=0x80_00_00)
    print(f"{num2=}, {float(num2)=}")
    result=num2+num1
    print(f"num1+num2, {result=}, {float(result)=}")
    result=num2-num1
    print(f"num2-num1, {result=}, {float(result)=}")
    result=num1*num2
    print(f"num1*num2, {result=}, {float(result)=}")


def test_packfloat():
    num1=packfloat(q=2-24,significand=0x80_00_00,k=32)
    print(num1.pack())