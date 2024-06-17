"""
Bit and integer sign manipulation routines

# Signed numbers
Python's native int format is a signed number of effectively unlimited bits. This
is in contrast to hardware ints, which are always a fixed number of bits. The bits
have an implied encoding, either unsigned or twos-complement signed, depending
on context. Unsigned values are the natural choice for bitfields and for values
which are known to be positive. If negative values are in range, twos-complement
encoding enables the same addition hardware to be used without caring whether the
inputs are signed or unsigned.

We therefore have two related but independent concepts:
* Sign extension: To encode a twos-complement number of a given shorter bit length
  as a number with a longer bit-length, use the MSb of the shorter number to fill
  in the longer number. For instance, -2 is encoded in 4 bits as 0b1110, since
  0b1110+0b0010=0b1_0000 and since the carry-out bit is dropped, we end up with
  0b0000 as expected for -2+2=0. To sign-extend this value to a higher bit length,
  we put the old number in the lower bits of a new value, then duplicate the highest
  bit of the old number in all the higher bits. So for example, to sign-extend a
  4-bit value encoding -2 to 8 bits, we initially have the number 0bxxxx_1110, where
  the lower bits are from the original value, and the new bits are undetermined as
  yet. The highest bit of -2=0b1110 is 0b1, so the new bits are *all* 0b1 and we end
  up with 0b1111_1110. If the original was encoding a positive number such as
  +2=0b0010, its highest bit would be 0 and the 8-bit equivalent would be
  0b0000_0010.
* Sign interpretation:
  In Python, there is no such thing as a highest bit. Any twos-complement encoding
  *can* be represented as a positive integer, including the encoding of negative
  numbers. In order for an encoded value to be "imported" to Python so that its
  normal arithmetic operations can be used, the twos-complement values must be
  interpreted. In order to do this, we need to know where the sign bit is. For
  hardware ints, this is always the MSb, but for Python we need to know which
  bit is intended to be the MSb. To do sign interpretation, we then do a
  twos-complement *decoding* and if the sign bit in the bitfield was lit, we
  return a native Python number which is negative and matches the encoded
  negative number.

Created: 6/17/24
"""
from typing import Iterable


def main():
    pass


if __name__ == "__main__":
    main()


def bitmask(bit1,bit0):
    """
    Make a bitmask.
    :param bit1: Highest bit to be set to 1. Note that this is
                 inclusive, unlike most other places like this
                 in Python.
    :param bit0: Lowest bit to be set to 1
    :return: Integer with all bits between bit0 and bit1 set to 1

    example:
       print("%b"%bitmask(6,0))
         1111111
       print("%b"%bitmask(11,7))
         0000111110000000

    """
    maskwidth=(bit1-bit0+1)
    return ((1<<maskwidth)-1)<<bit0


def read_bitfield(x, bit1, bit0):
    """
    Parse a bitfield out of a larger number
    :param bit1: Highest bit to be set to 1. Note that this is
                 inclusive, unlike most other places like this
                 in Python.
    :param bit0: Lowest bit to be set to 1
    :return: bits in the bit field, shifted right so that the
            least significant bit of the field falls on 0
    """
    return (x & bitmask(bit1,bit0))>>bit0


def sign_extend(val, sign_bit, new_width):
    """
    Sign extend a number of a given bit-length
    :param val: twos-complement value to extend. This will be a
                *positive* number in Python even when a negative
                value is encoded.
    :param sign_bit: bit position of sign bit
    :param new_width: width of new number in bits
    :return: *positive* number with the sign bit repeated as many
             times as necessary to fill out the rest of the number
    """
    if read_bitfield(val, sign_bit, sign_bit) == 1:
        result=val
        for bit_pos in range(sign_bit+1,new_width):
            result|=1<<bit_pos
        return result
    else:
        return val


def signed(val,bit):
    """
    Interpret a twos-complement number of given length as a Python signed integer
    :param val: *positive* Python integer carrying the twos-complement
                encoding of a value
    :param bit: position of the sign bit, so for instance will be 11 to
                interpret a 12-bit signed number
    :return: Python integer of correct sign, IE the twos-complement encoding
             of a negative number (which is positive) will be interpreted as
             a negative number.
    """
    if read_bitfield(val,bit,bit)==1:
        min_negative=1<<bit
        negative_value=min_negative-read_bitfield(val,bit-1,0)
        return -negative_value
    return val


def read_bitfields(ins:int,fields:Iterable[tuple[int,int,int]],XLEN:int=None,is_signed:bool=False):
    """
    Read a value from multiple separate fields of a number

    :param ins: Instruction or other bitfield value
    :param fields: List of tuples, one for each field to extract. The tuple consists of (b1,b0,shift):
      * b1 is the MSb in the original bitfield
      * b0 is the LSb in the original bitfield
      * shift is the LSb in the final value, IE b0 of where this field will land.
    :param XLEN: If passed, sign-extend the number to this many bits.
    :param is_signed: If True, interpret the number as signed
    :return:

    """
    result=0
    signbit=0
    for b1,b0,shift in fields:
        result|=read_bitfield(ins,b1,b0)<<shift
        this_signbit=shift+(b1-b0)
        if this_signbit>signbit:
            signbit=this_signbit
    if XLEN is not None:
        result=sign_extend(result,signbit,XLEN)
        signbit=XLEN-1
    if is_signed:
        result=signed(result,signbit)
    return result
