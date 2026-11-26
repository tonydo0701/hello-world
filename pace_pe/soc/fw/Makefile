# make KERNEL=<pace-sim kernel dir> GOLD_DM=<golden dm prefix>
CC      = riscv64-unknown-elf-gcc
OBJCOPY = riscv64-unknown-elf-objcopy
CFLAGS  = -march=rv32im -mabi=ilp32 -O2 -ffreestanding -nostdlib -Wall
all: firmware.hex
kernel.h: $(KERNEL)
	python3 ../../scripts/cgra_image.py $(KERNEL) ../../build/fw_kernel.writes kernel.h $(GOLD_DM)
firmware.elf: start.S main.c pace_cgra.h kernel.h link.ld
	$(CC) $(CFLAGS) -T link.ld start.S main.c -o $@ -lgcc
firmware.hex: firmware.elf
	$(OBJCOPY) -O binary $< firmware.bin
	python3 -c "import sys;d=open('firmware.bin','rb').read();d+=bytes(-len(d)%4);open('$@','w').write('\n'.join(f'{int.from_bytes(d[i:i+4],\"little\"):08x}' for i in range(0,len(d),4))+'\n')"
clean:
	rm -f kernel.h firmware.elf firmware.bin firmware.hex
