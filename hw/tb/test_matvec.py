"""Generate, simulate and check hardwired matvec modules against the golden model.

  python3 tb/test_matvec.py                  # all 7 projections at TINY size
  python3 tb/test_matvec.py --config qwen3 --only k_proj --p 16   # one full-size matrix
"""
import argparse
import subprocess
import sys
from pathlib import Path

import numpy as np

HW = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HW))
from model.config import QWEN3_0_6B, TINY  # noqa: E402
from model.ref import ACC_BITS, X_BITS, matvec, random_acts  # noqa: E402
from gen.gen_matvec import emit_top, emit_verilog  # noqa: E402
from model.ref import random_weights  # noqa: E402


def pack_vec(vals, bits):
    """Pack signed ints into a hex string, element 0 least significant."""
    mask = (1 << bits) - 1
    word = 0
    for i, v in enumerate(vals):
        word |= (int(v) & mask) << (i * bits)
    return f"{word:0{len(vals) * bits // 4}x}"


def unpack_vec(hexstr, n, bits):
    word = int(hexstr, 16)
    mask = (1 << bits) - 1
    out = []
    for i in range(n):
        v = (word >> (i * bits)) & mask
        out.append(v - (1 << bits) if v >> (bits - 1) else v)
    return np.array(out, dtype=np.int64)


def run_one(name, n, k, p, nv, build, seed, top=False):
    rng = np.random.default_rng(seed)
    w = random_weights(n, k, rng)
    xs = random_acts(k, rng, nv)
    # Include the extreme values so sign handling is tested.
    xs[0, :] = -(1 << (X_BITS - 1))
    w_v = emit_verilog(name, w, p) + emit_top(name, n, k)

    d = build / name
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{name}.v").write_text(w_v)
    (d / "x.hex").write_text("\n".join(pack_vec(x, X_BITS) for x in xs) + "\n")

    defines = [f"-DDUT={name}{'_top' if top else ''}", f"-DN={n}", f"-DK={k}", f"-DNV={nv}",
               f'-DXFILE="{d / "x.hex"}"', f'-DYFILE="{d / "y.hex"}"']
    sim = d / "sim.vvp"
    subprocess.run(["iverilog", "-g2005", "-o", str(sim), *defines,
                    str(HW / "rtl/matvec_core.v"), str(d / f"{name}.v"), str(HW / ("tb/tb_matvec_top.v" if top else "tb/tb_matvec.v"))],
                   check=True)
    out = subprocess.run(["vvp", "-n", str(sim)], check=True, capture_output=True, text=True).stdout
    cycles = next(int(l.split()[1]) for l in out.splitlines() if l.startswith("CYCLES_PER_MATVEC"))

    got = [unpack_vec(l, n, ACC_BITS) for l in (d / "y.hex").read_text().split()]
    bad = sum(not np.array_equal(g, matvec(w, x)) for g, x in zip(got, xs))
    ok = bad == 0 and len(got) == nv
    label = name + ("_top" if top else "")
    print(f"{'PASS' if ok else 'FAIL'}  {label:14s} N={n:5d} K={k:5d} P={p:3d}  "
          f"{nv} vectors" + ("" if top else f", {cycles} cycles/matvec (= K/P {k // p} + 2 handshake)"))
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", choices=["tiny", "qwen3"], default="tiny")
    ap.add_argument("--p", type=int, default=4)
    ap.add_argument("--vectors", type=int, default=8)
    ap.add_argument("--only", help="test a single matrix, e.g. k_proj")
    ap.add_argument("--top", action="store_true", help="test through the narrow _top wrapper")
    args = ap.parse_args()
    cfg = TINY if args.config == "tiny" else QWEN3_0_6B
    build = HW / "build" / args.config

    results = [run_one(name, n, k, args.p, args.vectors, build, seed, args.top)
               for seed, (name, n, k) in enumerate(cfg.matrices())
               if not args.only or name == args.only]
    sys.exit(0 if all(results) else 1)


if __name__ == "__main__":
    main()
