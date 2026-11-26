/* pace_cgra.h - bare-metal driver for the re-created PACE CGRA.
 *
 * The CGRA is a memory-mapped slave of the RISC-V core. Everything (PE
 * configuration memories, AGU programs, data memories, run control) is
 * reached with ordinary 32-bit loads/stores into a 512 KB window.
 */
#ifndef PACE_CGRA_H
#define PACE_CGRA_H
#include <stdint.h>

#define CGRA_BASE        0x10000000u
#define CGRA_REG(off)    (*(volatile uint32_t *)(CGRA_BASE + (off)))

/* ---- address map (byte offsets inside the CGRA window) ---- */
#define CGRA_PE_CM(pe, e, hi)   (((pe) << 10) | (0u << 8) | ((e) << 3) | ((hi) << 2))
#define CGRA_AGU_CM(pe, e)      (((pe) << 10) | (1u << 8) | ((e) << 2))
#define CGRA_AGU_ARF(pe, e)     (((pe) << 10) | (2u << 8) | ((e) << 2))
#define CGRA_AGU_MAX(pe)        (((pe) << 10) | (3u << 8))
#define CGRA_DM(d, byte)        (0x20000u | ((d) / 4u) << 16 | ((d) % 4u) << 14 | (byte))
#define CGRA_CTRL        0x60000u   /* W: bit0 START, bit1 STOP            */
#define CGRA_STATUS      0x60004u   /* R: bit0 BUSY bit1 DONE bit2 STOPPED */
#define CGRA_CYCLES      0x60008u
#define CGRA_IRQ_EN      0x6000Cu
#define CGRA_ID          0x60010u
#define CGRA_RUN_LIMIT   0x60014u

#define CGRA_ST_BUSY     1u
#define CGRA_ST_DONE     2u
#define CGRA_ST_STOPPED  4u

/* Write one 64-bit configuration word into PE `pe` (0..63 = y*8+x), entry e.
 * Low word first: the high-word write commits the 64-bit entry. */
static inline void cgra_write_cfg(unsigned pe, unsigned e, uint64_t w) {
    CGRA_REG(CGRA_PE_CM(pe, e, 0)) = (uint32_t)w;
    CGRA_REG(CGRA_PE_CM(pe, e, 1)) = (uint32_t)(w >> 32);
}

/* Replay a pre-linked image: list of {offset, value} host writes. */
static inline void cgra_load_image(const unsigned int (*img)[2], unsigned n) {
    for (unsigned i = 0; i < n; i++) CGRA_REG(img[i][0]) = img[i][1];
}

static inline void cgra_start(void)        { CGRA_REG(CGRA_CTRL) = 1u; }
static inline uint32_t cgra_status(void)   { return CGRA_REG(CGRA_STATUS); }

/* Busy-wait until the kernel finishes (AGU end) or is stopped. */
static inline uint32_t cgra_wait(void) {
    uint32_t s;
    do { s = cgra_status(); } while (s & CGRA_ST_BUSY);
    return s;
}
#endif
