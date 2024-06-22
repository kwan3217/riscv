"""
Describe purpose of this script here

Created: 6/22/24
"""


import io
import re
from subprocess import run


def read_syms(elffn:str):
    objdump = run(f"riscv64-unknown-elf-objdump -x {elffn}", capture_output=True, shell=True)
    if len(objdump.stderr) != 0:
        raise Exception(objdump.stderr)
    with io.TextIOWrapper(io.BytesIO(objdump.stdout)) as dumpf:
        for line in dumpf:
            if line.strip()=="SYMBOL TABLE:":
                break
        result={}
        for line in dumpf:
            line=line.strip()
            if match:=re.match(r"(?P<addr>[0-9a-f]+)\s+(?P<flags>[a-zA-Z! ]{7})\s+(?P<section>.+)\s+(?P<len>[0-9a-f]+)\s+(?P<symbol>.+)",line):
                addr=int(match.group("addr"),16)
                flags=match.group("flags")
                section=match.group("section")
                lenalign=match.group("len")
                sym=match.group("symbol")
                result[sym]=addr
    return result


def read_hex(hexfn:str=None, hexf: io.TextIOBase =None)->dict[int,int]:
    """
    Read an Intel Hex file

    :param hexfn: Name of file to load
    :return: dict -- key is address, value is byte at that address
    """
    result={}
    hiaddr=0
    if hexf is None:
        hexf=open(hexfn,"rt")
        needs_close=True
    else:
        needs_close=False
    try:
        for line in hexf:
            line=line.strip()
            bytecount=int(line[1:3],16)
            loaddr=int(line[3:7],16)
            rtype=int(line[7:9],16)
            stored_cksum=int(line[bytecount*2+9:bytecount*2+9+2],16)
            if rtype==0:
                data = bytes([int(line[i * 2 + 9:i * 2 + 9 + 2], 16) for i in range(bytecount)])
                # Data, stuff into memory at given addr
                for i,b in enumerate(data):
                    addr=loaddr+hiaddr*0x10000+i
                    result[addr]=b
            elif rtype==1:
                # End of file record
                break
            elif rtype==4:
                # Extended linear address (upper 16 bits of 32-bit address)
                hiaddr=int(line[9:13],16)
    finally:
        if needs_close:
            hexf.close()
    return result


def read_elf(elffn: str) -> dict[int,int]:
    """
    Read an ELF image

    :param elffn:
    :return: dict of symbols. Key is string name of symbol, val is parsed address
    """
    result = run(f"riscv64-unknown-elf-objcopy -O ihex {elffn} /dev/stdout",capture_output=True, shell=True)
    if len(result.stderr) != 0:
        raise RuntimeError(result.stderr)
    with io.TextIOWrapper(io.BytesIO(result.stdout)) as hexf:
        result=read_hex(hexf=hexf)
    return result

