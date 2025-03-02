"""
Implement the Supervisor (S) mode. This adds the CSRs and handlers
for this mode only.

Created: 2/26/25
"""
from typing import Mapping

from riscv import modeM, sv39
from riscv.bits import read_bitfield
from riscv.hart import Hart, InstructionSet, InstructionHandler
from riscv.memory import Memory


class ModeS(InstructionSet):
    class MMU(Memory):
        def __init__(self,hart:Hart,*args,**kwargs):
            super().__init__(*args,**kwargs)
            # Steal the physical memory from the hart, then install ourselves as the memory
            self.hart=hart
            self.phys_mem=hart.mem
            self.tlb={}
        def _translate_address(self,virtaddr:int):
            # Check the satp register
            satp=self.hart.csr["satp"]
            # This MMU is currently designed for RV64 only, so a 4-bit MODE field in bits 63-60
            mode=read_bitfield(satp,63,60)
            if mode==0: # Straight-through mapping
                return virtaddr
            else:
                # Virtual address active
                # split the address into a page number and offset, but use the address of the bottom of the
                # page because that's what the page table walker expects.
                virtpageaddr=read_bitfield(virtaddr,38,12)<<12
                ofs=read_bitfield(virtaddr,11,0)
                # Check the TLB
                if virtpageaddr in self.tlb:
                    physpageaddr=self.tlb[virtpageaddr]
                else:
                    physpageaddr=sv39.walk(phys_mem=self.phys_mem,satp=self.hart.csr["satp"],virtaddr=virtpageaddr)
                    self.tlb[virtpageaddr]=physpageaddr
                return physpageaddr + ofs
        def partial_tlb_flush(self,vma:int,asid:int):
            """
            Invalidate the TLB associated with the given virtual memory address
            and address space ID.
            :param vma: Virtual memory address. If None, invalidate all VMAs associated with the given asid
            :param asid: Address space ID. If None, invalidate all TLBs associated with the given VMA in any address space
            If both are None, do a full TLB flush.
            """
            # Do a full flush because it's simple and allowed.
            self.tlb={}
        def __getitem__(self,virtaddr:int):
            physaddr=self._translate_address(virtaddr)
            return self.phys_mem[physaddr]
        def __setitem__(self, virtaddr: int,data:int):
            physaddr = self._translate_address(virtaddr)
            self.phys_mem[physaddr]=data
    csrs = {
        #  Supervisor Trap Setup
        0x100: ("SRW", "sstatus", "Supervisor status register"),
        0x102: ("SRW", "sedeleg", "Supervisor exception delegation register"),
        0x103: ("SRW", "sideleg", "Supervisor interrupt delegation register"),
        0x104: ("SRW", "sie", "Supervisor interrupt-enable register"),
        0x105: ("SRW", "stvec", "Supervisor trap handler base address"),
        0x106: ("SRW", "scounteren", "Supervisor counter enable"),
        #  Supervisor Trap Handling
        0x140: ("SRW", "sscratch", "Scratch register for supervisor trap handlers"),
        0x141: ("SRW", "sepc", "Supervisor exception program counter"),
        0x142: ("SRW", "scause", "Supervisor trap cause"),
        0x143: ("SRW", "stval", "Supervisor bad address or instruction"),
        0x144: ("SRW", "sip", "Supervisor interrupt pending"),
        #  Supervisor Protection and Translation
        0x180: ("SRW", "satp", "Supervisor address translation and protection"),
    }
    def add_state(self,hart:Hart):
        hart.csr.add_regs(self.csrs)
        hart.mem = self.MMU(hart)
    class SFENCE_VMA(InstructionHandler):
        """
        Interface to manage the TLB. This informs the MMU that a given virtual
        address has a new mapping, and in practice the MMU acts on that knowledge
        by invalidating the TLB for that address.
        The given virtual address is held in rs1 and the given address space ID
        is held in rs2. x0 as either rs1 or rs2 is a special case -- this
        remaps all addresses in a given space and/or all address spaces
        for a given address. x0 as both remaps all addresses and the MMU should
        flush the whole TLB.
        """
        def __init__(self):
            self.name = "SFENCE.VMA"
        def execute(self, p: Mapping[str, int], hart: Hart) -> None:
            if p['rs1']==0:
                vma=None
            else:
                vma=hart.x[p['rs1']]
            if p['rs2']==0:
                asid=None
            else:
                asid=hart.x[p['rs2']]
            hart.mem.partial_tlb_flush(vma,asid)
        def disasm(self, p: Mapping[str, int], XLEN: int):
            return f"{self.name:7s} x{p['rs1']:2},(x{p['rs2']:2})"
        def formula(self, p: Mapping[str, int], XLEN: int):
            f=f"flush TLB"
            if p['rs1']!=0:
                f+=f" for virtual address {self.abi_regnames[p['rs1']][self.nameidx]}"
            if p['rs2']!=0:
                f+=f" in address space {self.abi_regnames[p['rs2']][self.nameidx]}"
    ins_exec = {
        ' ___|___ ___|_ _____ ___ _____ |||__||':modeM.ModeM.xRET("SRET",0x141),
        ' ___|__| zzzzz lllll ___ _____ |||__||':SFENCE_VMA()
    }
    def get_decode_table(self):
        return self.ins_exec


