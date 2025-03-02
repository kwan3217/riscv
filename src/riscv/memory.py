"""
Module defining a byte-addressed memory

Created: 6/18/24
"""
import io
from subprocess import run

import numpy as np

from elf import read_syms
from riscv.bits import read_bitfield


def main():
    pass
    
    
if __name__=="__main__":
    main()


class Misaligned(Exception):
    pass


class Memory(dict):
    def __init__(self,verbose:bool=False,*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.lbreak=set()
        self.sbreak = set()
        self.verbose=verbose
    def __missing__(self,k):
        return 0
    def load(self,width,baseaddr,verbose=None,allow_misaligned=True):
        """
        Loads a little-endian value of arbitrary width from the memory
        :param baseaddr:
        :param width:
        :return:
        """
        result=0
        if not allow_misaligned:
            misalignment=baseaddr%width
            if misalignment!=0:
                raise Misaligned()
        for ofs in range(width):
            try:
                b=self[baseaddr+ofs]
            except KeyError:
                b=0
            result |= b<<(ofs*8)
        if verbose if verbose is not None else self.verbose:
            print(f"mem[0x{baseaddr:08x}]->0x{result:0{width * 2}x}")
        if baseaddr in self.lbreak:
            print("Memory breakpoint")
        return result
    def store(self,width,baseaddr,value,verbose=None,allow_misaligned=True):
        """
        Stores a little-endian value of arbitrary width from the memory
        :param baseaddr:
        :param width:
        :return:
        """
        if baseaddr in self.sbreak:
            print("Memory breakpoint")
        if not allow_misaligned:
            misalignment=baseaddr%width
            if misalignment!=0:
                raise Misaligned()
        if verbose if verbose is not None else self.verbose:
            print(f"mem[0x{baseaddr:08x}]<-0x{value:0{width * 2}x}")
        for ofs in range(width):
            self[baseaddr+ofs]= read_bitfield(value, ofs * 8 + 7, ofs * 8)
    def stuff(self, data:dict[int,int]):
        for addr,b in data.items():
            self[addr]=b
    def fill(self,addr0:int,addr1:int,val:int):
        for addr in range(addr0,addr1):
            self[addr]=val
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


class Bus(Memory):
    def __init__(self,regions:dict[tuple[int,int],Memory],*args,**kwargs):
        super().__init__(*args,**kwargs)
        self.regions=regions
    def get_region(self,addr:int)->tuple[int,Memory]:
        """
        Return the region which covers a given address
        :param addr: Physical address
        :return: Tuple of:
          * Lower end of address region. This will usually be subtracted off the physical address
            so each region will think it is zero-based. This especially helps for if we have multiple
            instances of the same class mapped to different ranges, say two UARTs. The UARTs don't
            have to know or care what address they are installed at.
          * Instance of a Memory class that handles the region
        """
        for (low,high),region in self.regions.items():
            if addr>=low and addr<high:
                return low,region
        raise ValueError(f"No memory found for address 0x{addr:x}")
    def __getitem__(self,addr:int):
        regionstart,region=self.get_region(addr)
        return region[addr-regionstart]
    def __setitem__(self,addr:int,val:int):
        regionstart,region=self.get_region(addr)
        region[addr-regionstart]=val


class NumpyMemory(Memory):
    def __init__(self,size:int=128*1024*1024,dtype:np.dtype=np.uint8,fillvalue:np.uint8=1):
        """
        Create a memory backed by a numpy array. The advantage of a numpy array is that the
        overhead is constant -- numpy array has a header, but each cell is exactly the size it needs to be.
        This is an improvement over a dict-backed memory, where each cell has an int address,
        an int value, and ints are at least 28 bytes.
        :param size: Number of addressable cells in the memory
        :param dtype: Type of each cell. Byte-addressable memories will use uint8, but for instance
                      the Kwan Simple 32bit processor has 32-bit registers and addresses 32-bit words
                      in memory, so it would get dtype=np.uint32.
        :param fillvalue: Value to fill memory with
        """
        self.array=np.full(size,fillvalue,dtype=dtype)
    def __getitem__(self,addr:int)->int:
        return int(self.array[addr])
    def __setitem__(self,addr:int,val:int):
        self.array[addr]=val
