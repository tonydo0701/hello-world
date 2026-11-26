"""Random co-simulation: RTL (Icarus) vs pace-sim PE model, trace-by-trace."""
import os, subprocess, sys, collections
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, 'build')
GOLD = os.path.join(ROOT, 'model/golden/target/release/pace-pe-golden')
SIM = sys.argv[3] if len(sys.argv) > 3 else 'iverilog'
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import gen_random

N = int(sys.argv[1]) if len(sys.argv) > 1 else 200
NCYC = int(sys.argv[2]) if len(sys.argv) > 2 else 300
os.makedirs(B, exist_ok=True)
if SIM == 'iverilog':
    run = ['vvp', '-n', os.path.join(B, 'tb_pe.vvp')]
else:
    run = [os.path.join(B, 'obj_tb_pe', 'Vtb_pe')]
fails = 0
opcount = collections.Counter()
NAMES = {0: 'NOP', 1: 'ADD', 2: 'SUB', 3: 'MULT', 5: 'DIV', 6: 'VADD', 7: 'VMUL', 8: 'LS', 9: 'RS',
         10: 'ASR', 11: 'AND', 12: 'OR', 13: 'XOR', 16: 'SEL', 17: 'CMERGE', 18: 'CMP',
         19: 'CLT', 21: 'CGT', 30: 'JUMP'}
cycles = 0
for seed in range(N):
    p, i, tg, tr = (os.path.join(B, f) for f in (f'{SIM}_prog.hex', f'{SIM}_inp.hex', f'{SIM}_gold.txt', f'{SIM}_rtl.txt'))
    gen_random.main(seed, p, i, NCYC)
    subprocess.run([GOLD, 'pe', p, i, tg], check=True)
    subprocess.run(run + [f'+PROG={p}', f'+INPUTS={i}', f'+TRACE={tr}'], check=True,
                   stdout=subprocess.DEVNULL)
    prog = [int(l, 16) for l in open(p)]
    g, r = open(tg).read().split('\n'), open(tr).read().split('\n')
    for c, (gl, rl) in enumerate(zip(g, r)):
        if gl.strip():
            cycles += 1
            opcount[NAMES[(prog[int(gl.split()[0], 16)] >> 30) & 31]] += 1
        if gl != rl:
            print(f"seed {seed} cycle {c} MISMATCH\n gold: {gl}\n rtl : {rl}")
            fails += 1
            break
    if len(g) != len(r):
        print(f"seed {seed}: trace length differs"); fails += 1
print(f"[{SIM}] {N} random programs x {NCYC} cycles = {cycles} cycles compared, "
      f"{fails} failing programs -> {'PASS' if fails == 0 else 'FAIL'}")
print("executed-op coverage:", dict(sorted(opcount.items(), key=lambda kv: -kv[1])))
