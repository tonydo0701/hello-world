"""Constrained-random program + stimulus generator for one PE."""
import random, sys

OPS = [0, 1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 16, 17, 18, 19, 21, 30]
SRCS = [0, 1, 2, 3, 4, 5, 7]
SRC2BIT = {0: 0, 1: 2, 2: 1, 3: 3}     # E,S,W,N source code -> {N,S,W,E} bit


def gen_word(rng):
    op = 30 if rng.random() < 0.08 else rng.choice(OPS[:-1])
    w = op << 30
    if op == 30:
        w |= rng.randrange(16) << 45 | rng.randrange(16) << 40 | rng.randrange(16) << 35
    else:
        w |= rng.getrandbits(16) << 35 | (rng.getrandbits(1) if op else 0) << 25
    w |= rng.getrandbits(1) << 62          # imm-valid (ignored by JUMP)
    for b in (63, 61, 60, 59):              # reserved / sideband noise
        w |= rng.getrandbits(1) << b
    bypass = rng.getrandbits(4)
    we = rng.getrandbits(4)
    fields = []
    for i in range(6):                      # E,S,W,N out, op1, op2
        while True:
            s = rng.choice(SRCS)
            if op in (0, 30) and s == 4:    # NOP/JUMP drive no ALU output
                continue
            # pace-sim only honours bypass on east_out; keep S/W/N outs from
            # bypassed directions out of the random space (see README).
            if i in (1, 2, 3) and s in SRC2BIT and (bypass >> SRC2BIT[s]) & 1:
                continue
            break
        fields.append(s)
    sw = 7 << 18
    for i, s in enumerate(fields):
        sw |= s << (3 * i)
    return w | sw | bypass << 21 | we << 26


def gen_val(rng):
    r = rng.random()
    if r < 0.35:
        return rng.getrandbits(64)
    if r < 0.6:
        return rng.randrange(0, 24) | (rng.choice([0, 0, 0xFFFF]) << 0)
    if r < 0.7:
        return rng.choice([0, 0x8000, 0x7FFF, 0xFFFF, 1])
    v = 0
    for i in range(8):                      # plausible FP8 lanes
        v |= (rng.getrandbits(1) << 7 | rng.randrange(3, 12) << 3 | rng.getrandbits(3)) << (8 * i)
    return v


def main(seed, prog_f, inp_f, ncyc):
    rng = random.Random(seed)
    with open(prog_f, 'w') as f:
        for _ in range(16):
            f.write(f"{gen_word(rng):016x}\n")
    with open(inp_f, 'w') as f:
        for _ in range(ncyc):
            f.write(' '.join(f"{gen_val(rng):016x}" for _ in range(4)) + '\n')


if __name__ == '__main__':
    main(int(sys.argv[1]), sys.argv[2], sys.argv[3], int(sys.argv[4]))
