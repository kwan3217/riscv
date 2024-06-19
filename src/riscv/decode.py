"""
General purpose decoder

Bit patten description

Each instruction is described by a bit pattern, indicating bits
that are required to be set or cleared, or bits that are part of
a bitfield. Bits are identified as follows:

* | and _ for bits that are required to be set or cleared
* . for don't care (there shouldn't be very many of these in most cases)
* d, l, z for bits that are part of the rd, rs1, or rs2 fields
* e, m, y for bits thate are part of rd', rs1', or rs2' fields
* other lower-case letters for other fields that aren't scrambled
* [0-9A-Z] for bits 0-35 of an immediate field. We use this term
  for any number encoded directly in the instruction.
* spaces for delimiters, in any way that is convenient for the human involved

Some instructions require particular bits in a field, while others
don't. The C instruction is full of these -- if the rd field is 0,
meaning that the instruction would store to x0 IE throw away the
observable result of an instruction, the instruction instead means
something else. So, we might have two instructions like this:

..._____...  C.J
...ddddd...  C.MV

In this case, the decoder must make sure that C.J gets priority. I
think that manual ordering will do it, but I also think there is
some way to automatically do it, like maybe give priority to
the instructions where more bits are required to be set or cleared.
"""
from collections import namedtuple
from typing import Mapping, Callable, Any, Iterable
from warnings import warn

from riscv.bits import read_bitfields

Handler=namedtuple('Handler','name sign',defaults=(None,'-'))

field_abbrev = {
    'rd': 'd',
    'rs1': 'l',
    'rs2': 'z',
    "rd'": "e",
    "rs1/rd": "f",
    "rs1'/rd'": "g",
    "rs1'": "m",
    "rs2'": "y"
}

# 0 is b1, highest bit index in the subfield. bit indexes count from 0 on the left
# 1 is b0, lowest bit index in the subfield.
# 2 is target_b0, the bit in the target where b0 goes
subfield_desc=tuple[int,int,int]

# key is a string field name, such as imm, rs1,rd, etc.
# value is a list of subfields which are to be combined to make this field
bitfields_desc=Mapping[str,Iterable[subfield_desc]]

# Compiled description of one instruction.
# 0 is clear mask -- bits which are set in this mask must be cleared in the instruction for it to match
# 1 is set mask   -- bits which are set in this mask must be set in the instruction for it to match
class compiled_encoding_bitmask:
    def __init__(self,c,s):
        self.c=c
        self.s=s
    def __str__(self):
        result=['.']*16
        for mask,c in zip([self.c,self.s],['0','1']):
            for i in range(16):
                if (mask & (1<<i))>0:
                    result[i]=c
        return "".join(result[::-1])
    def __repr__(self):
        return self.__str__()
    def match(self,ins:int):
        return (ins & self.s)==self.s and (~ins & self.c)==self.c
    def bit_count(self):
        return self.s.bit_count() + self.c.bit_count()


compiled_encodings=Mapping[compiled_encoding_bitmask,tuple[bitfields_desc,'InstructionHandler']]


def get_mask(encoding:str,bit:str)->int:
    mask=0
    for i,encoded_bit in enumerate(encoding):
        if encoded_bit in bit:
            mask|=1<<i
    return mask


def compile_encoding(human_encoding:str)->tuple[compiled_encoding_bitmask,bitfields_desc]:
    encoding=reverse_encoding(human_encoding)
    clearb=get_mask(encoding,'_')
    setb=get_mask(encoding,'|')
    fields={}
    for full_field,abbrev in field_abbrev.items():
        if abbrev in encoding:
            b0=None
            b1=None
            for i,b in enumerate(encoding):
                if b==abbrev:
                    if b0 is None:
                        b0=i
                else:
                    if b0 is not None:
                        b1=i-1
                        break
            for field in full_field.split("/"):
                fields[field]=((b1,b0,0),)
    imm_subfields=[]                     #0123456788
    for imm_bit,c in enumerate('0123456789ABCDEFGHIJ'):
        if c in encoding:
            ins_bit=encoding.index(c)
            imm_subfields.append((ins_bit,ins_bit,imm_bit))
    if len(imm_subfields)>0:
        fields['imm']=tuple(imm_subfields)
    return compiled_encoding_bitmask(clearb,setb),fields


def reverse_encoding(human_encoding:str)->str:
    return "".join(human_encoding.split(" "))[::-1]


# Instructions in the RV32CI instruction set, those
# instructions that encode in the RV32I instruction
# set. This excludes:
#  * Floating point stuff
#  * Instructions which are not valid in RV32
# Reserved and Non-Standard extensions are defined as None,
# since they are usually more specific. The outer code
# will interpret finding a None as WrongExtension and
# look in the next one.
C32I_encodings={
    # Quadrant 0
    "___ ________ ___ __":"C.UNIM",  # Architecture-defined permanent illegal instruction
    "___ 549 876 23 eee __":Handler(name="C.ADDI4SPN",sign='+'), # Immediate is specified as zero-extended
    "__| 543 mmm 76 eee __":None, # C.FLD in C32/64F
    "__| 548 mmm 76 eee __":None, # C.LQ in C128I
    "_|_ 543 mmm 26 eee __":Handler(name="C.LW",sign='+'), # Immediate is specified as zero-extended
    "_|| 543 mmm 26 eee __":None,  # C.FLW in C32F
    "_|| 543 mmm 76 eee __":None,  # C.LD
    "|__ ... ... .. ... __":None,  # Reserved
    "|_| 543 mmm 76 yyy __":None,  # C.FSD in C32/64F
    "|_| 548 mmm 76 yyy __":None,  # C.SQ in C128I
    "||_ 543 mmm 26 yyy __":Handler(name="C.SW",sign='+'), # Likewise
    "||| 543 mmm 26 yyy __":None,  # C.FSW
    "||| 543 mmm 76 yyy __":None,  # C.SD
    # Quadrant 1
    "___ _ _____ _____ _|":"C.NOP",
    "___ 5 _____ 43210 _|":Handler(name="C.HINT1",sign='+'), #Treat it as unsigned zero-ext because it will be used as a bitfield
    "___ 5 fffff 43210 _|":Handler(name="C.ADDI"),  #Immediate must be nonzero and is sign-extended. Zero immediate is a hint.
    "___ _ 43210 _____ _|":Handler(name="C.HINT2",sign='+'),
    "__| B498A673215 _|":Handler(name="C.JAL"),     # Signed offset
    #"__| 5 fffff 43210 _|":None, # C.ADDIW in C64/128I
    "_|_ 5 ddddd 43210 _|":"C.LI",
    "_|_ 5 _____ 43210 _|":Handler("C.HINT3",sign='+'),
    "_|| 9 ___|_ 46875 _|":Handler("C.ADDI16SP"), #Nonzero sign-extended. Zero immediate is reserved.
    "_|| _ ___|_ _____ _|":None, # Reserved for future standard extensions, equivalent to C.ADDI16SP 0
    "_|| H ddddd GFEDC _|":Handler("C.LUI"),
    "_|| _ ddddd _____ _|":None, # Reserved
    "_|| 5 _____ 43210 _|":Handler(name="C.HINT4",sign='+'),
    "|__ _ __ ggg 43210 _|":"C.SRLI", # Bit 12 is nzimm5, which must be 0 for RV32C
    "|__ 5 __ ggg 43210 _|":None, #SRLI in C64/128I
    "|__ _ __ 210 _____ _|":Handler(name="C.HINT5",sign='+'), #C.SRLI64 in RV128C
    "|__ _ _| ggg 43210 _|":"C.SRAI", # Bit 12 is nzimm5, which must be 0 for RV32C
    "|__ 5 _| ggg 43210 _|":None,     # SRAI in C64/128I
    "|__ _ _| 210 _____ _|":Handler(name="C.HINT6",sign='+'),  # C.SRAI64 in RV128C
    "|__ 5 |_ ggg 43210 _|":Handler("C.ANDI"),
    "|__ _ || ggg __ yyy _|":Handler("C.SUB"),
    "|__ _ || ggg _| yyy _|":Handler("C.XOR"),
    "|__ _ || ggg |_ yyy _|":Handler("C.OR"),
    "|__ _ || ggg || yyy _|":Handler("C.AND"),
    "|__ | || ggg __ yyy _|":None, # C.SUBW
    "|__ | || ggg _| yyy _|":None, # C.ADDW
    "|__ | || ... |_ ... _|":None, # Reserved
    "|__ | || ... || ... _|":None, # Reserved
    "|_| B498A673215 _|":"C.J",
    "||_ 843 mmm 76215 _|":Handler(name="C.BEQZ"),
    "||| 843 mmm 76215 _|":Handler(name="C.BNEZ")
}

C_encodings={}
C_encodings.update(C32I_encodings)

C_compiled_encodings={}
for human_encoding,handler in C_encodings.items():
    clearset,fields=compile_encoding(human_encoding)
    if clearset in C_compiled_encodings:
        if C_compiled_encodings[clearset][1] is not None:
            # Otherwise we are just replacing a reserved
            warn(f"Duplicate clearset {clearset}-- old={C_compiled_encodings[clearset]}, new={(fields,handler)}")
    C_compiled_encodings[clearset]=(fields,handler)


def decide(ins:int,compiled_descs:compiled_encodings)->compiled_encoding_bitmask:
    """
    Decide which of the compiled instruction descriptions match the
    given instruction
    :param ins: instruction to check
    :param compiled_descs:
    :return: The bitmask that matched the ins, or None if none of them did.
    """
    best_mask=None
    best_bit_count=0
    for this_mask in compiled_descs:
        if this_mask.match(ins):
            this_bit_count=this_mask.bit_count()
            if this_bit_count>best_bit_count:
                best_mask=this_mask
                best_bit_count=this_bit_count
    return best_mask


def decode(ins:int,compiled_descs:compiled_encodings,XLEN:int=32)->tuple[Mapping[str,int],'InstructionHandler']:
    """

    :param ins:
    :param compiled_descs:
    :return:
    """
    mask=decide(ins,compiled_descs)
    desc=compiled_descs[mask]
    fields={}
    sign='-'
    if isinstance(desc[1],Handler):
        sign=desc[1].sign
    if sign=='-':
        # Don't bother with sign-extending to XLEN, just flip it to Python negative.
        sign_ext=False
        signed=True
    elif sign=='+':
        # It's unsigned and zero-extended
        sign_ext=False
        signed=False
    elif sign=='x':
        # It's sign-extended but then treated as positive
        sign_ext=True
        signed=False
        # The other case, signed and sign-extended, is redundant since
        # Python doesn't use twos complement for integers (or maybe uses
        # a form of unlimited-length twos-complement).
    else:
        raise ValueError(sign)
    for name,subfields in desc[0].items():
        if name=="imm":
            fields[name]=read_bitfields(ins,subfields,XLEN=XLEN if sign_ext else None,is_signed=signed)
        elif "'" in name:
            fields[name[:-1]]=read_bitfields(ins,subfields,is_signed=False)+8
        else:
            fields[name]=read_bitfields(ins,subfields,is_signed=False)
    return fields,desc[1]


def main():
    from test_decode import test_decode
                #     B498A673215
    test_decode(0b001_01010101010_01,'C.JAL')
                  # BA9876543210
    manual_decode=0b000101011010


if __name__ == "__main__":
    main()
