    .section .text.start
    .global _start
_start:
    li   sp, 0x10000          # top of 64 KB RAM
    call main
    li   t0, 0x20000004       # console exit register
    sw   a0, 0(t0)
1:  j    1b
