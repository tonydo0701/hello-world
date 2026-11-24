"""Model shapes. QWEN3_0_6B is the real model; TINY keeps the same ratios
(q_proj = 2x hidden, 2:1 GQA, FFN = 3x hidden) so simulations run fast."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    hidden: int
    n_heads: int
    n_kv_heads: int
    head_dim: int
    ffn: int
    n_layers: int
    vocab: int
    rope_theta: float = 1_000_000.0
    rms_eps: float = 1e-6

    def matrices(self):
        """(name, out_features N, in_features K) for each fixed-weight matrix in a layer."""
        q = self.n_heads * self.head_dim
        kv = self.n_kv_heads * self.head_dim
        h, f = self.hidden, self.ffn
        return [
            ("q_proj", q, h), ("k_proj", kv, h), ("v_proj", kv, h), ("o_proj", h, q),
            ("gate_proj", f, h), ("up_proj", f, h), ("down_proj", h, f),
        ]


QWEN3_0_6B = Config(hidden=1024, n_heads=16, n_kv_heads=8, head_dim=128,
                    ffn=3072, n_layers=28, vocab=151_936)

TINY = Config(hidden=64, n_heads=4, n_kv_heads=2, head_dim=32,
              ffn=192, n_layers=2, vocab=256)
