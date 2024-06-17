all: example.hex
ARCH=rv32ic
ABI=ilp32
OPT=-Og
PREFIX=riscv64-unknown-elf

example.hex: example.elf
	$(PREFIX)-objcopy -O ihex $< $@

example.elf: example.o
	$(PREFIX)-gcc $(OPT) --static -march=$(ARCH) -mabi=$(ABI) -o $@ $< -T rv32i.ld
	$(PREFIX)-objdump -xS $@ > $@.lss
	$(PREFIX)-strip $@
	$(PREFIX)-objdump -xS $@ > $@.strip.lss


%.o: %.c
	$(PREFIX)-gcc $(OPT) -g -c -march=$(ARCH) -mabi=$(ABI) -o $@ $<
	$(PREFIX)-objdump -xS $@ > $@.map


clean:
	$(RM) example.o
	$(RM) example.elf
	$(RM) example*.lss
	$(RM) example*.map
	$(RM) example*.hex

