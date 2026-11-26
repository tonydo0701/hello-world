MEMORY { RAM (rwx) : ORIGIN = 0x0, LENGTH = 60K }
SECTIONS {
  .text : { *(.text.start) *(.text*) *(.rodata*) *(.srodata*) } > RAM
  .data : { *(.data*) *(.sdata*) } > RAM
  .bss  : { *(.bss*) *(.sbss*) *(COMMON) } > RAM
}
