"""
Module defining a byte-addressed memory

Created: 6/18/24
"""
import io
from subprocess import run

from elf import read_syms
from riscv.bits import read_bitfield


def main():
    pass
    
    
if __name__=="__main__":
    main()


class Memory(dict):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.lbreak=set()
        self.sbreak = set()
    def __missing__(self,k):
        return 0
    def load(self,width,baseaddr):
        """
        Loads a little-endian value of arbitrary width from the memory
        :param baseaddr:
        :param width:
        :return:
        """
        result=0
        for ofs in range(width):
            try:
                b=self[baseaddr+ofs]
            except KeyError:
                b=0
            result |= b<<(ofs*8)
        if baseaddr in self.lbreak:
            print("Memory breakpoint")
            print(f"mem[0x{baseaddr:08x}]->0x{result:0{width * 2}x}")
            raise StopIteration()
        return result
    def store(self,width,baseaddr,value):
        """
        Stores a little-endian value of arbitrary width from the memory
        :param baseaddr:
        :param width:
        :return:
        """
        print(f"mem[0x{baseaddr:08x}]<-0x{value:0{width * 2}x}")
        for ofs in range(width):
            self[baseaddr+ofs]= read_bitfield(value, ofs * 8 + 7, ofs * 8)
        if baseaddr in self.sbreak:
            print("Memory breakpoint")
            raise StopIteration()
    def stuff(self, data:dict[int,int]):
        for addr,b in data.items():
            self[addr]=b
    def dump(self,addr0,addr1):
        for i in range(0,addr1-addr0,16):
            print(f"{addr0+i:08x}  ",end='')
            for j in range(16):
                if addr0+i+j in self:
                    val=f"{self[addr0+i+j]:02x}"
                else:
                    val="xx"
                if addr0+i+j<addr1:
                    print(val,end='')
                else:
                    print('  ',end='')
                if j%4==3:
                    print(" ",end='')
            print(" ",end='')
            for j in range(16):
                if addr0+i+j<addr1:
                    if addr0 + i + j not in self:
                        val = '_'
                    elif 32<=self[addr0+i+j]<=127:
                        val=chr(self[addr0+i+j])
                    else:
                        val='.'
                    print(val, end='')
                else:
                    print(' ',end='')
            print()
