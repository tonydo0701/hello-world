"""Parameter, compute, memory and Gemmini-cycle estimate for GateFormer-T.
Gemmini model: 32x32 weight-stationary array, one 32x32 weight tile at a time,
cycles per tile = rows streamed (M) + 64 fill/drain. Ignores DMA stalls, so treat
the result as an upper bound on throughput (use FireSim for real numbers)."""
import math
from config import FULL

T = 32


def gemm(name, M, K, N, n=1):
    return dict(name=name, M=M, K=K, N=N, n=n, macs=M * K * N * n,
                cycles=math.ceil(K / T) * math.ceil(N / T) * (M + 2 * T) * n)


def ops(cfg):
    d, f, H, dh = cfg.d_model, cfg.d_ff, cfg.n_heads, cfg.d_head
    N, Nk = cfg.n_tokens, cfg.n_pooled + 1
    Nm = cfg.mem_frames * cfg.n_pooled
    g = []
    h, w, cin = cfg.img_h, cfg.img_w, 1
    for i, c in enumerate(cfg.stem_ch):
        h, w = h // 2, w // 2
        g.append(gemm(f"stem conv{i} 3x3", h * w, 9 * cin, c))
        cin = c
    g.append(gemm("stem conv 2x2 -> d", cfg.n_grid, 4 * cin, d))
    for l in range(cfg.n_layers):
        L = f"L{l}"
        g += [gemm(f"{L} Q proj", N, d, d), gemm(f"{L} K,V proj", Nk, d, d, 2),
              gemm(f"{L} QK^T", N, dh, Nk, H), gemm(f"{L} AV", N, Nk, dh, H),
              gemm(f"{L} out proj", N, d, d)]
        if l in cfg.temporal_layers:
            # K/V of each memory frame are projected once, when the frame enters memory
            g += [gemm(f"{L} cross Q", N, d, d), gemm(f"{L} cross K,V (new frame)", cfg.n_pooled, d, d, 2),
                  gemm(f"{L} cross QK^T", N, dh, Nm, H), gemm(f"{L} cross AV", N, Nm, dh, H),
                  gemm(f"{L} cross out", N, d, d)]
        g += [gemm(f"{L} FC1", N, d, f), gemm(f"{L} FC2", N, f, d)]
    g += [gemm("corner head", cfg.n_grid, d, cfg.n_corners * 3), gemm("state head", 1, d, d), gemm("state out", 1, d, cfg.state_dim)]
    return g


def params(cfg):
    d, f = cfg.d_model, cfg.d_ff
    p, cin = 0, 1
    for c in cfg.stem_ch:
        p += 9 * cin * c + c
        cin = c
    p += 4 * cin * d + d + cfg.n_grid * d + (cfg.imu_dim + 2) * d + cfg.mem_frames * d
    per = 4 * (d * d + d) + 2 * d * f + f + d + 4 * d
    p += cfg.n_layers * per + len(cfg.temporal_layers) * (4 * (d * d + d) + 2 * d)
    p += 2 * d + d * cfg.n_corners * 3 + cfg.n_corners * 3 + d * d + d + d * cfg.state_dim + cfg.state_dim
    return p


def nonlinear(cfg):
    N, Nk, Nm = cfg.n_tokens, cfg.n_pooled + 1, cfg.mem_frames * cfg.n_pooled
    exp = cfg.n_layers * cfg.n_heads * N * Nk + len(cfg.temporal_layers) * cfg.n_heads * N * Nm
    gelu = cfg.n_layers * N * cfg.d_ff
    ln_rows = N * (2 * cfg.n_layers + len(cfg.temporal_layers) + 1)
    return exp, gelu, ln_rows


def report(cfg=FULL, freq_ghz=1.0, util=0.5):
    g = ops(cfg)
    macs = sum(x["macs"] for x in g)
    cyc = sum(x["cycles"] for x in g)
    groups = {}
    for x in g:
        key = x["name"].split(" ", 1)[1] if x["name"].startswith("L") else x["name"]
        key = key.replace("(new frame)", "").strip()
        a = groups.setdefault(key, [0, 0])
        a[0] += x["macs"]; a[1] += x["cycles"]
    print(f"GateFormer-T  input {cfg.img_w}x{cfg.img_h}, {cfg.n_tokens} tokens, {cfg.n_pooled + 1} keys, "
          f"{cfg.n_layers} layers, d={cfg.d_model}, heads={cfg.n_heads}, MLP={cfg.d_ff}")
    p = params(cfg)
    print(f"Parameters: {p/1e6:.2f} M  ->  {p/2**20:.2f} MiB as INT8")
    mem = len(cfg.temporal_layers) * cfg.mem_frames * cfg.n_pooled * cfg.d_model * 3   # src + K + V
    print(f"Temporal memory (pooled tokens + projected K/V): {mem/2**10:.0f} KiB")
    print(f"Largest activation: {cfg.n_tokens * cfg.d_ff / 2**10:.0f} KiB (FC1 output, INT8)")
    print(f"Compute: {macs/1e9:.2f} GMAC = {2*macs/1e9:.2f} GOP per frame")
    print(f"\n{'operation':28s}{'GMAC':>8s}{'share':>8s}{'array util':>12s}")
    for k, (m, c) in sorted(groups.items(), key=lambda kv: -kv[1][0]):
        print(f"{k:28s}{m/1e9:8.3f}{100*m/macs:7.1f}%{100*m/(c*T*T):11.0f}%")
    ex, ge, ln = nonlinear(cfg)
    print(f"\nNon-linear work per frame: {ex/1e6:.1f} M exp, {ge/1e6:.2f} M GELU, {ln} LayerNorm rows")
    t_ideal = cyc / (freq_ghz * 1e9)
    print(f"\nGemmini 32x32 at {freq_ghz} GHz, tiling-limited: {cyc/1e6:.1f} M cycles = {1e3*t_ideal:.2f} ms/frame "
          f"(array util {100*macs/(cyc*T*T):.0f}%)")
    for n in (1, 2):
        t = t_ideal / n / util
        print(f"  {n} Gemmini, {int(util*100)}% further efficiency loss (DMA, non-linear ops): {1e3*t:.1f} ms -> {1/t:.0f} fps")


if __name__ == "__main__":
    report()
