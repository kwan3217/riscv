"""
Stuff to deal with ELF images

Created: 6/15/24
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


