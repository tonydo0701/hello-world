"""Deterministic random parameters. Replace with trained weights later
(e.g. initialise layers from DeiT-Tiny, which has the same width: d=192,
3 heads, MLP 768)."""
import numpy as np


def init_params(cfg, seed=0):
    rng = np.random.default_rng(seed)
    d, f = cfg.d_model, cfg.d_ff

    def lin(fan_in, fan_out, gain=1.0):
        return {"w": rng.normal(0, gain / np.sqrt(fan_in), (fan_in, fan_out)),
                "b": rng.normal(0, 0.02, fan_out)}

    def ln():
        return {"g": 1.0 + rng.normal(0, 0.1, d), "b": rng.normal(0, 0.1, d)}

    p = {"stem": []}
    cin = 1
    for c in cfg.stem_ch:
        p["stem"].append(lin(9 * cin, c, gain=np.sqrt(2)))
        cin = c
    p["stem"].append(lin(4 * cin, d))
    p["pos"] = rng.normal(0, 0.1, (cfg.n_grid, d))
    p["imu"] = lin(cfg.imu_dim, d)
    p["imu_type"] = rng.normal(0, 0.1, d)
    p["age"] = rng.normal(0, 0.1, (cfg.mem_frames, d))
    p["layers"] = []
    for i in range(cfg.n_layers):
        L = {"ln1": ln(), "q": lin(d, d, 2.0), "k": lin(d, d, 2.0), "v": lin(d, d), "o": lin(d, d, 0.5),
             "ln2": ln(), "fc1": lin(d, f, 1.5), "fc2": lin(f, d, 0.5)}
        if i in cfg.temporal_layers:
            L.update({"lnc": ln(), "cq": lin(d, d, 2.0), "ck": lin(d, d, 2.0), "cv": lin(d, d),
                      "co": lin(d, d, 0.5)})
        p["layers"].append(L)
    p["lnf"] = ln()
    p["corner"] = lin(d, cfg.n_corners * 3)          # per corner: logit, dx, dy
    p["state1"] = lin(d, d)
    p["state2"] = lin(d, cfg.state_dim)
    return p


def make_inputs(cfg, n_frames, seed=1):
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:cfg.img_h, 0:cfg.img_w]
    frames = []
    for t in range(n_frames):
        # a moving bright square "gate" on a noisy background
        img = rng.normal(90, 25, (cfg.img_h, cfg.img_w))
        cy, cx = cfg.img_h // 2 + 3 * t, cfg.img_w // 2 - 4 * t
        s = cfg.img_h // 4
        ring = (np.abs(yy - cy) < s) & (np.abs(xx - cx) < s) & ~((np.abs(yy - cy) < s - 6) & (np.abs(xx - cx) < s - 6))
        img[ring] = 230
        frames.append(np.clip(img, 0, 255).astype(np.uint8))
    imus = [rng.normal(0, 0.5, cfg.imu_dim) for _ in range(n_frames)]
    return frames, imus
