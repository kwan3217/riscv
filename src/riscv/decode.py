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
from dataclasses import dataclass
from typing import Mapping, Callable, Any, Iterable
from warnings import warn

from riscv.bits import read_bitfields

compiled_encoding=namedtuple('compiled_encoding','mask fields sign_ext signed')
compiled_handler=namedtuple('compiled_handler','handler fields sign_ext signed')

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
@dataclass(frozen=True)
class compiled_encoding_bitmask:
    c:int
    s:int
    def __str__(self):
        result=['.']*32
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


def get_encoding_sign(human_encoding: str):
    if human_encoding[0] == 'x':
        sign_ext = True
        signed = False
        human_encoding = human_encoding[1:]
    elif human_encoding[0] == '+':
        sign_ext = False
        signed = False
        human_encoding = human_encoding[1:]
    elif human_encoding[0] == '-':
        sign_ext = True
        signed = True
        human_encoding = human_encoding[1:]
    else:
        # Default case is to sign-extend immediates and treat them as signed
        sign_ext = True
        signed = True
    return human_encoding, sign_ext, signed


def compile_encoding(human_encoding:str)->tuple[compiled_encoding_bitmask,bitfields_desc,bool,bool]:
    human_encoding,sign_ext,signed=get_encoding_sign(human_encoding)
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
                                         #1         2         3
    imm_subfields=[]                     #0123456789012345678901
    for imm_bit,c in enumerate('0123456789ABCDEFGHIJKLMNOPQRSTUV'):
        if c in encoding:
            ins_bit=encoding.index(c)
            imm_subfields.append((ins_bit,ins_bit,imm_bit))
    if len(imm_subfields)>0:
        fields['imm']=tuple(imm_subfields)
    return compiled_encoding(mask=compiled_encoding_bitmask(clearb,setb),fields=fields,signed=signed,sign_ext=sign_ext)


def compile_encodings(human_encodings):
    result={}
    for human_encoding, handler in human_encodings.items():
        clearset, fields, sign_ext, signed = compile_encoding(human_encoding)
        if clearset in result:
            if result[clearset][1] is not None:
                # Otherwise we are just replacing a reserved
                warn(f"Duplicate clearset {clearset}-- old={result[clearset]}, new={(fields, handler)}")
        result[clearset] = compiled_handler(fields=fields, sign_ext=sign_ext,signed=signed, handler=handler)
    return result


def reverse_encoding(human_encoding:str)->str:
    return "".join(human_encoding.split(" "))[::-1]


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


def decode(ins:int,compiled_descs:compiled_encodings,XLEN:int)->tuple[Mapping[str,int],'InstructionHandler']:
    """

    :param ins:
    :param compiled_descs:
    :return:
    """
    mask=decide(ins,compiled_descs)
    if mask is None:
        from riscv.hart import WrongInterpreter
        raise WrongInterpreter(f"Mask for instruction 0x{ins:08x} not found")
    desc=compiled_descs[mask]
    fields={}
    for name,subfields in desc.fields.items():
        if name=="imm":
            fields[name]=read_bitfields(ins,subfields,XLEN=XLEN if desc.sign_ext else None,is_signed=desc.signed)
        elif "'" in name:
            fields[name[:-1]]=read_bitfields(ins,subfields,is_signed=False)+8
        else:
            fields[name]=read_bitfields(ins,subfields,is_signed=False)
    return fields,desc.handler


def main():
    from test_decode import test_decode
                #     B498A673215
    test_decode(0b001_01010101010_01,'C.JAL')
                  # BA9876543210
    manual_decode=0b000101011010


if __name__ == "__main__":
    main()
