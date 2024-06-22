# Imperas test suite

The Imperas test suite was the first hit I found
that promised a relatively complete coverage of
the RISC-V spec. Unfortunately, it promised more
than it delivered -- it only delivered RV32I. Not
even C.

The old code for running Imperas is in the history,
but not currently present in the working copy. That's
why we use git in the first place.

Below is the old stuff about Imperas from the readme.md:

# Compiling the Imperas suite

## Get the suite
```
git clone git@github.com:riscv-ovpsim/imperas-riscv-tests.git
```

## Build the tests
For the supported tests, there is a .S file with the assembly for the test,
and a reference output. Compile the tests as follows:

```
cd imperas-riscv-tests
make RISCV_TARGET=riscvOVPsim RISCV_PREFIX=riscv-none-embed- 
```

## Dump the tests
The Python code can't handle ELF directly, and needs
to have the binary dumped to a suitable format. 
[Intel HEX](https://en.wikipedia.org/wiki/Intel_HEX) is
simple enough but supports all the features we need,
namely the ability to stuff_hex code at a particular address
in the address space.

We also want to have the disassembly of the files -- the
input source code doesn't have addresses etc, and have tons
of macros with non-trivial expansions. So, do the following:

```
cd work/rv32i_m/I
for i in *.elf
do
  riscv-none-embed-objdump -xS $i > `basename $i .elf`.objdump
  riscv-none-embed-objcopy -O ihex $i `basename $i .elf`.hex
done
```
