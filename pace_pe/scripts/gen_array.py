"""Constrained-random 8x8 kernel generator in pace-sim's folder format.

All PEs run the same loop shape (CM[0] = JUMP into a loop over CM[1..L-1]) so
PCs stay in lock-step and routing constraints can be checked per CM index:
  * a PE only reads a mesh input / writes an input register if its neighbour
    drives that link in the same CM entry (pace-sim errors on undriven wires)
  * pass-through (multi-hop) paths only flow east/south, so the combinational
    network is acyclic; W/N outputs only carry ALU_out / ALU_res
  * no outputs leave the array; NOP/JUMP never route ALU_out
  * every AGU program has a single access type/width (see README, finding 6);
    the two ports of a DM use disjoint halves so stores never collide
"""
import os, random, sys

MAX_CYC = 200          # longest run the regression uses
OPS = [1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 16, 17, 18, 19, 21, 0]
E, S, W, N, AO, AR, OP = 0, 1, 2, 3, 4, 5, 7
DIRBIT = {E: 0, W: 1, S: 2, N: 3}


def word_bytes_str(w):
    return ''.join(f'{b:08b}' for b in w.to_bytes(8, 'little'))


def gen(seed, outdir, L=None):
    rng = random.Random(seed)
    L = L or rng.randint(3, 16)
    os.makedirs(outdir, exist_ok=True)
    prog = [[[0] * L for _ in range(8)] for _ in range(8)]
    # drive[y][x][k] = set of output directions driven
    drive = [[[set() for _ in range(L)] for _ in range(8)] for _ in range(8)]
    ops = [[[0] * L for _ in range(8)] for _ in range(8)]
    for y in range(8):
        for x in range(8):
            prog[y][x][0] = 30 << 30 | 1 << 45 | (L - 1) << 40 | 1 << 35 | 0o7777777  # JUMP, all open
            for k in range(1, L):
                ops[y][x][k] = rng.choice(OPS)
    bypass = [[[rng.getrandbits(4) if rng.random() < .3 else 0 for _ in range(L)] for _ in range(8)] for _ in range(8)]
    outs = [[[dict() for _ in range(L)] for _ in range(8)] for _ in range(8)]
    # pass 1: outputs, in raster order (pass-through depends on W / N neighbours)
    for k in range(1, L):
        for y in range(8):
            for x in range(8):
                op = ops[y][x][k]
                alu_srcs = [AR] + ([AO] if op not in (0, 30) else [])
                byp = bypass[y][x][k]
                for d, ok in ((E, x < 7), (S, y < 7), (W, x > 0), (N, y > 0)):
                    src = OP
                    if ok and rng.random() < 0.55:
                        cands = list(alu_srcs)
                        if d in (E, S):
                            if x > 0 and E in drive[y][x - 1][k]:
                                if d == E or not (byp >> DIRBIT[W]) & 1:
                                    cands += [W, W]
                            if y > 0 and S in drive[y - 1][x][k]:
                                if d == E or not (byp >> DIRBIT[N]) & 1:
                                    cands += [N, N]
                        src = rng.choice(cands)
                    outs[y][x][k][d] = src
                    if src != OP:
                        drive[y][x][k].add(d)
    # pass 2: operands, input registers
    for y in range(8):
        for x in range(8):
            for k in range(1, L):
                op = ops[y][x][k]
                inc = []                                   # driven incoming directions
                if x > 0 and E in drive[y][x - 1][k]: inc.append(W)
                if x < 7 and W in drive[y][x + 1][k]: inc.append(E)
                if y > 0 and S in drive[y - 1][x][k]: inc.append(N)
                if y < 7 and N in drive[y + 1][x][k]: inc.append(S)
                byp = bypass[y][x][k]
                readable = inc + [d for d in (E, S, W, N) if (byp >> DIRBIT[d]) & 1 and d not in inc]
                srcs = [OP, AR] + ([AO] if op not in (0, 30) else []) + readable * 2
                o1, o2 = rng.choice(srcs), rng.choice(srcs)
                we = sum(1 << DIRBIT[d] for d in inc if rng.random() < 0.4)
                imm = None
                if op == 5 or rng.random() < 0.3:
                    imm = rng.randint(1, 0xFFFF) if op == 5 else rng.getrandbits(16)
                w = op << 30
                if imm is not None:
                    w |= 1 << 62 | imm << 35
                if op != 0 and rng.random() < 0.7:
                    w |= 1 << 25
                if x in (0, 7) and rng.random() < 0.35:
                    w |= 1 << 59
                oo = outs[y][x][k]
                sw = OP << 18 | o2 << 15 | o1 << 12 | oo[N] << 9 | oo[W] << 6 | oo[S] << 3 | oo[E]
                prog[y][x][k] = w | sw | byp << 21 | we << 26
    for y in range(8):
        for x in range(8):
            with open(os.path.join(outdir, f'PE-Y{y}X{x}'), 'w') as f:
                f.write('\n'.join(word_bytes_str(v) for v in prog[y][x]) + '\n')
    for a in range(16):
        n = rng.randint(1, 4)
        typ = rng.choice(['LOAD', 'LOAD', 'STORE'])
        wid = rng.choice(['B8', 'B16', 'B64'])
        lines, arf = [], []
        lo = 0 if (a % 8) % 2 == 0 else 4096                # DM port A / port B halves
        for i in range(n):
            mode = rng.choice(['STRIDED', 'STRIDED', 'CONST'])
            # hard bound: even if the PE triggers every cycle for MAX_CYC cycles,
            # this entry's address stays inside its 4 KB half of the DM
            size = {'B8': 1, 'B16': 2, 'B64': 8}[wid]
            hits = -(-MAX_CYC // n)
            st = rng.randint(0, min(3, (4096 - 1500 - 8) // (size * hits))) if mode == 'STRIDED' else 0
            lines.append(f'{typ}, {mode}, {wid}, {st}')
            arf.append(lo + rng.randint(0, 1500))   # worst case growth < 2.6 KB stays in this half
        with open(os.path.join(outdir, f'agu{a}'), 'w') as f:
            f.write('CM:\n' + '\n'.join(lines) + '\n\nARF:\n' + '\n'.join(map(str, arf)) + '\n\nMAX COUNT:\n100000')
    for d in range(8):
        with open(os.path.join(outdir, f'dm{d}'), 'w') as f:
            for _ in range(1024):
                f.write(word_bytes_str(rng.getrandbits(64)) + '\n')


if __name__ == '__main__':
    gen(int(sys.argv[1]), sys.argv[2])
