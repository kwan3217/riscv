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
        return result
    def store(self,width,baseaddr,value):
        """
        Stores a little-endian value of arbitrary width from the memory
        :param baseaddr:
        :param width:
        :return:
        """
        for ofs in range(width):
            self[baseaddr+ofs]= read_bitfield(value, ofs * 8 + 7, ofs * 8)
    def stuff_hex(self, hexfn:str=None, hexf: io.TextIOBase =None):
        """
        Load an Intel Hex file into memory

        :param hexfn: Name of file to load
        :return:
        """
        hiaddr=0
        if hexf is None:
            hexf=open(hexfn,"rt")
            needs_close=True
        else:
            needs_close=False
        try:
            for line in hexf:
                line=line.strip()
                bytecount=int(line[1:3],16)
                loaddr=int(line[3:7],16)
                rtype=int(line[7:9],16)
                stored_cksum=int(line[bytecount*2+9:bytecount*2+9+2],16)
                if rtype==0:
                    data = bytes([int(line[i * 2 + 9:i * 2 + 9 + 2], 16) for i in range(bytecount)])
                    # Data, stuff into memory at given addr
                    for i,b in enumerate(data):
                        addr=loaddr+hiaddr*0x10000+i
                        self[addr]=b
                elif rtype==1:
                    # End of file record
                    break
                elif rtype==4:
                    # Extended linear address (upper 16 bits of 32-bit address)
                    hiaddr=int(line[9:13],16)
        finally:
            if needs_close:
                hexf.close()
    def stuff_elf(self,elffn:str)->dict[str,int]:
        """
        Load an ELF image into memory

        :param elffn:
        :return: dict of symbols. Key is string name of symbol, val is parsed address
        """
        result = run(
            f"riscv64-unknown-elf-objcopy -O ihex {elffn} /dev/stdout",
            capture_output=True, shell=True)
        if len(result.stderr)!=0:
            raise RuntimeError(result.stderr)
        with io.TextIOWrapper(io.BytesIO(result.stdout)) as hexf:
            self.stuff_hex(hexf=hexf)
        return read_syms(elffn)
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
                    elif self[addr0+i+j]>=32 and self[addr0+i+j]<=127:
                        val=chr(self[addr0+i+j])
                    else:
                        val='.'
                    print(val, end='')
                else:
                    print(' ',end='')
            print()
