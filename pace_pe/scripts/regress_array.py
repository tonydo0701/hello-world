"""Random 8x8 co-simulation: pace_cgra RTL (via host bus) vs pace-sim grid."""
import os, subprocess, sys, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B = os.path.join(ROOT, 'build', 'arr')
GOLD = os.path.join(ROOT, 'model/golden/target/release/pace-pe-golden')
sys.path.insert(0, os.path.join(ROOT, 'scripts'))
import gen_array, cgra_image
N = int(sys.argv[1]) if len(sys.argv) > 1 else 20
NCYC = int(sys.argv[2]) if len(sys.argv) > 2 else 150
SIM = sys.argv[3] if len(sys.argv) > 3 else 'iverilog'
run = (['vvp', '-n', os.path.join(ROOT, 'build', 'tb_cgra.vvp')] if SIM == 'iverilog'
       else [os.path.join(ROOT, 'build', 'obj_tb_cgra', 'Vtb_cgra')])
fails = 0; cycles = 0
for seed in range(N):
    k = os.path.join(B, f'{SIM}_k'); shutil.rmtree(k, ignore_errors=True)
    gen_array.gen(seed, k)
    img = os.path.join(B, f'{SIM}.writes')
    with open(img, 'w') as f:
        for a, v in cgra_image.image(k):
            f.write(f'{a:05x} {v:08x}\n')
    g = subprocess.run([GOLD, 'grid', k, str(NCYC), f'{B}/{SIM}_g.trace', f'{B}/{SIM}_g.dm'],
                       capture_output=True, text=True)
    if g.returncode:
        print(f'seed {seed}: golden error\n{g.stderr[-600:]}'); fails += 1; continue
    subprocess.run(run + [f'+IMG={img}', f'+TRACE={B}/{SIM}_r.trace', f'+DMOUT={B}/{SIM}_r.dm',
                          f'+MAXCYC={NCYC}'], check=True, capture_output=True)
    gt, rt = open(f'{B}/{SIM}_g.trace').read().splitlines(), open(f'{B}/{SIM}_r.trace').read().splitlines()
    bad = None
    for c, (a, b) in enumerate(zip(gt, rt)):
        if a != b:
            fa, fb = a.split(), b.split()
            i = next(i for i in range(len(fa)) if fa[i] != fb[i])
            bad = f'cycle {c} PE{i // 4} field {"pc op1 op2 res".split()[i % 4]}: gold {fa[i]} rtl {fb[i]}'
            break
    if bad is None and len(gt) != len(rt):
        bad = f'trace length gold {len(gt)} rtl {len(rt)}'
    if bad is None:
        for d in range(8):
            if open(f'{B}/{SIM}_g.dm{d}').read() != open(f'{B}/{SIM}_r.dm{d}').read():
                bad = f'DM{d} contents differ'; break
    if bad:
        print(f'seed {seed}: MISMATCH {bad}'); fails += 1
    cycles += len(gt)
print(f'[{SIM}] {N} random 8x8 kernels, {cycles} array-cycles x 64 PEs + 8 DMs compared, '
      f'{fails} failing -> {"PASS" if fails == 0 else "FAIL"}')
