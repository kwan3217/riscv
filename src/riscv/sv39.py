"""
Code dealing with sv39 paging mode.

Created: 2/28/25
"""
from collections import namedtuple

from riscv.bits import read_bitfield
from riscv.hart import RVException, ExcCause
from riscv.memory import Memory


class PageFault(RVException):
    def __init__(self,*,message:str=None):
        super().__init__(message,is_interrupt=False,cause=None,epc=None)


parsed_pte=namedtuple("ptetype","n pbmt res0 ppn2 ppn1 ppn0 rsw d a g u x w r v")
def parse_pte(pte:int)->parsed_pte:
    n = read_bitfield(pte, 63, 63)
    pbmt = read_bitfield(pte, 62, 61)
    res0 = read_bitfield(pte, 60, 54)
    ppn2 = read_bitfield(pte, 53, 28)
    ppn1 = read_bitfield(pte, 27, 19)
    ppn0 = read_bitfield(pte, 18, 10)
    rsw = read_bitfield(pte, 9, 8)
    d = read_bitfield(pte, 7, 7)
    a = read_bitfield(pte, 6, 6)
    g = read_bitfield(pte, 5, 5)
    u = read_bitfield(pte, 4, 4)
    x = read_bitfield(pte, 3, 3)
    w = read_bitfield(pte, 2, 2)
    r = read_bitfield(pte, 1, 1)
    v = read_bitfield(pte, 0, 0)
    return parsed_pte(n=n,pbmt=pbmt,res0=res0,
                      ppn2=ppn2,ppn1=ppn1,ppn0=ppn0,
                      rsw=rsw,
                      d=d,a=a,g=g,u=u,x=x,w=w,r=r,v=v)


def print_page_table(mem:Memory,addr:int):
    for i in range(512):
        pte=mem.load(8,addr+i*8)
        n,pbmt,_,ppn2,ppn1,ppn0,rsw,d,a,g,u,x,w,r,v=parse_pte(pte)
        ppa=ppn2<<30 | ppn1<<21 |ppn0<<12 | 0x000
        ppa0=read_bitfield(ppa,15, 0)
        ppa1=read_bitfield(ppa,31,16)
        ppa2=read_bitfield(ppa,47,32)
        ppa3=read_bitfield(ppa,55,48)
        row=(f"{i:03x} 0x{ppa3:02x}_{ppa2:04x}_{ppa1:04x}_{ppa0:04x} "
             f"{'D' if d else 'd'}"
             f"{'A' if a else 'a'}"
             f"{'G' if g else 'g'}"
             f"{'U' if u else 'u'}"
             f"{'X' if x else 'x'}"
             f"{'W' if w else 'w'}"
             f"{'R' if r else 'r'}"
             f"{'V' if v else 'v'}")
        if v:
            print(row)


def walk(phys_mem:Memory,satp:int,virtaddr:int)->int:
    """
    Walk the page table. Given a virtual address, start at the root
    of the page table given in satp, then follow it down using the
    page table index of each part of the address. Eventually this
    will handle megapages and gigapages but for now we don't.
    :param phys_mem:
    :param satp: Value of satp register, used to find the page table root
    :param virtaddr: Virtual address to translate
    :return: Physical address
    """
    # Split virtual address up
    vpn2=read_bitfield(virtaddr,38,30)
    vpn1=read_bitfield(virtaddr,29,21)
    vpn0=read_bitfield(virtaddr,20,12)
    ofs=read_bitfield(virtaddr,11,0)
    # TODO - This is where we have to verify canonical addresses
    #    bits 39-63 must all match bit 38
    ppnroot=read_bitfield(satp,43,0)
    paroot=ppnroot<<12
    pte2=phys_mem.load(8,paroot+vpn2*8,allow_misaligned=False)
    pte2=parse_pte(pte2)
    if not pte2.v:
        raise PageFault(f"Entry for vpn2=0x{vpn2:03x} isn't marked valid")
    pa2=pte2.ppn2<<30 | pte2.ppn1<<21 |pte2.ppn0<<12 | 0x000
    pte1=phys_mem.load(8,pa2+vpn1*8,allow_misaligned=False)
    pte1=parse_pte(pte1)
    if not pte1.v:
        raise PageFault(f"Entry for vpn2=0x{vpn2:03x},vpn1=0x{vpn1:03x} isn't marked valid")
    pa1=pte1.ppn2<<30 | pte1.ppn1<<21 |pte1.ppn0<<12 | 0x000
    pte0=phys_mem.load(8,pa1+vpn0*8,allow_misaligned=False)
    pte0=parse_pte(pte0)
    if not pte0.v:
        raise PageFault(f"Entry for vpn2=0x{vpn2:03x},vpn1=0x{vpn1:03x},vpn1=0x{vpn1:03x} isn't marked valid")
    physaddr=pte0.ppn2<<30 | pte0.ppn1<<21 |pte0.ppn0<<12 | ofs
    return physaddr


def main():
    pass


if __name__ == "__main__":
    main()
