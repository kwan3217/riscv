all: example
ARCH=rv32i
OPT=-Og

example.hex: example
	riscv-none-embed-objcopy -O ihex $< $@

example: example.o
	riscv-none-embed-gcc $(OPT) --static -march=$(ARCH) -o $@ $< -T rv32i.ld
	riscv-none-embed-objdump -xS $@ > $@.lss
	riscv-none-embed-strip $@
	riscv-none-embed-objdump -xS $@ > $@.strip.lss


%.o: %.c
	riscv-none-embed-gcc $(OPT) -g -c -march=$(ARCH) -o $@ $<
	riscv-none-embed-objdump -xS $@ > $@.map


clean:
	$(RM) example.o
	$(RM) example
	$(RM) example.lss
	$(RM) example.o.map

