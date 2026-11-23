"""Float reference forward pass of GateFormer-T. It also records the
max-abs value of every named activation, which the integer model uses as
its calibration (static per-tensor INT8 scales)."""
import numpy as np


def erf(x):
    # Abramowitz & Stegun 7.1.26, |error| < 1.5e-7
    s = np.sign(x)
    x = np.abs(x)
    t = 1.0 / (1.0 + 0.3275911 * x)
    y = 1 - (((((1.061405429 * t - 1.453152027) * t) + 1.421413741) * t - 0.284496736) * t + 0.254829592) * t * np.exp(-x * x)
    return s * y


def gelu(x):
    return 0.5 * x * (1 + erf(x / np.sqrt(2)))


def layernorm(x, p, eps=1e-6):
    mu = x.mean(-1, keepdims=True)
    var = ((x - mu) ** 2).mean(-1, keepdims=True)
    return (x - mu) / np.sqrt(var + eps) * p["g"] + p["b"]


def softmax(x):
    x = x - x.max(-1, keepdims=True)
    e = np.exp(x)
    return e / e.sum(-1, keepdims=True)


def im2col(x, k, stride, pad):
    """x: (H, W, C) -> (Ho*Wo, k*k*C), Ho, Wo"""
    H, W, C = x.shape
    xp = np.pad(x, ((pad, pad), (pad, pad), (0, 0)))
    Ho = (H + 2 * pad - k) // stride + 1
    Wo = (W + 2 * pad - k) // stride + 1
    cols = np.empty((Ho, Wo, k, k, C), dtype=x.dtype)
    for i in range(k):
        for j in range(k):
            cols[:, :, i, j, :] = xp[i:i + stride * Ho:stride, j:j + stride * Wo:stride, :]
    return cols.reshape(Ho * Wo, k * k * C), Ho, Wo


def pool2x2(grid):
    """grid: (h, w, d) -> ((h/2)*(w/2), d) average pooling"""
    h, w, d = grid.shape
    g = grid[: h // 2 * 2, : w // 2 * 2].reshape(h // 2, 2, w // 2, 2, d)
    return g.mean(axis=(1, 3)).reshape(-1, d)


class Recorder:
    def __init__(self):
        self.maxabs = {}

    def __call__(self, name, x):
        m = float(np.max(np.abs(x)))
        self.maxabs[name] = max(self.maxabs.get(name, 0.0), m)
        return x


def mha(xq, xkv, P, pre, n_heads, rec, tag):
    q = rec(f"{tag}.q", xq @ P[pre + "q"]["w"] + P[pre + "q"]["b"])
    k = rec(f"{tag}.k", xkv @ P[pre + "k"]["w"] + P[pre + "k"]["b"])
    v = rec(f"{tag}.v", xkv @ P[pre + "v"]["w"] + P[pre + "v"]["b"])
    dh = q.shape[1] // n_heads
    outs = []
    for h in range(n_heads):
        sl = slice(h * dh, (h + 1) * dh)
        s = q[:, sl] @ k[:, sl].T / np.sqrt(dh)
        outs.append(softmax(s) @ v[:, sl])
    av = rec(f"{tag}.av", np.concatenate(outs, axis=1))
    return rec(f"{tag}.proj", av @ P[pre + "o"]["w"] + P[pre + "o"]["b"])


def forward(cfg, P, img, imu, memory, rec=None):
    """img: uint8 (H, W); imu: (imu_dim,); memory: dict layer -> list of previous
    pooled kv sources (newest first). Returns (corners, state, new_memory_entries)."""
    rec = rec or Recorder()
    x = (img.astype(np.float64) - 128.0) / 128.0
    x = x[:, :, None]
    for i, st in enumerate(P["stem"][:-1]):
        cols, Ho, Wo = im2col(x, 3, 2, 1)
        x = rec(f"stem{i}", np.maximum(cols @ st["w"] + st["b"], 0)).reshape(Ho, Wo, -1)
    cols, Ho, Wo = im2col(x, 2, 2, 0)
    g = rec("stem_out", cols @ P["stem"][-1]["w"] + P["stem"][-1]["b"])
    g = rec("embed", g + P["pos"])
    t_imu = rec("imu", imu @ P["imu"]["w"] + P["imu"]["b"] + P["imu_type"])
    x = rec("tok", np.concatenate([g, t_imu[None, :]], axis=0))
    new_mem = {}
    for l, L in enumerate(P["layers"]):
        tag = f"L{l}"
        h = rec(f"{tag}.ln1", layernorm(x, L["ln1"]))
        pooled = pool2x2(h[:-1].reshape(cfg.grid_h, cfg.grid_w, -1))
        kv = np.concatenate([pooled, h[-1:]], axis=0)
        x = rec(f"{tag}.res1", x + mha(h, kv, L, "", cfg.n_heads, rec, f"{tag}.sa"))
        if l in cfg.temporal_layers:
            new_mem[l] = pooled
            prev = memory.get(l, [])
            if prev:
                hc = rec(f"{tag}.lnc", layernorm(x, L["lnc"]))
                m = rec(f"{tag}.mem", np.concatenate([pm + P["age"][a] for a, pm in enumerate(prev)], axis=0))
                x = rec(f"{tag}.resc", x + mha(hc, m, L, "c", cfg.n_heads, rec, f"{tag}.ca"))
        h = rec(f"{tag}.ln2", layernorm(x, L["ln2"]))
        a = rec(f"{tag}.fc1", h @ L["fc1"]["w"] + L["fc1"]["b"])
        a = rec(f"{tag}.gelu", gelu(a))
        x = rec(f"{tag}.res2", x + rec(f"{tag}.fc2", a @ L["fc2"]["w"] + L["fc2"]["b"]))
    x = rec("lnf", layernorm(x, P["lnf"]))
    corners = rec("corner", x[:-1] @ P["corner"]["w"] + P["corner"]["b"])
    s = rec("state1", np.maximum(x[-1] @ P["state1"]["w"] + P["state1"]["b"], 0))
    state = rec("state", s @ P["state2"]["w"] + P["state2"]["b"])
    return corners.reshape(cfg.grid_h, cfg.grid_w, cfg.n_corners, 3), state, new_mem


def run_sequence(cfg, P, frames, imus, rec=None):
    """Runs frames in order, maintaining the temporal memory. Returns outputs per frame."""
    rec = rec or Recorder()
    memory, outs = {}, []
    for img, imu in zip(frames, imus):
        c, s, new = forward(cfg, P, img, imu, memory, rec)
        outs.append((c, s))
        for l, pm in new.items():
            memory[l] = ([pm] + memory.get(l, []))[: cfg.mem_frames]
    return outs, rec
