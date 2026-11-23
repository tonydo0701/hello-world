"""GateFormer-T: a small, integer-friendly encoder-only transformer for
high-speed drone perception (Tier 3). All sizes are multiples of 32 where it
matters so the matrix multiplies tile cleanly onto a 32x32 Gemmini array."""
from dataclasses import dataclass


@dataclass(frozen=True)
class Config:
    img_h: int = 480            # grayscale camera frame
    img_w: int = 640
    stem_ch: tuple = (24, 48, 96)  # 3x conv3x3 stride 2 (+ReLU), then conv2x2 stride 2 -> d_model
    d_model: int = 192
    n_heads: int = 3            # head dim 64
    d_ff: int = 768
    n_layers: int = 6
    kv_pool: int = 2            # keys/values from 2x2-pooled tokens (spatial-reduction attention)
    temporal_layers: tuple = (4, 5)  # these layers also cross-attend to previous frames
    mem_frames: int = 3         # number of previous frames kept as memory
    imu_dim: int = 6            # pre-integrated gyro (3) + accel (3) since last frame
    n_corners: int = 4          # gate corners predicted per grid cell
    state_dim: int = 10         # gate pose (6) + ego velocity (3) + confidence (1)

    @property
    def stride(self):
        return 16

    @property
    def grid_h(self):
        return self.img_h // self.stride

    @property
    def grid_w(self):
        return self.img_w // self.stride

    @property
    def n_grid(self):
        return self.grid_h * self.grid_w

    @property
    def n_tokens(self):          # grid tokens + 1 IMU token
        return self.n_grid + 1

    @property
    def n_pooled(self):
        return (self.grid_h // self.kv_pool) * (self.grid_w // self.kv_pool)

    @property
    def d_head(self):
        return self.d_model // self.n_heads


FULL = Config()
# Small configuration used by the unit tests so they run in seconds.
TINY = Config(img_h=96, img_w=128, n_layers=3, temporal_layers=(2,), mem_frames=2)
