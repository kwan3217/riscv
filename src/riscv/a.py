"""
Implement the Risc-V atomic memory operations

Created: 6/11/24
"""
from dataclasses import dataclass
from typing import Callable, Mapping

import riscv.bits
from riscv.hart import InstructionSet, Hart, InstructionHandler, RVException, ExcCause
from riscv.bits import sign_extend
from riscv.memory import Misaligned


class A(InstructionSet):
    class Atomic(InstructionHandler):
        """
        Atomically perform the following operations:
        1) Load the value from mem[rs1].
        2) Read the original value from rs2.
        3) Perform the operation with the value from memory and the value in rs2.
        4) Place the loaded memory value in rd.
        5) Write the result back to mem[rs1].

        Atomic in this context means that the given memory address is marked to
        not be allowed to be changed by anything else which can read this memory.
        Older chips (8086 had a LOCK prefix to allow for multi-core) asserted a
        bus lock during the operation which prohibited any other bus master from
        using to the address bus, so the operation was:
        * Lock the bus
        * Put the address on the address bus
        * Read the memory
        * Put the value in rd
        * Perform the operation
        * write the result back to the same address
        * Release the lock
        Since the LOCK signal was asserted, no other chip was allowed to place
        any address on the address bus, so no other chip could read nor write
        while the LOCK signal is asserted.

        The present code is not anticipated to really use the memory in parallel,
        so we just perform the swap without worrying about atomicity.
        """
        def __init__(self,name:str,size:int,op:Callable[[int,int],int]):
            """

            :param name: Name of the operation to show in disassembly
            :param size: Size of operation. Only needs to work for 4 or 8 (in A64).
            :param op: Callable which takes two signed integers and returns the
                       value to be stored in the destination register, like this:
                def op(mem:int,rs2:int)->int:
                   '''
                   :param mem: Value from memory, signed integer
                   :param rs2: Value from rs2, signed integer.
                   :return: value to be stored in rd
            """
            self.name=name
            self.size=size
            self.op=op
            self.cast=f"i{self.size*8}"
        def execute(self, p: Mapping[str,int], hart: Hart) -> None:
            # 1) Load the value from mem[rs1]
            addr = hart.x[p['rs1']]  # base
            try:
                # Misaligned atomic operations are specifically disallowed UNLESS the physical memory area
                # granule permits it. PMA granules say that as long as the whole access occurs in one granule,
                # then it can proceed. Granules only make sense if they are *larger* than the word being accessed.
                # The idea is that only one granule in memory would need to be locked at a time, so it needs
                # to be bigger than one word so as to contain both parts of a misaligned word, but as small as is
                # reasonable such that as small a section of memory as possible is locked. Having said that, it is
                # conceivable for the "granule" to be the whole memory -- the whole memory is locked while an atomic
                # operation is ongoing. An example for a smaller granule -- Say we are on RV32 and the granule size
                # is 8 bytes. An atomic operation would:
                #   * succeed for address 0x00 because it is aligned
                #   * succeed for 0x01-0x03 because even though it's misaligned, the whole access is
                #     within the granule 0x00-0x07
                #   * succeed for address 0x04 because it's aligned
                #   * fail for 0x05-0x07 because part of the word hangs off the end of this granule into the next.
                # Since I haven't implemented PMA yet, we fall back on the "unaligned is prohibited" backstop.
                mem = hart.mem.load(self.size, addr,allow_misaligned=False)
            except Misaligned:
                # Defer throwing the RVException to here, where the hart with its pc is available
                raise RVException(message=f"Misaligned load: Addr=0x{addr:08x}, width={self.size}",
                                  is_interrupt=False,
                                  cause=ExcCause.LOAD_ADDRESS_MISALIGNED,
                                  epc=hart.pc,
                                  tval=addr
                                  )
            # 2) Place the value in rd. Value is always sign-extended, say if we do an amoxxx.W on RV64
            mem = sign_extend(mem, self.size * 8 - 1, hart.XLEN)
            # 3) Perform the operation with the value from memory and the value in rs2.
            rs2=hart.x[p['rs2']]
            # 4) Place the loaded memory value in rd.
            hart.x[p['rd']]=mem
            val_to_store=self.op(hart,mem,rs2)
            # 5) Write the value back to mem[rs1]. Don't worry about misalignment -- if it was misaligned, the load
            #    would have caught it.
            hart.mem.store(self.size,addr,val_to_store,allow_misaligned=True)
        def disasm(self, p: Mapping[str,int], XLEN: int):
            return f"{self.name:7s}{'.AQ' if p['imm']%4>0 else ''}{'.RL' if p['imm']%2>0 else ''} x{p['rd']:2},x{p['rs1']:2},(x{p['rs2']:2})"
        def formula(self, p: Mapping[str, int], XLEN: int):
            return f"{self.abi_regnames[p['rd']][self.nameidx]}={self.cast}(mem[{self.abi_regnames[p['rs1']][self.nameidx]}])"
    class AtomicSwap(Atomic):
        def __init__(self,name:str,size:int):
            # The operation returns rs2 because that's what will end up in mem and we're doing a swap.
            super().__init__(name,size,op=lambda hart,mem,rs2:rs2)
        def formula(self, p: Mapping[str, int], XLEN: int):
            return f"{self.abi_regnames[p['rd']][self.nameidx]}={self.cast}(mem[{self.abi_regnames[p['rs1']][self.nameidx]}]),mem[{self.abi_regnames[p['rs2']][self.nameidx]}]={self.cast}({self.abi_regnames[p['rs1']][self.nameidx]})"
    ins_exec={
        "____| 10 zzzzz lllll _|_ ddddd _|_||||":AtomicSwap('AMOSWAP.W',size=4),
        "_____ 10 zzzzz lllll _|_ ddddd _|_||||":Atomic('AMOADD.W', size=4,op=lambda hart,mem,rs2:mem+rs2),
        "__|__ 10 zzzzz lllll _|_ ddddd _|_||||":Atomic('AMOXOR.W', size=4, op=lambda hart,mem, rs2: mem^rs2),
        "_||__ 10 zzzzz lllll _|_ ddddd _|_||||":Atomic('AMOAND.W', size=4, op=lambda hart,mem, rs2: mem&rs2),
        "_|___ 10 zzzzz lllll _|_ ddddd _|_||||":Atomic('AMOOR.W', size=4, op=lambda hart,mem, rs2: mem|rs2),
        "|____ 10 zzzzz lllll _|_ ddddd _|_||||":Atomic('AMOMIN.W', size=4, op=lambda hart,mem, rs2: mem if hart.signed(rs2)>hart.signed(mem) else rs2),
        "|_|__ 10 zzzzz lllll _|_ ddddd _|_||||":Atomic('AMOMAX.W', size=4, op=lambda hart,mem, rs2: mem if hart.signed(rs2)<hart.signed(mem) else rs2),
        "||___ 10 zzzzz lllll _|_ ddddd _|_||||":Atomic('AMOMINU.W', size=4, op=lambda hart,mem, rs2: mem if hart.unsigned(rs2)>hart.unsigned(mem) else rs2),
        "|||__ 10 zzzzz lllll _|_ ddddd _|_||||":Atomic('AMOMAXU.W', size=4, op=lambda hart,mem, rs2: mem if hart.unsigned(rs2)<hart.unsigned(mem) else rs2),
    }
    def get_decode_table(self):
        return self.ins_exec


