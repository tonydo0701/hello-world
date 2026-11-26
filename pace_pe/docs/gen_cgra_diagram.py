"""Generate docs/pace_cgra_soc_diagram.svg: RISC-V host + 8x8 CGRA (ISSCC style)."""
import os
from xml.sax.saxutils import escape as _esc

W, H = 1600, 1130
F = "Arial, Helvetica, sans-serif"
C_RT, C_ALU, C_CTL, C_MEM, C_CPU = "#dbe8f5", "#fde3c4", "#e0efd6", "#ececec", "#efe3f6"
BLUE = "#1f4e9c"
o = []
add = o.append


def text(x, y, s, size=13, anchor="start", weight="normal", fill="#000", style="normal"):
    add(f'<text x="{x}" y="{y}" font-family="{F}" font-size="{size}" text-anchor="{anchor}" '
        f'font-weight="{weight}" font-style="{style}" fill="{fill}">{_esc(s)}</text>')


def rect(x, y, w, h, fill="#fff", stroke="#000", sw=1.4, rx=0, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{d}/>')


def line(pts, sw=1.6, color="#000", dash=None, arrow="end"):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    mk = "ah" if color == "#000" else "ahb"
    m = ""
    if arrow in ("end", "both"):
        m += f' marker-end="url(#{mk})"'
    if arrow in ("start", "both"):
        m += f' marker-start="url(#{mk})"'
    p = " ".join(f"{x},{y}" for x, y in pts)
    add(f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="{sw}"{d}{m}/>')


def slash(x, y, n):
    add(f'<line x1="{x-5}" y1="{y+6}" x2="{x+5}" y2="{y-6}" stroke="#000" stroke-width="1.2"/>')
    text(x, y - 9, str(n), 10, "middle")


add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
add('<defs>'
    '<marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    '<path d="M0,0 L10,5 L0,10 z" fill="#000"/></marker>'
    f'<marker id="ahb" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    f'<path d="M0,0 L10,5 L0,10 z" fill="{BLUE}"/></marker>'
    '<marker id="ahs" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">'
    '<path d="M0,0 L10,5 L0,10 z" fill="#555"/></marker></defs>')
rect(0, 0, W, H, "#fff", "none", 0)

# ======================================================================= RISC-V subsystem
rect(30, 60, 400, 640, C_CPU, "#000", 1.6, 6)
text(46, 84, "RISC-V HOST SUBSYSTEM", 15, weight="bold")
rect(60, 110, 340, 110, "#fff", "#000", 1.4)
text(230, 138, "RISC-V core", 14, "middle", "bold")
text(230, 158, "PicoRV32 · RV32IM · IRQ", 12, "middle")
text(230, 176, "runs the CGRA driver (C firmware):", 11, "middle", style="italic")
text(230, 192, "configure → start → wait → read back", 11, "middle", style="italic")
text(230, 210, "(PACE silicon: RISC-V controller, 42% of die area)", 10, "middle", fill="#555")
# system bus
add('<line x1="230" y1="220" x2="230" y2="262" stroke="#000" stroke-width="3"/>')
add('<line x1="70" y1="262" x2="410" y2="262" stroke="#000" stroke-width="5"/>')
text(244, 285, "native bus", 10.5, weight="bold")
text(244, 297, "32b valid/ready", 10)
rect(60, 300, 150, 90, "#fff", "#000", 1.3)
text(135, 330, "SRAM 64 KB", 13, "middle", "bold")
text(135, 348, "firmware, stack,", 11, "middle")
text(135, 363, "kernel image", 11, "middle")
text(135, 380, "0x0000_0000", 10.5, "middle", fill=BLUE)
line([(135, 262), (135, 300)], arrow="both")
rect(240, 310, 160, 80, "#fff", "#000", 1.3)
text(320, 334, "Console / exit", 13, "middle", "bold")
text(320, 348, "putchar, exit code", 11, "middle")
text(320, 380, "0x2000_0000", 10.5, "middle", fill=BLUE)
line([(320, 262), (320, 310)], arrow="both")
rect(240, 430, 160, 110, "#fff", "#000", 1.3)
text(320, 455, "Bus bridge", 13, "middle", "bold")
text(320, 473, "native → APB", 11, "middle")
text(320, 489, "SETUP / ACCESS", 11, "middle")
text(320, 505, "32b, 0 wait states", 11, "middle")
text(320, 528, "0x1000_0000 + 512 KB", 10.5, "middle", fill=BLUE)
add('<line x1="410" y1="262" x2="410" y2="420" stroke="#000" stroke-width="3"/>')
line([(410, 420), (410, 425), (330, 425), (330, 430)], 2)
text(60, 600, "Every CGRA resource is an ordinary", 11.5, style="italic")
text(60, 616, "32-bit load/store target for the core:", 11.5, style="italic")
text(60, 632, "no custom instructions, no DMA needed.", 11.5, style="italic")
text(60, 660, "irq: DONE/STOPPED → PicoRV32 irq[3]", 11.5, style="italic", fill=BLUE)

# APB link into CGRA host interface
line([(400, 485), (455, 485), (455, 132), (560, 132)], 2.4, arrow="both")
text(462, 300, "APB", 13, weight="bold")
text(462, 316, "19b addr", 10)
text(462, 330, "32b data", 10)
text(462, 344, "0 wait", 10)
line([(560, 165), (400, 165)], 1.4, BLUE, "6 3")
text(470, 182, "irq", 11, weight="bold", fill=BLUE)

# ======================================================================= CGRA
rect(540, 40, 1030, 900, "none", "#000", 2.4, 6)
text(556, 62, "CGRA (PACE-style, 8 × 8)", 16, weight="bold")
text(790, 62, "64 PEs · 8 × 8 KB data memories (left + right) · 16 AGUs · 64b mesh", 12.5, style="italic")
rect(560, 80, 990, 100, C_CTL, "#000", 1.4, 4)
text(574, 100, "HOST INTERFACE", 13.5, weight="bold")
text(574, 120, "address decoder: [18:17] 00 PE / AGU · 01 data memory · 11 control", 11.5)
text(574, 138, "PE config word = two 32b writes (low word buffered, high word commits)", 11.5)
text(574, 156, "CTRL (start/stop) · STATUS (busy/done/stopped) · CYCLES · IRQ_EN · ID 0x13E · RUN_LIMIT", 11.5)
rect(1240, 92, 296, 78, "#fff", "#000", 1.2)
text(1388, 110, "RUN CONTROL", 12, "middle", "bold")
text(1388, 127, "START → clear PE/AGU state → RUN", 10.5, "middle")
text(1388, 142, "END = any AGU triggered at max count", 10.5, "middle")
text(1388, 157, "→ DONE (+irq); state frozen", 10.5, "middle")

# config distribution bus
add(f'<line x1="600" y1="196" x2="1510" y2="196" stroke="{BLUE}" stroke-width="2.2" stroke-dasharray="7 4"/>')
line([(1000, 180), (1000, 196)], 1.6, BLUE, arrow="none")
text(1010, 192, "config / data write bus (to every PE CM, AGU, DM)", 10.5, fill=BLUE)

GX, GY, P, S = 790, 228, 72, 50
for y in range(8):
    for x in range(8):
        px, py = GX + P * x, GY + P * y
        mem = x in (0, 7)
        rect(px, py, S, S, C_ALU if not mem else "#f8d3a6", "#000", 1.2)
        text(px + S / 2, py + 22, f"PE", 11, "middle", "bold")
        text(px + S / 2, py + 37, f"{y},{x}", 10, "middle")
        if x < 7:   # horizontal link (bidirectional)
            add(f'<line x1="{px+S}" y1="{py+19}" x2="{px+P}" y2="{py+19}" stroke="#555" stroke-width="1.1" marker-end="url(#ahs)"/>')
            add(f'<line x1="{px+P}" y1="{py+31}" x2="{px+S}" y2="{py+31}" stroke="#555" stroke-width="1.1" marker-end="url(#ahs)"/>')
        if y < 7:
            add(f'<line x1="{px+19}" y1="{py+S}" x2="{px+19}" y2="{py+P}" stroke="#555" stroke-width="1.1" marker-end="url(#ahs)"/>')
            add(f'<line x1="{px+31}" y1="{py+P}" x2="{px+31}" y2="{py+S}" stroke="#555" stroke-width="1.1" marker-end="url(#ahs)"/>')
text(GX + P * 3.5 + S / 2 - P / 2 + 10, GY + P * 8 + 8, "64b mesh links, N/S/W/E, combinational multi-hop (SMART-style)", 11.5, "middle", style="italic")

# AGUs + data memories
for side in (0, 1):
    for y in range(8):
        py = GY + P * y
        if side == 0:
            ax, pe_x = 722, GX
            line([(pe_x, py + 38), (ax + 46, py + 38)], 1.2)               # trigger PE -> AGU
            line([(ax, py + 38), (ax - 14, py + 38)], 1.3)                 # AGU -> DM addr
            line([(ax - 14, py + 12), (pe_x, py + 12)], 1.3, arrow="both")  # data
        else:
            ax, pe_x = GX + P * 7 + S + 22, GX + P * 7 + S
            line([(pe_x, py + 38), (ax, py + 38)], 1.2)
            line([(ax + 46, py + 38), (ax + 60, py + 38)], 1.3)
            line([(pe_x, py + 12), (ax + 60, py + 12)], 1.3, arrow="both")
        rect(ax, py + 26, 46, 22, C_CTL, "#000", 1.1)
        text(ax + 23, py + 41, f"AGU{y + 8 * side}", 9.5, "middle", "bold")
    for d in range(4):
        py = GY + P * 2 * d - 4
        dx = 590 if side == 0 else GX + P * 7 + S + 82
        rect(dx, py, 118, P + S + 8, C_MEM, "#000", 1.4)
        idx = d + 4 * side
        text(dx + 59, py + 36, f"DM{idx}", 14, "middle", "bold")
        text(dx + 59, py + 54, "8 KB SRAM", 11, "middle")
        text(dx + 59, py + 69, "2 PE ports + host", 10.5, "middle")
        text(dx + 59, py + 84, "8/16/64b, byte addr", 10.5, "middle")
        text(dx + 59, py + 104, f"rows {2*d}, {2*d+1}", 10, "middle", style="italic")
        text(dx + 59, py + 118, f"0x{0x20000 | side << 16 | d << 14:05x}", 9.5, "middle", fill=BLUE)
        add(f'<line x1="{dx + 59}" y1="196" x2="{dx + 59}" y2="{py}" stroke="{BLUE}" stroke-width="1" stroke-dasharray="3 3"/>') if d == 0 else None
text(596, 846, "left data memories", 11, style="italic")
text(1424, 846, "right data memories", 11, style="italic")
for x in range(8):
    add(f'<line x1="{GX + P * x + S / 2}" y1="196" x2="{GX + P * x + S / 2}" y2="{GY}" stroke="{BLUE}" stroke-width="1" stroke-dasharray="3 3"/>')

# legend under the array
rect(560, 862, 990, 64, "#fff", "#000", 1, 3)
rect(574, 874, 18, 14, "#f8d3a6", "#000", 1)
text(598, 886, "memory PE (columns 0, 7): CM bit 59 triggers its AGU; load data → op1 two cycles later; store data = op1", 11.5)
rect(574, 898, 18, 14, C_ALU, "#000", 1)
text(598, 910, "compute PE: 16 × 64b config memory, 16b INT + 8 × FP8 ALU, 6 × 7 router (see PE diagram)", 11.5)

# ======================================================================= bottom: driver sequence + address map
rect(30, 720, 400, 220, "#fff", "#000", 1.3, 4)
text(46, 744, "Driver sequence (soc/fw/main.c)", 13.5, weight="bold")
steps = ["1  write PE config words  (pe<<10 | e<<3)",
         "2  write AGU CM / ARF / MAX  (edge PEs)",
         "3  write input data into DM0..7",
         "4  IRQ_EN = 1;  CTRL = START",
         "5  wait: poll STATUS.BUSY or take irq",
         "6  read CYCLES, read results from DMs"]
for i, s in enumerate(steps):
    text(50, 770 + 26 * i, s, 12)

rect(30, 960, 1540, 140, "#fff", "#000", 1.3, 4)
text(46, 984, "CGRA host address map (byte offset in the 512 KB window; CPU address = 0x1000_0000 + offset)", 13.5, weight="bold")
rows = [("0x00000 + pe·0x400 + e·8 (+4)", "PE config memory, entry e (0–15), low / high word", "16 × 64b per PE, 64 PEs"),
        ("0x00100 + pe·0x400 + e·4", "AGU instruction e  {stride[7:4] width[3:2] const[1] store[0]}", "edge PEs only (x = 0, 7)"),
        ("0x00200 + pe·0x400 + e·4", "AGU address register e (13b byte address)", ""),
        ("0x00300 + pe·0x400", "AGU MAX: [31:24] last instruction, [23:0] iterations", ""),
        ("0x20000 + side·0x10000 + d·0x4000 + byte", "data memory d (0–3) on left (side 0) / right (side 1)", "8 KB each"),
        ("0x60000 …0x60014", "CTRL · STATUS · CYCLES · IRQ_EN · ID · RUN_LIMIT", "run control")]
for i, (a, b, c) in enumerate(rows):
    yy = 1006 + 15.5 * i
    text(50, yy, a, 11.5, weight="bold")
    text(400, yy, b, 11.5)
    text(1100, yy, c, 11.5, style="italic")

add("</svg>")
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pace_cgra_soc_diagram.svg")
open(out, "w").write("\n".join(o))
print("wrote", out)
