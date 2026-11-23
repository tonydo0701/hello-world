"""Export bit-accurate golden vectors for RTL verification.
Writes, for every traced tensor of one frame: <name>.hex (one value per line,
two's complement, width from the value range) and all tensors in golden.npz,
plus manifest.json with shapes, bit widths and the per-tensor scales.

Usage: python3 export_vectors.py [--full] [--out vectors]"""
import argparse, json, os
import numpy as np
from config import TINY, FULL
from params import init_params, make_inputs
from float_model import run_sequence
from int_model import QModel


def width(a):
    lo, hi = int(a.min()), int(a.max())
    for b in (8, 16, 32, 48, 64):
        if -2 ** (b - 1) <= lo and hi <= 2 ** (b - 1) - 1:
            return b
    raise ValueError("value out of range")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--full", action="store_true", help="640x480 instead of the small test size")
    ap.add_argument("--out", default="vectors")
    args = ap.parse_args()
    cfg = FULL if args.full else TINY
    P = init_params(cfg)
    frames, imus = make_inputs(cfg, cfg.mem_frames + 1)
    _, rec = run_sequence(cfg, P, frames, imus)          # calibration
    qm = QModel(cfg, P, rec.maxabs)
    qm.run_sequence(frames[:-1], imus[:-1])              # fill temporal memory (untraced)
    memory = {}
    for img, imu in zip(frames[:-1], imus[:-1]):
        _, _, new = qm.forward(img, imu, memory)
        for l, pm in new.items():
            memory[l] = ([pm] + memory.get(l, []))[: cfg.mem_frames]
    qm.trace = {}
    qm.forward(frames[-1], imus[-1], memory)             # traced frame
    os.makedirs(args.out, exist_ok=True)
    manifest = {"config": cfg.__dict__ | {"name": "FULL" if args.full else "TINY"},
                "scales": qm.s, "tensors": {}}
    for name, a in qm.trace.items():
        b = width(a)
        with open(os.path.join(args.out, name + ".hex"), "w") as fh:
            for v in a.ravel():
                fh.write(format(int(v) & (2 ** b - 1), f"0{b // 4}x") + "\n")
        manifest["tensors"][name] = {"shape": list(a.shape), "bits": b}
    np.savez_compressed(os.path.join(args.out, "golden.npz"), **qm.trace)
    with open(os.path.join(args.out, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=1)
    print(f"wrote {len(qm.trace)} tensors to {args.out}/")


if __name__ == "__main__":
    main()
