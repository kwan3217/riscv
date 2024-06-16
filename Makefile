all: example.hex
ARCH=rv32ic
ABI=ilp32
OPT=-Og
PREFIX=riscv32-unknown-elf

example.hex: example
	$(PREFIX)-objcopy -O ihex $< $@

example: example.o
	$(PREFIX)-gcc $(OPT) --static -march=$(ARCH) -mabi=$(ABI) -o $@ $< -T rv32i.ld
	$(PREFIX)-objdump -xS $@ > $@.lss
	$(PREFIX)-strip $@
	$(PREFIX)-objdump -xS $@ > $@.strip.lss


%.o: %.c
	$(PREFIX)-gcc $(OPT) -g -c -march=$(ARCH) -mabi=$(ABI) -o $@ $<
	$(PREFIX)-objdump -xS $@ > $@.map


clean:
	$(RM) example.o
	$(RM) example
	$(RM) example.lss
	$(RM) example.o.map

