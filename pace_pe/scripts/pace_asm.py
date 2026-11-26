"""Tiny encoder for PACE PE configuration words (format of pace-sim)."""
OPC = dict(NOP=0, ADD=1, SUB=2, MULT=3, SEXT=4, DIV=5, VADD=6, VMUL=7, LS=8, RS=9,
           ASR=10, AND=11, OR=12, XOR=13, LOADD=14, STORED=15, SEL=16, CMERGE=17,
           CMP=18, CLT=19, BR=20, CGT=21, MOVCL=23, LOAD=24, LOADB=26, STORE=27,
           STOREB=29, JUMP=30, MOVC=31)
SRC = dict(E=0, S=1, W=2, N=3, ALUOUT=4, ALURES=5, OPEN=7)
DIRBIT = dict(E=0, W=1, S=2, N=3)          # bit position in the {N,S,W,E} masks


def mask(dirs):
    return sum(1 << DIRBIT[d] for d in dirs)


def word(op, imm=None, upd=False, east='OPEN', south='OPEN', west='OPEN', north='OPEN',
         op1='OPEN', op2='OPEN', pred='OPEN', bypass=(), we=(), agu=False,
         jdst=0, ls=0, le=15):
    w = OPC[op] << 30
    if op == 'JUMP':
        w |= (jdst & 0x1F) << 45 | (le & 0x1F) << 40 | (ls & 0x1F) << 35
    else:
        if imm is not None:
            w |= 1 << 62 | (imm & 0xFFFF) << 35
        w |= int(upd) << 25
    sw = (SRC[pred] << 18 | SRC[op2] << 15 | SRC[op1] << 12 | SRC[north] << 9 |
          SRC[west] << 6 | SRC[south] << 3 | SRC[east])
    w |= sw | mask(bypass) << 21 | mask(we) << 26 | int(agu) << 59
    return w
