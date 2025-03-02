"""
Describe purpose of this script here

Created: 6/26/24
"""
from dataclasses import dataclass, replace

zero=None

@dataclass
class softfloat:
    """
    Software floating point operations. This is the in-memory form, with potentially unlimited
    precision (like the ints underlaying it).

    The following symbols are used throughout:

    * k -- Total number of bits in the format. Single-precision float has k==32, double has k==64, etc.
    * b -- Base of exponent, 2 for Binary and 10 for Decimal
    * p -- precision (length of significand) in bits, inclduing any implied digits
    * q -- exponent when thinking of the significand as an integer, q=e-p+1
    * e -- exponent when thinking of the significand as a real number in [1,2), e=q+p-1
    * E -- stored exponent, E=e+bias. Stored bias also has some special values:
           * (2**w)-1 (all 1s) -- either infinite (significand is all 1s) or NaN (significand isn't all 1s)
           * (2**w)-2 -- maps to emax, maximum exponent of a finite number
           * 1 -- maps to emin, minimum exponent of a finite normal number
           * 0 -- maps to zero (significand is all 0s) or subnormal number (significand is not all 0s).
    * emax - maximum expressable exponent
    * bias -- exponent bias between stored and actual e, bias=E-e
    * qbias -- exponent bias between stored and q exponent
                         E=e+bias
    * w -- number of bits to store exponent
    * t -- number of bits of significand to store, t=k-w-1. In practice, t=p-1, so p=t+1

    The following relations exist between integer-related exponent parameters q* and [1,2)
    related parameters e*:
    * q=e-(p-1)
       =e-p+1
    * e=q+p-1
    * E=e+bias
    *  =q+p-1+bias
    * e=E-bias
    * qbias=p-1+bias
    * E=q+qbias
    * There is no equivalent Q -- q is determined from E just as e is.
    * q=E-qbias
    * qmax=emax-p+1
    * emax=qmax+p-1

    The following relations also exist for E and w:
    * Infinite or NaN -- E=(2**w)-1
    * Emax=(2**w)-2
    * Emin=1
    * Subnormal or zero -- E=0
    * emax=Emax-bias
    *     =(2**w)-2-bias
    * emin=1-bias
    * qmax=Emax-qbias
    *     =(2**w)-2-qbias
    *     =(2**w)-2-(p-1+bias)
    *     =(2**w)-2-p+1-bias
    * qmin=1

    Scientific notation expresses any number as the product of three things:
     * a number between 1 and almost 10. This is called the mantissa or significand.
     * 10 raised to a given power
     * either -1 or +1 to make the number negative or positive.

    For instance, Avogadro's number is about +1*6.022*10**23, so the sign part is +1,
    the significand is 6.022, and the exponent e is 23.

    However, we could think of it differently. We decide to keep a given number of
    significant figures p, and then use a positive integer with p digits. If we kept 10
    digits, we would say that Avogadro's number is +1*6,022,000,000*10**14 . Here the
    integer exponent q is only 14, since it has to shift the decimal only 14 places
    because the fact we are using an integer already shifts it 9 places relative
    to what we have above.

    Humans use base 10, and therefore it is convenient to use 10 as the base for
    the exponent, because multiplying or dividing by 10 is shifting left or right.
    For any given significand which isn't a proper scientific notation number,
    we can convert it to be so by shifting the number so that the decimal is
    between the first and second digit to the right, and counting how many digits
    that is and adjusting the exponent by adding or subtracting that many digits.

    Thus we see that e will always be greater than q, by exactly the number of
    digits to the right of the decimal. This number is p-1, and it's only coincidence
    that t=p-1 is also the number of stored bits. Therefore we have e=q+(p-1)
    (not e=q+t).

    Similarly, computers use base 2, so it's convenient to use 2 for the exponent
    since multiplying or dividing by 2 is shifting bits left or right.

    Base 2 is used in electronics for one main reason: Since even digital is analog,
    it's always easier to distinguish symbols in a smaller alphabet versus a larger
    one. Base 2 just has two symbols, which happens to match the two power rails
    (vcc and gnd) so any symbol can be amplified until it saturates at one or the
    other rail. With any other alphabet, you have to be more careful to maintain
    signals in between the two rails.

    Now having said that, we can also take advantage of some coincidences:

    * Since there are only two symbols, and one of them is 0, this makes multiplying
      just as easy as shifting and adding. The times table has 4 cells, and 3 of them
      are 0. Elementary-school multiplication just becomes shift-and-sometimes-add --
      if we are multiplying by a 1 in this digit of the bottom factor, we just copy
      the shifted top factor down to the sum below. If we are multiplying by a 0, we
      just don't. Our algorithm then becomes:
      - Shift the top factor left by 1 so it lines up with digit `i` in the bottom
        factor
      - If the bottom factor digit `i` is 1, add the shifted top factor to the product
        accumulator. If it's a zero, then just don't add.
      - Repeat until you run out of bottom factor digits. The answer is then left in
        the product accumulator.
    * In scientific notation (in any base) the one and only digit to the left of the
      fraction point is never 0. In base 10, it can be anything from 1 to 9. In base
      2, it can be anything from 1 to... 1. Since there is no surprise in this
      digit, it carries no information (in the Shannon sense) and can always be
      losslessly compressed away, by the simple expedient of not recording it. This is
      the "implied digit" mentioned below. It means that our significand *always* has
      a 1 in the most significant digit. We will generally explicitly keep the implied
      digit in memory so that it acts like a perfectly normal integer where we can use
      the integer operations. The implicit digit will be dropped when the data is packed
      for its long long journey out of the floating-point system to main memory, and
      re-expressed when unpacked in a floating-point register. We will have to be
      careful though when we handle subnormal numbers. Due to this fact, the number
      of *stored* digits `t` is p-1

    Similarly in floating point, we use 2 raised to a power as our exponent part,
    so our significand is between 1 and almost 2. Or we treat the significand
    as an integer between 2**(p-1) and (2**p)-1. I have decided to go with the
    integer interpretation, in an attempt to keep the properties of integers
    (exactness and performance) for as long as is reasonable.

    The fundamental value with no special cases is:
    (-1**sign)*(2**q)*(significand).

    So, if the significand is 24 bits (like it will be on a 32-bit float) bit 23
    will always be set, so the significand is between 2**23 and 2**24-1. As Strong
    Bad would say, "That is not a small number. That is a *BIG* number!" Therefore,
    to get a number with an absolute value near 1, the exponent q will have to be
    about -23.

    The other way to think about it is that the significand is a fixed-point
    number with a 1 digit to the right of the radix point. In this form, the
    significand is always between 1 and almost 2, and to get a number with an
    absolute value near 1, the exponent e will be near 0.

    # Subnormal numbers
    One of the things I never thought of while learning programming is underflow.
    Overflow is obvious -- if the exponent of the result of an operation doesn't
    fit into the exponent field, this is overflow and is a problem. The true result
    is almost certainly still finite, but no longer representable. IEEE 754 has an
    encoding for infinity, so that's the obvious choice for an operation that
    overflows. Older formats like with Applesoft Basic don't support infinity and
    throw an error on overflow.

    On the other end, an operation can generate a result with an exponent less than
    emin. This is *underflow*, the exact mirror problem to overflow.

    """
    # Significand, with implicit digits explicitly included. Always unsigned,
    # will have a maximum of self.p bits precision, IE 0<=significand<2**(self.b)
    significand:int=0
    # Number of digits (bits) of significand, including any implicit digits
    # Note that this is needed for shift-back of multiplication, which produces
    # a result with as many digits as the total digits of both factors.
    p:int=24
    # exponent, based on looking at significand as an integer.
    q:int=0
    # Sign bit, with 0 indicating a positive number and 1 indicating a negative.
    sign:int=0
    isinf:bool=False
    isqnan:bool=False
    issnan:bool=False
    def __neg__(self):
        return replace(self,sign=1-self.sign)
    def __pos__(self):
        return replace(self)
    def __abs__(self):
        return replace(self,sign=0)
    def __mul__(self,other:'ieee754_float'):
        if self.is_zero():
            return zero
        if other.is_zero():
            return zero
        # result has twice as many digits as either factor
        result_significand=self.significand*other.significand
        # todo - Think about rounding at this point, while we can still
        #        see the extra digits.
        # Shift result back to throw away extra digits on left.
        result_significand>>=(self.p-1+1)
        result_q=self.q+other.q+(self.p)
        result_sign=0 if (self.sign==other.sign) else 1
        result=replace(self,q=result_q,significand=result_significand,sign=result_sign)
        return result
    def __add__(self,other:'ieee754_float'):
        if self.is_zero():
            return replace(other)
        if other.is_zero():
            return replace(self)
        if self.sign==0 and other.sign==0:
            # both positive case, just add
            if self.q>=other.q:
                # self is "bigger" than other
                # figure out how much to shift
                shift_amount=self.q-other.q
                # shift other mantissa that much
                other_significand=other.significand>>shift_amount
                # todo -- rounding?
                # do the addition
                result_significand=self.significand+other_significand
                return replace(self,significand=result_significand)
            else:
                # other is "bigger" than self
                shift_amount=other.q-self.q
                self_significand=self.significand>>shift_amount
                result_significand=self_significand+other.significand
                return replace(other,significand=result_significand)
        elif self.sign==0 and other.sign==1:
            if self.q>=other.q:
                shift_amount=self.q-other.q
                other_significand=other.significand>>shift_amount
                result_significand=self.significand-other_significand
                return replace(self,significand=result_significand)
            else:
                shift_amount=other.q-self.q
                self_significand=self.significand>>shift_amount
                result_significand=self_significand-other.significand
                return replace(other,significand=result_significand)
    def __sub__(self,other):
        return self+(-other)
    def is_zero(self):
        return self.significand==0
    def __float__(self):
        # We take the view that the significand is an integer, and
        # that therefore to get a number near 1, the number is a
        # large int raised to a small (much less than 1) exponent.
        sign_part=-1 if self.sign==1 else 1
        b_part=2**float(self.q)
        sig_part=self.significand
        result=sign_part*b_part*sig_part
        return result


zero=softfloat(sign=0,significand=0,q=-126)

# Repeated here for convenience:
#   * k -- Total number of bits in the format. Single-precision float has k==32, double has k==64, etc.
#   * p -- precision (length of significand) in bits, inclduing any implied digits
#   * q -- exponent when thinking of the significand as an integer, q=e-p+1
#   * e -- exponent when thinking of the significand as a real number in [1,2), e=q+p-1
#   * E -- stored exponent, E=e+bias
#   * bias -- exponent bias between stored and actual bias, bias=E-e
#   * w -- number of bits to store exponent
#   * t -- number of bits of significand to store, t=k-w-1. In practice, t=p-1

ktuple=(16,32,64,128)
pdict=    {k:v for k,v in zip(ktuple,(11, 24,  53,  113))}
emaxdict= {k:v for k,v in zip(ktuple,(15,127,1023,16383))}
# For all defined widths, emax==bias
wdict=    {k:v for k,v in zip(ktuple,( 5,  8,  11,   15))}
# For all defined widths, t=k-w-1
@dataclass
class packfloat(softfloat):
    def __init__(self,val:float=None,*,k:int=32,**kwargs):
        super().__init__(**kwargs)
        # Total amount of storage, bits
        self.k=k
        # Number of significant figures in significand, including any implied bits
        self.p=pdict[k]
        # Maximum exponent from the point of view of a significand in [1,2)
        self.emax=emaxdict[k]
        # Maximum exponent from the point of view of a significand in the range [2**(p-1),2**p-1]
        self.qmax=self.emax-self.p+1
        # Bias, equal to emax for all defined bit widths
        self.bias=self.emax
        self.qbias=self.bias-self.p+1
        # Number of bits of stored exponent. 2**w must be >= Emax
        self.w=wdict[k]
        # Number of bits used to store the significand, not counting any implied bits
        self.t=self.p-1
        # Check that we add up
        assert self.k==(self.t+self.w+1)
    def pack(self)->int:
        """
        Return the packed form of this number
        :return: int which encodes this number according to IEEE 754 binary encoding
        """
        result=((self.sign        <<(self.w+self.t)) | #sign bit in most significant bit
                (self.q-self.qbias<<(       self.t)) | #Biased exponent in next bits
                (self.significand <<             0 ) ) #
