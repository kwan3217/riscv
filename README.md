# riscv
This is an emulator for the RISC-V
instruction set architecture. This
architecture is known for being very
well-designed, being basically a clean sheet
with everything that has been learned about
computer architecture and organization in the
last 40 years.

The specification is a much better source for
their rationale than anything I can state
here. I am just doing this emulator for
learning purposes.

## Philosophy
I am interested in things like modularity,
cleanliness, elegance, etc. One of the things
I like most of all is table-driven code. An
old programming manual that I loved (probably
[Code Complete](https://www.amazon.com/Complete-Microsoft-Programming-Steve-McConnell/dp/1556154844/))
recommended to make your tables smart and
your code stupid, and that advice has stuck.

The priorities then are:

1. *Regularity* -- Make each opcode handler
   as much like other handlers as possible,
   and make the decoder table-driven.
2. *Readability* -- Usually this is #1, but
   I'm trying something new in this project.
3. *Specification driven* -- Make the program
   match the structure of the specification
   in the most obvious way possible. Do
   things "by the book" and make the program
   a Python translation of an English document.
4. *Modularity* -- The specification is
   modular, and the program should be also.
   Each part of the spec is implemented in
   a matching piece of code, usually a class
   in a Python module
5. *Performance* -- This is a distant last
   place, since this code will *only* ever
   be used for learning, *never* for any
   actual practical use.

## Program structure

The code is structured in a tree, as is usual
for Python programs:

```
src
  \--riscv -- code directly dealing with RISC-V
     \--bits.py -- bitfield stuff
     \--decode.py -- code for a table-driven decoder
     \--hart.py -- code for a (har)dware (t)hread, the basic unit of RISC-V computation.
     \--memory.py -- code for implementing an addressable memory
     \--rv32i.py -- instruction handlers and decode table for the 32-bit 
                      base integer instruction set
     \--rv32c.py -- instruction handlers and decode table for the compressed
                      instructions that correspond to RV32I instructions
     \--(rv64i.py) -- todo - 64-bit base integer instruction set
     \--(rv64c.py) -- todo - compressed instructions that correspond to RV64I
     \--(m32.py) -- todo - multiply and divide extension on 32-bit integer registers.
                    This actually works on any XLEN registers, be they 32, 64, 128, 
                    or 97 bits.
     \--(m64.py) -- todo - multiply and divide extension on 64-bit integer registers.
                    Most of this overlaps m32.py, so only include the difference here.
     \--(other standard extensions) -- todo, named by their official abbreviation, so
                    f.py for single-precision floating point, d.py for 
                    double-precision, etc.
     \--zicsr.py -- CSR, control and status registers. This includes tables naming
                    the standard CSRs, along with the instructions to acces them.
     \--priv.py -- Privileged architecture, mostly trap handling at this point
     \--spike.py -- code to control the Spike RISC-V emulator. This is used to generate
                    the reference test signatures.
   \--elf -- code for working with an ELF image, mostly by using objdump and objcopy
```