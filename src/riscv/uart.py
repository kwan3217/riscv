"""
Implement an emulation of a 16550A UART

Created: 2/28/25
"""
from riscv.memory import Memory


class UART16550(Memory):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.ier=0
        self[5]=0x20 # Set the status word to always indicate ready to transmit
    def is_dlab(self):
        return self[0b11] & 0x80>0
    def __getitem__(self,addr):
        if addr==0 and not self.is_dlab():
            # RHR - do a read of one character from stdin. Not currently implemented
            raise NotImplementedError
        elif addr==1 and not self.is_dlab():
            # IER - this overlaps address with divisor latch high, but divisor latch high is stored in normal Memory
            return self.ier
        else:
            return super().__getitem__(addr)
    def __setitem__(self,addr,data):
        if addr==0 and not self.is_dlab():
            #print(f"UART Tx: 0x{data:02x}, {chr(data)}")
            print(f"{chr(data)}",end='')
        elif addr==1 and not self.is_dlab():
            # IER - this overlaps address with divisor latch high, but divisor latch high is stored in normal Memory
            self.ier=data
        else:
            super().__setitem__(addr,data)


