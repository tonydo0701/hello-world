"""Integer-only forward pass of GateFormer-T (bit-accurate golden model).
Activations are int8 with static per-tensor scales from calibration; weights are
int8 per tensor; biases int32. The only float operations are on the host:
quantising the inputs and dequantising the two outputs."""
import numpy as np
from float_model import im2col
from int_ops import (scale_for, quantize, requant, imatmul, int_add, pool2x2,
                     i_softmax_weights, i_attn_normalise, i_gelu, i_layernorm, AV_FRAC, LN_FRAC)


class QModel:
    def __init__(self, cfg, P, maxabs):
        self.cfg, self.P = cfg, P
        self.s = {k: scale_for(v) for k, v in maxabs.items()}
        self.trace = None                 # set to a dict to capture intermediate tensors

    # -- helpers
    def _t(self, name, q):
        if self.trace is not None:
            self.trace[name] = q.copy()
        return q

    def qlin(self, xq, sx, p, name, relu=False):
        sw = scale_for(np.abs(p["w"]).max())
        acc = imatmul(xq, quantize(p["w"], sw)) + quantize(p["b"], sx * sw, bits=32)
        if relu:
            acc = np.maximum(acc, 0)
        return self._t(name, requant(acc, sx * sw / self.s[name]))

    def qln(self, xq, sx, p, name):
        sg = scale_for(np.abs(p["g"]).max())
        acc = i_layernorm(xq, quantize(p["g"], sg), quantize(p["b"], sg * 2 ** -LN_FRAC, bits=32))
        return self._t(name, requant(acc, sg * 2 ** -LN_FRAC / self.s[name]))

    def qmha(self, hq, sh, kvq, P, pre, tag):
        s, H = self.s, self.cfg.n_heads
        q = self.qlin(hq, sh, P[pre + "q"], f"{tag}.q")
        k = self.qlin(kvq, sh, P[pre + "k"], f"{tag}.k")
        v = self.qlin(kvq, sh, P[pre + "v"], f"{tag}.v")
        dh = q.shape[1] // H
        outs = []
        for h in range(H):
            sl = slice(h * dh, (h + 1) * dh)
            acc = imatmul(q[:, sl], k[:, sl].T)
            w, rowsum = i_softmax_weights(acc, s[f"{tag}.q"] * s[f"{tag}.k"] / np.sqrt(dh))
            self._t(f"{tag}.w{h}", w)
            outs.append(i_attn_normalise(imatmul(w, v[:, sl]), rowsum))
        av = self._t(f"{tag}.av", requant(np.concatenate(outs, 1), 2 ** -AV_FRAC * s[f"{tag}.v"] / s[f"{tag}.av"]))
        return self.qlin(av, s[f"{tag}.av"], P[pre + "o"], f"{tag}.proj")

    # -- forward
    def forward(self, img, imu, memory):
        cfg, P, s = self.cfg, self.P, self.s
        x = self._t("input", img.astype(np.int64) - 128)[:, :, None]      # scale 1/128
        sx = 1 / 128
        for i, st in enumerate(P["stem"][:-1]):
            cols, Ho, Wo = im2col(x, 3, 2, 1)
            x = self.qlin(cols, sx, st, f"stem{i}", relu=True).reshape(Ho, Wo, -1)
            sx = s[f"stem{i}"]
        cols, _, _ = im2col(x, 2, 2, 0)
        g = self.qlin(cols, sx, P["stem"][-1], "stem_out")
        g = self._t("embed", int_add(g, s["stem_out"], quantize(P["pos"], s["embed"]), s["embed"], s["embed"]))
        imu_q = quantize(imu, 1 / 32)                                     # IMU input: fixed scale 1/32
        sw = scale_for(np.abs(P["imu"]["w"]).max())
        acc = imatmul(imu_q[None, :], quantize(P["imu"]["w"], sw)) + quantize(P["imu"]["b"] + P["imu_type"], sw / 32, bits=32)
        t_imu = requant(acc, sw / 32 / s["tok"])
        g = requant(g, s["embed"] / s["tok"])
        x = self._t("tok", np.concatenate([g, t_imu], 0))
        sx = s["tok"]
        new_mem = {}
        for l, L in enumerate(P["layers"]):
            tag = f"L{l}"
            h = self.qln(x, sx, L["ln1"], f"{tag}.ln1")
            pooled = pool2x2(h[:-1].reshape(cfg.grid_h, cfg.grid_w, -1))
            kv = np.concatenate([pooled, h[-1:]], 0)
            a = self.qmha(h, s[f"{tag}.ln1"], kv, L, "", f"{tag}.sa")
            x = self._t(f"{tag}.res1", int_add(x, sx, a, s[f"{tag}.sa.proj"], s[f"{tag}.res1"]))
            sx = s[f"{tag}.res1"]
            if l in cfg.temporal_layers:
                new_mem[l] = (pooled, s[f"{tag}.ln1"])
                prev = memory.get(l, [])
                if prev:
                    hc = self.qln(x, sx, L["lnc"], f"{tag}.lnc")
                    sm = s[f"{tag}.mem"]
                    m = np.concatenate([int_add(pm, spm, quantize(P["age"][i], sm), sm, sm)
                                        for i, (pm, spm) in enumerate(prev)], 0)
                    a = self.qmha(hc, s[f"{tag}.lnc"], self._t(f"{tag}.mem", m), L, "c", f"{tag}.ca")
                    x = self._t(f"{tag}.resc", int_add(x, sx, a, s[f"{tag}.ca.proj"], s[f"{tag}.resc"]))
                    sx = s[f"{tag}.resc"]
            h = self.qln(x, sx, L["ln2"], f"{tag}.ln2")
            sh = s[f"{tag}.ln2"]
            sw = scale_for(np.abs(L["fc1"]["w"]).max())
            acc = imatmul(h, quantize(L["fc1"]["w"], sw)) + quantize(L["fc1"]["b"], sh * sw, bits=32)
            gq, sg = i_gelu(acc, sh * sw)
            a = self._t(f"{tag}.gelu", requant(gq, sg / s[f"{tag}.gelu"]))
            f2 = self.qlin(a, s[f"{tag}.gelu"], L["fc2"], f"{tag}.fc2")
            x = self._t(f"{tag}.res2", int_add(x, sx, f2, s[f"{tag}.fc2"], s[f"{tag}.res2"]))
            sx = s[f"{tag}.res2"]
        h = self.qln(x, sx, P["lnf"], "lnf")
        corners = self.qlin(h[:-1], s["lnf"], P["corner"], "corner")
        st1 = self.qlin(h[-1:], s["lnf"], P["state1"], "state1", relu=True)
        state = self.qlin(st1, s["state1"], P["state2"], "state")
        c = corners.reshape(cfg.grid_h, cfg.grid_w, cfg.n_corners, 3) * s["corner"]
        return c, state[0] * s["state"], new_mem

    def run_sequence(self, frames, imus):
        memory, outs = {}, []
        for img, imu in zip(frames, imus):
            c, st, new = self.forward(img, imu, memory)
            outs.append((c, st))
            for l, pm in new.items():
                memory[l] = ([pm] + memory.get(l, []))[: self.cfg.mem_frames]
        return outs
