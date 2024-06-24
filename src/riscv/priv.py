"""
Risc-V priveleged mode stuff. We will treat this as an extension
but it has a couple of other functions, including most importantly
what to do with a trap.

Created: 6/12/24
"""
from riscv.bits import read_bitfield


def trap(hart:'Hart',e:'RVException'):
    print(f"Handling {e}")
    hart.csr['mcause'] = e.cause.value | ((1 if e.is_interrupt else 0)<<31)
    hart.csr['mtval']=e.tval
    hart.csr['mepc']=e.epc # This is always the address of the instruction
                           #   that caused the exception/was interrupted.
                           #   It is up to the trap handler to decide to
                           #   advance the pc on return (indicating that the
                           #   trap handler emulated the instruction) or
                           #   not (indicating that the instruction can be
                           #   repeated, with some hope of success).
    hart.csr['mstatus']=0x00001800 # MPP=0x11. Don't know what this means yet.
    mtvec=hart.csr['mtvec']
    mode=read_bitfield(mtvec,1,0)
    mtvec=mtvec&~0x03 #Mask off the mode bits -- trap handlers are required to be
                      #aligned to 4 bytes.
    if e.is_interrupt:
        if mode==1:
            # vectored interrupt - treat mtvec as base of a table of 4-byte entries
            mtvec+=e.cause*4
    hart.pc=mtvec     # Jump to the trap handler


def main():
    pass


if __name__ == "__main__":
    main()
