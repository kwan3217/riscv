"""
Implement the Risc-V 32-bit integer base instructions

Created: 6/11/24
"""
from dataclasses import dataclass
from typing import Callable, Mapping

from riscv.hart import InstructionSet, Hart, InstructionHandler
from riscv.memory import Memory


class NoSuchCSR(Exception):
    pass


class CSR(Memory):
    # This is solely the registers not attached to any particular privilege mode. As it turns out, there aren't any.

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.csrname_index={}
        self.csrnames={}
    def add_reg(self,i:int,access:str,name:str,comment:str,
                rside:Callable[[Hart,int],int]=None,
                wside:Callable[[Hart,int],int]=None,
                cside:Callable[[Hart],int]=None):
        """
        Add a CSR
        :param i: Address of register
        :param access: Access mode string:
          First character - minimum privilege needed to read the register
                 'U'=user mode or better, 'S'=supervisor mode or better, 'M'=machine mode
          Second two control access direction
                 'RW' Read-write
                 'RO' Read-only
        :param name: Official name of register in all lower-case
        :param comment: Official comment on register
        :param rside: Read side effect. Callable that takes a hart and the value which is stored
                      in the array. Return value is the actual value to be recieved by the hart.
                      None is the same as lambda hart,val:val. Callable is allowed to modify hart
                      state, including access any register, memory address, CSR, etc. Callable is
                      allowed to create host output.
        :param wside: Write side effect. Callable that takes a hart and the value which the hart
                      gave to be written to the register. Return value is the value which will
                      actually be stored in the array. Similarly callable is allowed to have
                      arbitrary effect on the hart state.
        :param cside: Cycle side effect. Callable that takes a hart and value currently stored in
                      the array for this register. Return value is value to be written back to the
                      CSR storage. Callable is allowed to have arbitrary effect on the hart state.
        """
        self.csrname_index[name]=i
        self.csrnames[i]=(access,name,comment,rside,wside,cside)
    def add_regs(self,regs:dict[int,tuple[str,str,str]]):
        """
        Add multiple registers to the CSRs
        :param regs: Dictionary. Key is 12-bit CSR address, value is tuple of access mode, name, and comment
        """
        for i,(access,name,comment,*rest) in regs.items():
            if len(rest)>0:
                rside,wside,cside=rest
            else:
                rside,wside,cside=None,None,None
            self.add_reg(i,access,name,comment,rside,wside,cside)
    def __getitem__(self,key):
        if type(key)==str:
            try:
                key=self.csrname_index[key]
            except IndexError:
                raise IndexError(f"CSR name {key} not found")
        if key not in self.csrnames:
            raise NoSuchCSR(f"Tried to read CSR[0x{key:03x}] which doesn't exist")
        if key not in self:
            super().__setitem__(key,0)
        value=super().__getitem__(key)
        if self.verbose:
            print(f"  CSR[0x{key:03x}{' ('+self.csrnames[key][1]+')' if key in self.csrnames else ''}]->value=0x{value:08x} {' # '+self.csrnames[key][2] if key in self.csrnames else ''}")
        return value
    def __setitem__(self,key,value):
        if type(key)==str:
            try:
                key=self.csrname_index[key]
            except IndexError:
                raise IndexError(f"CSR name {key} not found")
        if key not in self.csrnames:
            raise NoSuchCSR(f"Tried to write to CSR[0x{key:03x}] which doesn't exist")
        if self.verbose:
            print(f"  CSR[0x{key:03x}{' ('+self.csrnames[key][1]+')' if key in self.csrnames else ''}]<-value=0x{value:08x} {' # '+self.csrnames[key][2] if key in self.csrnames else ''}")
        super().__setitem__(key,value)
    def cycle_side_effect(self,hart:Hart):
        for addr,(access,name,comment,rside,wside,cside) in self.csrnames.items():
            if cside is not None:
                self[addr]=cside(hart,self[addr])


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
    def __init__(self,verbose:bool=False):
        self.verbose=verbose
    def add_state(self,hart:Hart):
        hart.csr=CSR(verbose=self.verbose)

    class CSRR(InstructionHandler):
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
            """

            :param name: Name of instruction
            :param symbol: Symbol for operation
            :param op: Callable which calculates the value to be stored in the CSR
            """
            self.name=name
            self.symbol=symbol
            self.op=op
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            if p['rd']==0:
                # Special case -- if would copy csr to x0, instead
                # don't read csr at all and don't trigger any read
                # side-effects. Just write rs1 to csr.
                old_csr=0
            else:
                old_csr = hart.csr[p['imm']]
            old_reg=hart.x[p['rs1']]
            hart.x[p['rd']]=old_csr
            # Special case: If using rs1=0, IE x0 as mask, don't
            # write to the csr at all and don't trigger any write
            # side effects.
            if p['rs1']!=0:
                hart.csr[p['imm']]=self.op(old_csr,old_reg)
        def disasm(self, p: Mapping[str,int], hart:Hart):
            return f"{self.name:7s}x{p['rd']:2},x{p['rs1']:2},{p['imm']:12}"
        def formula(self, p: Mapping[str,int], hart:Hart):
            name=f"0x{p['imm']:03x}"
            if p['imm'] in hart.csr.csrnames:
                name+=f" ({hart.csr.csrnames[p['imm']][1]})"
            if p['rd']==0:
                return f"CSR[{name}]{self.symbol}{self.abi_regnames[p['rs1']][self.nameidx]}"
            elif "CSRRS"==self.name and p['rs1']==0:
                return f"{self.abi_regnames[p['rd']][self.nameidx]}=CSR[{name}]"
            else:
                return f"{self.abi_regnames[p['rd']][self.nameidx]}=CSR[{name}],CSR[{name}]{self.symbol}{self.abi_regnames[p['rs1']][self.nameidx]}"
    class CSRRW(InstructionHandler):
        """
        CSR Read and Write -- perform the following two operations
        simultaneously and atomically:

        * If rd isn't x0, then read the CSR and write it to rd,
          triggering whatever side effects a read of that CSR
          may have. If rd *is* x0, don't read the CSR and don't
          trigger the read side-effects.
        * Write the value in rs1 to the CSR.

        """
        def execute(self, p:Mapping[str,int], hart: Hart) -> None:
            if p['rd']==0:
                # Special case -- if would copy csr to x0, instead
                # don't read csr at all and don't trigger any read
                # side-effects. Just write rs1 to csr.
                old_csr=0
            else:
                # Normal case -- simultaneously copy csr to rd and rs1 to csr. When done,
                # rd will have old csr value and csr will have old rs1 value. It is
                # specifically allowed for rd==rs1, which results in a proper swap.
                old_csr=hart.csr[p['imm']]
            old_reg=hart.x[p['rs1']]
            hart.x[p['rd']]=old_csr
            hart.csr[p['imm']]=old_reg
        def disasm(self, p:Mapping[str,int], hart:Hart):
            return f"CSRRW  x{p['rd']:2},x{p['rs1']:2},{p['imm']:12}"
        def formula(self, p:Mapping[str,int], hart:Hart):
            name=f"0x{p['imm']:03x}"
            if p['imm'] in hart.csr.csrnames:
                name+=f" ({hart.csr.csrnames[p['imm']][1]})"
            if p['rd']==0:
                return f"CSR[{name}]={self.abi_regnames[p['rs1']][self.nameidx]}"
            else:
                return f"{self.abi_regnames[p['rd']][self.nameidx]}=CSR[{name}],CSR[{name}]={self.abi_regnames[p['rs1']][self.nameidx]}"
    class CSRI(InstructionHandler):
        """
        CSR Read and Set Immediate -- Same as above, but use an immediate value instead of
          a register as the source.

        This one is a bit weird in that it is an I-type, but the rs1 slot is interpreted as
        a 5-bit unsigned immediate instead of a register number.
        """
        def __init__(self,name:str,symbol:str,op:Callable[[int,int],int]):
            self.name=name
            self.symbol=symbol
            self.op=op
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            if p['imm'] not in hart.csr:
                hart.csr[p['imm']]=0
            if p['rd']==0:
                # Special case -- if would copy csr to x0, instead
                # don't read csr at all and don't trigger any read
                # side-effects. Just write rs1 to csr.
                hart.csr[p['imm']]=self.op(hart.csr[p['imm']],p['rs1'])
            # Normal case -- simultaneously copy csr to rd and rs1 to csr. When done,
            # rd will have old csr value and csr will have old rs1 value. if rd==rs1,
            # this is an atomic swap.
            old_csr=hart.csr[p['imm']]
            old_reg=p['rs1']
            hart.csr[p['imm']]=self.op(old_csr,old_reg)
            hart.x[p['rd']]=old_csr
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"{self.name:7s}x{p['rd']:2},{p['rs1']:2},{p['imm']:13}"
        def formula(self, p: Mapping[str,int], XLEN: int):
            name=f"0x{p['imm']:03x}"
            if p['imm'] in csrnames:
                name+=f" ({csrnames[p['imm']][1]})"
            if p['rd']==0:
                return f"CSR[{name}]{self.symbol}{p['rs1']}"
            else:
                return f"{self.abi_regnames[p['rd']][self.nameidx]}=CSR[{name}],CSR[{name}]{self.symbol}{p['rs1']}"
    ins_exec={
        '+BA9876543210 lllll __| ddddd |||__||':CSRRW(),
        '+BA9876543210 lllll _|_ ddddd |||__||':CSRR("CSRRS" ,"|=" ,lambda csr,rs1:csr|rs1),
        '+BA9876543210 lllll _|| ddddd |||__||':CSRR("CSRRC" ,"&=~",lambda csr,rs1:csr&~rs1),
        '+BA9876543210 lllll |_| ddddd |||__||':CSRI("CSRRWI", "=" ,lambda csr,rs1:rs1),     # For CSRI, we have to encode *two* immediates,
        '+BA9876543210 lllll ||_ ddddd |||__||':CSRI("CSRRSI","|=" ,lambda csr,rs1:csr|rs1), #     one for the CSR index and one for the value to use.
        '+BA9876543210 lllll ||| ddddd |||__||':CSRI("CSRRCI","&=~",lambda csr,rs1:csr&~rs1),#     We use the rs1 slot for the value.
    }
    def get_decode_table(self):
        return self.ins_exec
