"""
Implement the Risc-V 32-bit integer base instructions

Created: 6/11/24
"""
from dataclasses import dataclass
from typing import Callable

from riscv.hart import InstructionSet, Hart, InstructionInterpreter, WrongInterpreter, \
    Memory, IllegalInstruction
from riscv.bits import read_bitfield, read_bitfields
from riscv.rv32i import ParsedInstruction, I


def decode(ins: int) -> ParsedInstruction:
    return ParsedInstruction(opcode=read_bitfield(ins, 6, 0),
                             rd=read_bitfield(ins, 11, 7),
                             funct3=read_bitfield(ins, 14, 12),
                             rs1=read_bitfield(ins, 19, 15),
                             imm=read_bitfields(ins, ((31, 20, 0),), 12, False))


# This is literally copied, pasted, and reformatted from privisa Table 2.2
csrnames = {
    #i_csr priv   name       desc
    #  User Trap Setup
    0x000:("URW","ustatus" ,"User status register"),
    0x004:("URW","uie"     ,"User interrupt-enable register"),
    0x005:("URW","utvec"   ,"User trap handler base address"),
    #  User Trap Handling
    0x040:("URW","uscratch","Scratch register for user trap handlers"),
    0x041:("URW","uepc"    ,"User exception program counter"),
    0x042:("URW","ucause"  ,"User trap cause"),
    0x043:("URW","utval"   ,"User bad address or instruction"),
    0x044:("URW","uip"     ,"User interrupt pending"),
    #  User Floating-Point CSRs
    0x001:("URW","fflags"  ,"Floating-Point Accrued Exceptions"),
    0x002:("URW","frm"     ,"Floating-Point Dynamic Rounding Mode"),
    0x003:("URW","fcsr"    ,"Floating-Point Control and Status Register (frm + fflags)"),
    #  User Counter/Timers
    0xC00:("URO","cycle"   ,"Cycle counter for RDCYCLE instruction"),
    0xC01:("URO","time"    ,"Timer for RDTIME instruction"),
    0xC02:("URO","instret" ,"Instructions-retired counter for RDINSTRET instruction"),}|{
    0xC00+x:("URO",f"hpmcounter{x}","Performance-monitoring counter") for x in range(3,32)}|{
    0xC80:("URO","cycleh"  ,"Upper 32 bits of cycle, RV32I only"),
    0xC81:("URO","timeh"   ,"Upper 32 bits of time, RV32I only"),
    0xC82:("URO","instreth","Upper 32 bits of instret, RV32I only"),}|{
    0xC80+x:("URO",f"hpmcounter{x}h","Upper 32 bits of hpmcounter{x}, RV32I only") for x in range(3,32)}|{
    #  Supervisor Trap Setup
    0x100:("SRW","sstatus","Supervisor status register"),
    0x102:("SRW","sedeleg","Supervisor exception delegation register"),
    0x103:("SRW","sideleg","Supervisor interrupt delegation register"),
    0x104:("SRW","sie","Supervisor interrupt-enable register"),
    0x105:("SRW","stvec","Supervisor trap handler base address"),
    0x106:("SRW","scounteren","Supervisor counter enable"),
    #  Supervisor Trap Handling
    0x140:("SRW","sscratch","Scratch register for supervisor trap handlers"),
    0x141:("SRW","sepc","Supervisor exception program counter"),
    0x142:("SRW","scause","Supervisor trap cause"),
    0x143:("SRW","stval","Supervisor bad address or instruction"),
    0x144:("SRW","sip","Supervisor interrupt pending"),
    #  Supervisor Protection and Translation
    0x180:("SRW","satp","Supervisor address translation and protection"),
    #  Machine Information Registers
    0xF11:("MRO","mvendorid","Vendor ID"),
    0xF12:("MRO","marchid","Architecture ID"),
    0xF13:("MRO","mimpid","Implementation ID"),
    0xF14:("MRO","mhartid","Hardware thread ID"),
    #  Machine Trap Setup
    0x300:("MRW","mstatus","Machine status register"),
    0x301:("MRW","misa","ISA and extensions"),
    0x302:("MRW","medeleg","Machine exception delegation register"),
    0x303:("MRW","mideleg","Machine interrupt delegation register"),
    0x304:("MRW","mie","Machine interrupt-enable register"),
    0x305:("MRW","mtvec","Machine trap-handler base address"),
    0x306:("MRW","mcounteren","Machine counter enable"),
    #  Machine Trap Handling
    0x340:("MRW","mscratch","Scratch register for machine trap handlers"),
    0x341:("MRW","mepc","Machine exception program counter"),
    0x342:("MRW","mcause","Machine trap cause"),
    0x343:("MRW","mtval","Machine bad address or instruction"),
    0x344:("MRW","mip","Machine interrupt pending"),
    #  Machine Memory Protection
    0x3A0:("MRW","pmpcfg0","Physical memory protection configuration"),
    0x3A1:("MRW","pmpcfg1","Physical memory protection configuration, RV32 only"),
    0x3A2:("MRW","pmpcfg2","Physical memory protection configuration"),
    0x3A3:("MRW","pmpcfg3","Physical memory protection configuration, RV32 only"),}|{
    0x3B0+x:("MRW",f"pmpaddr{x}","Physical memory protection address register") for x in range(0,16)}|{
    #  Machine Counter/Timers
    0xB00:("MRW","mcycle"  ,"Machine cycle counter"),
    0xB02:("MRW","minstret","Machine instructions-retired counter")}|{
    0xB00+x:("MRW",f"mhpmcounter{x}","Machine performance-monitoring counter") for x in range(3,32)}|{
    0xB80:("MRW","mcycleh","Upper 32 bits of mcycle, RV32I only"),
    0xB82:("MRW","minstreth","Upper 32 bits of minstret, RV32I only"),}|{
    0xB80+x:("MRW", f"mhpmcounter{x}h", f"Upper 32 bits of mhpmcounter{x}, RV32I only") for x in range(3, 32)}|{
    #  Machine Counter Setup
    0x320:("MRW","mcountinhibit","Machine counter-inhibit register"),}|{
    0x320+x:("MRW", f"mhpmevent{x}", "Machine performance-monitoring event selector") for x in range(3, 32)}|{
    #  Debug/Trace Registers (shared with Debug Mode)
    0x7A0:("MRW","tselect Debug/Trace trigger register select"),
    0x7A1:("MRW","tdata1 First Debug/Trace trigger data register"),
    0x7A2:("MRW","tdata2 Second Debug/Trace trigger data register"),
    0x7A3:("MRW","tdata3 Third Debug/Trace trigger data register"),
    #  Debug Mode Registers
    0x7B0:("DRW","dcsr","Debug control and status register"),
    0x7B1:("DRW","dpc","Debug PC"),
    0x7B2:("DRW","dscratch0","Debug scratch register 0"),
    0x7B3:("DRW","dscratch1","Debug scratch register 1"),}


class CSR(Memory):
    def __getitem__(self,key):
        if key not in csrnames:
            raise IllegalInstruction(f"Tried to read CSR[0x{key:03x}] which doesn't exist")
        if key not in self:
            super().__setitem__(key,0)
        value=super().__getitem__(key)
        print(f"Read  CSR[0x{key:03x}{' ('+csrnames[key][1]+')' if key in csrnames else ''}], value=0x{value:08x}  {' # '+csrnames[key][2] if key in csrnames else ''}")
        return value
    def __setitem__(self,key,value):
        if key not in csrnames:
            raise IllegalInstruction(f"Tried to write to CSR[0x{key:03x}] which doesn't exist")
        print(f"Write CSR[0x{key:03x}{' ('+csrnames[key][1]+')' if key in csrnames else ''}], value=0x{value:08x} {' # '+csrnames[key][2] if key in csrnames else ''}")
        value=super().__setitem__(key,value)


class Zicsr(InstructionSet):
    """
    Implement the CSRs (Control and Status Registers). This is a separate 12-bit address
    space which may be sparse. Access to these registers is restricted:
        * Reading from a nonexistent CSR causes an Illegal Instruction exception
        * Writing to a nonexistent CSR causes an Illegal Instruction exception
        * Reading or writing to a CSR without enough privilege causes an Illegal Instruction exception
        * Writing to a read-only CSR causes an Illegal Instruction exception
        * If a register is partially writable and partially read-only, writes to read-only bits are
          ignored and do not cause an exception. Simultaneous writes to writable bits are successful.
    This emulator will enforce these restrictions.
    """
    def add_state(self,hart:Hart):
        hart.csr=CSR()
    def interpret(self, hart: Hart, ins: int)->bool:
        p=decode(ins)
        if p.opcode!=0b1110011:
            raise WrongInterpreter("Not a system instruction")
        ins_type = self.ins_exec[p.funct3]
        if ins_type is None:
            raise WrongInterpreter("Instruction not in Zicsr table")
        elif not isinstance(ins_type, InstructionInterpreter):
            if p.imm not in ins_type:
                raise WrongInterpreter()
            ins_type=ins_type[p.imm]
        print(f"{hart.pc:08x} -- {ins:08x}  {ins_type.disasm(ins,hart.XLEN)}  # {ins_type.formula(ins,hart.XLEN)}")
        ins_type.execute(ins, hart)
    ins_exec = [None for func3 in range(8)]
    class xRET(InstructionInterpreter):
        """
        Return to a different privilege level. For now we just
        copy the correct CSR (determined by which privilege level
        we are going to) to the pc
        """

        def __init__(self, name: str, csr:int):
            self.name = name
            self.csr = csr
        def execute(self, ins: int, hart: Hart) -> None:
            hart.pc=hart.csr[self.csr]
        def disasm(self, ins: int, XLEN: int):
            return f"{self.name:7s}"
        def formula(self, ins: int, XLEN: int):
            name=f"0x{self.csr:03x}"
            if self.csr in csrnames:
                name+=f" ({csrnames[self.csr][1]})"
            return f"pc=CSR[{name}]"
    ins_exec[0b000]={}
    ins_exec[0b000][0b0011000_00010]=xRET("MRET",0x341)

    class CSRR(InstructionInterpreter):
        """
        CSR Read and Set -- perform the following two operations
        simultaneously and atomically:

        * If rd isn't x0, then read the CSR and write it to rd,
          triggering whatever side effects a read of that CSR
          may have. If rd *is* x0, don't read the CSR and don't
          trigger the read side-effects.
        * For every bit position that is set in rs1, set the
          corresponding bit in the CSR, if the bit is writable.
          Trying to set a non-writable bit is ignored and does
          not trigger an exception.
        """
        def __init__(self,name:str,symbol:str,op:Callable[[int,int],int]):
            self.format = I
            self.name=name
            self.symbol=symbol
            self.op=op
        def execute(self, ins: int, hart: Hart) -> None:
            p = decode(ins)
            if p.rd==0:
                # Special case -- if would copy csr to x0, instead
                # don't read csr at all and don't trigger any read
                # side-effects. Just write rs1 to csr.
                old_csr=0
            else:
                old_csr = hart.csr[p.imm]
            old_reg=hart.x[p.rs1]
            hart.x[p.rd]=old_csr
            # Special case: If using rs1=0, IE x0 as mask, don't
            # write to the csr at all and don't trigger any write
            # side effects.
            if p.rs1!=0:
                hart.csr[p.imm]=self.op(old_csr,old_reg)
        def disasm(self, ins: int, XLEN: int):
            p = decode(ins)
            return f"{self.name:7s}x{p.rd:2},x{p.rs1:2},{p.imm:12}"
        def formula(self, ins: int, XLEN: int):
            p = decode(ins)
            name=f"0x{p.imm:03x}"
            if p.imm in csrnames:
                name+=f" ({csrnames[p.imm][1]})"
            if p.rd==0:
                return f"CSR[{name}]{self.symbol}{self.abi_regnames[p.rs1][self.nameidx]}"
            elif "CSRRS"==self.name and p.rs1==0:
                return f"{self.abi_regnames[p.rd][self.nameidx]}=CSR[{name}]"
            else:
                return f"{self.abi_regnames[p.rd][self.nameidx]}=CSR[{name}],CSR[{name}]{self.symbol}{self.abi_regnames[p.rs1][self.nameidx]}"
    class CSRRW(InstructionInterpreter):
        """
        CSR Read and Write -- perform the following two operations
        simultaneously and atomically:

        * If rd isn't x0, then read the CSR and write it to rd,
          triggering whatever side effects a read of that CSR
          may have. If rd *is* x0, don't read the CSR and don't
          trigger the read side-effects.
        * Write the value in rs1 to the CSR.

        """
        def execute(self, ins: int, hart: Hart) -> None:
            p = decode(ins)
            if p.rd==0:
                # Special case -- if would copy csr to x0, instead
                # don't read csr at all and don't trigger any read
                # side-effects. Just write rs1 to csr.
                old_csr=0
            else:
                # Normal case -- simultaneously copy csr to rd and rs1 to csr. When done,
                # rd will have old csr value and csr will have old rs1 value. It is
                # specifically allowed for rd==rs1, which results in a proper swap.
                old_csr=hart.csr[p.imm]
            old_reg=hart.x[p.rs1]
            hart.x[p.rd]=old_csr
            hart.csr[p.imm]=old_reg
        def disasm(self, ins: int, XLEN: int):
            p = decode(ins)
            return f"CSRRW  x{p.rd:2},x{p.rs1:2},{p.imm:12}"
        def formula(self, ins: int, XLEN: int):
            p = decode(ins)
            name=f"0x{p.imm:03x}"
            if p.imm in csrnames:
                name+=f" ({csrnames[p.imm][1]})"
            if p.rd==0:
                return f"CSR[{name}]={self.abi_regnames[p.rs1][self.nameidx]}"
            else:
                return f"{self.abi_regnames[p.rd][self.nameidx]}=CSR[{name}],CSR[{name}]={self.abi_regnames[p.rs1][self.nameidx]}"
    class CSRI(InstructionInterpreter):
        """
        CSR Read and Set Immediate -- Same as above, but use an immediate value instead of
          a register as the source.

        This one is a bit weird in that it is an I-type, but the rs1 slot is interpreted as
        a 5-bit unsigned immediate instead of a register number.
        """
        def __init__(self,name:str,symbol:str,op:Callable[[int,int],int]):
            self.format = I
            self.name=name
            self.symbol=symbol
            self.op=op
        def execute(self, ins: int, hart: Hart) -> None:
            p = decode(ins)
            if p.imm not in hart.csr:
                hart.csr[p.imm]=0
            if p.rd==0:
                # Special case -- if would copy csr to x0, instead
                # don't read csr at all and don't trigger any read
                # side-effects. Just write rs1 to csr.
                hart.csr[p.imm]=self.op(hart.csr[p.imm],p.rs1)
            # Normal case -- simultaneously copy csr to rd and rs1 to csr. When done,
            # rd will have old csr value and csr will have old rs1 value. if rd==rs1,
            # this is an atomic swap.
            old_csr=hart.csr[p.imm]
            old_reg=p.rs1
            hart.csr[p.imm]=self.op(old_csr,old_reg)
            hart.x[p.rd]=old_csr
        def disasm(self, ins: int, XLEN: int):
            p = decode(ins)
            return f"{self.name:7s}x{p.rd:2},{p.rs1:2},{p.imm:12}"
        def formula(self, ins: int, XLEN: int):
            p = decode(ins)
            name=f"0x{p.imm:03x}"
            if p.imm in csrnames:
                name+=f" ({csrnames[p.imm][1]})"
            if p.rd==0:
                return f"CSR[{name}]{self.symbol}{p.rs1}"
            else:
                return f"{self.abi_regnames[p.rd][self.nameidx]}=CSR[{name}],CSR[{name}]{self.symbol}{p.rs1}"
    ins_exec[0b001]=CSRRW()
    ins_exec[0b010]=CSRR("CSRRS","|=",lambda csr,rs1:csr|rs1)
    ins_exec[0b011]=CSRR("CSRRC","&=~",lambda csr,rs1:csr&~rs1)
    ins_exec[0b101]=CSRI("CSRRWI","=",lambda csr,rs1:rs1)
    ins_exec[0b110]=CSRI("CSRRSI","|=",lambda csr,rs1:csr|rs1)
    ins_exec[0b111]=CSRI("CSRRCI","&=~",lambda csr,rs1:csr&~rs1)
