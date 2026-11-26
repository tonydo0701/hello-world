"""Generate docs/pace_pe_block_diagram.svg (ISSCC-style block diagram)."""
import os
from xml.sax.saxutils import escape as _esc

W, H = 1550, 1040
F = "Arial, Helvetica, sans-serif"
C_RT, C_ALU, C_CTL, C_MEM = "#dbe8f5", "#fde3c4", "#e0efd6", "#ececec"
BLUE = "#1f4e9c"
o = []


def add(s):
    o.append(s)


def text(x, y, s, size=13, anchor="start", weight="normal", fill="#000", style="normal", rot=None):
    tr = f' transform="rotate({rot} {x} {y})"' if rot is not None else ""
    add(f'<text x="{x}" y="{y}" font-family="{F}" font-size="{size}" text-anchor="{anchor}" '
        f'font-weight="{weight}" font-style="{style}" fill="{fill}"{tr}>{_esc(s)}</text>')


def rect(x, y, w, h, fill="#fff", stroke="#000", sw=1.4, rx=0, dash=None):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    add(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="{sw}"{d}/>')


def line(pts, sw=1.6, color="#000", dash=None, arrow=True):
    d = f' stroke-dasharray="{dash}"' if dash else ""
    m = ' marker-end="url(#ah)"' if arrow and color == "#000" else (' marker-end="url(#ahb)"' if arrow else "")
    p = " ".join(f"{x},{y}" for x, y in pts)
    add(f'<polyline points="{p}" fill="none" stroke="{color}" stroke-width="{sw}"{d}{m}/>')


def dot(x, y, r=3.2):
    add(f'<circle cx="{x}" cy="{y}" r="{r}" fill="#000"/>')


def slash(x, y, n, dx=0, dy=-9):
    add(f'<line x1="{x-5}" y1="{y+6}" x2="{x+5}" y2="{y-6}" stroke="#000" stroke-width="1.2"/>')
    text(x + dx, y + dy - 2, str(n), 10, "middle")


def vslash(x, y, n):
    add(f'<line x1="{x-6}" y1="{y+5}" x2="{x+6}" y2="{y-5}" stroke="#000" stroke-width="1.2"/>')
    text(x + 9, y + 4, str(n), 10)


def mux(x, y, w, h, label=None, size=10):
    add(f'<polygon points="{x},{y} {x+w},{y+h*0.22} {x+w},{y+h*0.78} {x},{y+h}" '
        f'fill="#fff" stroke="#000" stroke-width="1.3"/>')
    if label:
        text(x + w / 2, y + h / 2 + 4, label, size, "middle")


def ff(x, y, w, h, label, sub=None, fill="#fff"):
    rect(x, y, w, h, fill)
    add(f'<polyline points="{x},{y+h-13} {x+7},{y+h-7} {x},{y+h-1}" fill="none" '
        f'stroke="#000" stroke-width="1.1"/>')
    text(x + w / 2 + 3, y + h / 2 + (-1 if sub else 4), label, 11.5, "middle", "bold")
    if sub:
        text(x + w / 2 + 3, y + h / 2 + 11, sub, 9, "middle")


from xml.sax.saxutils import escape as _esc
MX = 70          # left margin shift for external labels
add(f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}">')
add('<defs>'
    '<marker id="ah" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    '<path d="M0,0 L10,5 L0,10 z" fill="#000"/></marker>'
    f'<marker id="ahb" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">'
    f'<path d="M0,0 L10,5 L0,10 z" fill="{BLUE}"/></marker>'
    '</defs>')
rect(0, 0, W, H, "#fff", "none", 0)
add(f'<g transform="translate({MX},0)">')

# ---------------------------------------------------------------- PE outline
rect(95, 34, 1290, 800, "none", "#000", 2.4, 6)
text(110, 58, "PACE PE (re-created)", 17, weight="bold")
text(300, 58, "64b datapath · one configuration word per cycle · 1 of 8×8 array", 13, style="italic")

# ---------------------------------------------------------------- ROUTER
rect(150, 74, 590, 440, C_RT, "#000", 1.4, 4)
text(162, 94, "ROUTER", 14, weight="bold")
text(232, 94, "(single-cycle multi-hop, 6 sources × 7 sinks)", 12)

rows = [("N", 160), ("S", 220), ("W", 280), ("E", 340)]
for d, y in rows:
    line([(-55, y), (225, y)])
    text(-55, y - 6, f"{d}_in", 12, weight="bold")
    slash(120, y, 64)
    dot(225, y)
    line([(225, y), (225, y - 22), (262, y - 22)])
    ff(262, y - 38, 58, 32, f"R_{d}", "64b")
    line([(320, y - 22), (388, y - 22)])
    line([(225, y), (388, y)])
    mux(388, y - 34, 26, 44)
    line([(414, y - 12), (488, y - 12)], arrow=False)
    text(244, y + 15, f"we[{d}]", 9.5, fill=BLUE)
    text(372, y + 20, f"byp[{d}]", 9.5, "end", fill=BLUE)
text(-55, 384, "from N/S/W/E", 11, style="italic")
text(-55, 398, "neighbour PEs", 11, style="italic")
text(165, 470, "R_x: input (“parking”) registers, write-enable we[x];", 10, style="italic")
text(165, 484, "bypass mux selects register (byp=1) or live wire (byp=0).", 10, style="italic")

rect(468, 104, 250, 398, "#f4f9fe", "#000", 1.3)
text(600, 122, "CROSSBAR", 12.5, "middle", "bold")
text(600, 135, "7 × (6:1 + open) mux, 3b select each", 9.5, "middle")
add('<line x1="488" y1="142" x2="488" y2="492" stroke="#000" stroke-width="3"/>')
sinks = [("E_out", 160), ("S_out", 204), ("W_out", 248), ("N_out", 292),
         ("op1", 336), ("op2", 380), ("pred", 424)]
for name, y in sinks:
    line([(488, y + 14), (560, y + 14)], 1.4)
    slash(524, y + 14, 6, dy=-7)
    mux(560, y, 30, 28)
    text(596, y + 9, name, 11, weight="bold")
text(700, 494, "sel[20:0]", 10, "end", fill=BLUE)

for name, y in sinks[:4]:
    yy = y + 14
    line([(590, yy), (1460, yy)])
    slash(1300, yy, 64)
    text(1395, yy - 6, name, 12, weight="bold")
text(1395, 330, "to N/S/W/E", 11, style="italic")
text(1395, 344, "neighbour PEs", 11, style="italic")

rect(760, 104, 520, 36, "#fffbe6", "#b08900", 1, 3, "4 3")
text(770, 119, "Mesh outputs are combinational (not registered): N/S/W/E_in → *_out within the", 11)
text(770, 133, "same cycle, so one value can traverse several PEs per clock (HyCUBE / SMART bypass).", 11)

# ---------------------------------------------------------------- ALU datapath
rect(760, 326, 600, 238, C_ALU, "#000", 1.4, 4)
text(1348, 346, "ALU DATAPATH", 14, "end", "bold")
op1y, op2y, prdy = 350, 394, 438
line([(590, op1y), (790, op1y)])
mux(790, op1y - 22, 22, 40)
text(801, op1y + 32, "ld_v", 9.5, "middle", fill=BLUE)
line([(812, op1y - 2), (836, op1y - 2)])
ff(836, op1y - 19, 56, 34, "OP1", "64b")
line([(590, op2y), (836, op2y)])
ff(836, op2y - 17, 56, 34, "OP2", "64b")
line([(590, prdy), (720, prdy)], 1.2, dash="3 3")
text(724, prdy + 4, "rsvd", 9.5, style="italic")
line([(892, op2y), (930, op2y)])
mux(930, op2y - 25, 22, 44)
text(941, op2y + 33, "imm_v", 9.5, "middle", fill=BLUE)
rect(990, 356, 220, 166, "#fff", "#000", 1.4)
text(1100, 373, "EXECUTE", 12, "middle", "bold")
rect(1000, 380, 200, 72, "#fff7ee", "#000", 1)
text(1100, 395, "INT16 scalar", 11, "middle", "bold")
text(1100, 409, "ADD SUB MULT DIV LS RS ASR", 9.5, "middle")
text(1100, 421, "AND OR XOR SEL CMERGE", 9.5, "middle")
text(1100, 433, "CMP CLT CGT", 9.5, "middle")
text(1100, 446, "op1[15:0] ∘ (imm16 | op2[15:0])", 9, "middle", style="italic")
rect(1000, 458, 200, 58, "#fff7ee", "#000", 1)
text(1100, 472, "8 × FP8 E4M3 SIMD", 11, "middle", "bold")
for k in range(8):
    rect(1010 + 23 * k, 478, 19, 15, "#fff", "#000", 0.9)
    text(1019.5 + 23 * k, 489.5, str(k), 9, "middle")
text(1100, 509, "VADD  VMUL  ·  RNE  ·  flush-to-zero", 9.5, "middle")
line([(892, op1y - 2), (972, op1y - 2), (972, 404), (1000, 404)])
slash(940, op1y - 2, 64)
line([(952, op2y - 3), (980, op2y - 3), (980, 418), (1000, 418)], 1.4)
text(966, op2y - 9, "16", 9.5, "middle")
line([(902, op2y + 8), (902, op2y + 8)], arrow=False)
dot(912, op1y - 2)
line([(912, op1y - 2), (912, 486), (1000, 486)], 1.3)
dot(918, op2y)
line([(918, op2y), (918, 500), (1000, 500)], 1.3)
line([(1210, 440), (1262, 440)])
text(1236, 428, "alu_out", 10.5, "middle", weight="bold")
dot(1248, 440)
ff(1262, 423, 60, 34, "RES", "64b")
text(1292, 474, "upd_res", 9.5, "middle", fill=BLUE)

line([(1248, 440), (1248, 534), (478, 534), (478, 504)])
text(800, 529, "ALU_out (same cycle)", 10.5, weight="bold")
line([(1322, 440), (1345, 440), (1345, 550), (498, 550), (498, 504)])
text(1000, 545, "ALU_res (registered)", 10.5, weight="bold")

# ---------------------------------------------------------------- CONTROL
DY = 34
rect(150, 556 + DY, 820, 228, C_CTL, "#000", 1.4, 4)
text(162, 576 + DY, "CONTROL", 14, weight="bold")
rect(175, 590 + DY, 230, 180, C_MEM, "#000", 1.3)
text(290, 608 + DY, "CONFIG MEMORY", 12, "middle", "bold")
text(290, 622 + DY, "16 × 64b = 1 Kb (128 B)", 10.5, "middle")
for r in range(16):
    rect(200, 630 + DY + 8 * r, 170, 8, "#fff", "#555", 0.6)
text(196, 637 + DY, "0", 8.5, "end")
text(196, 757 + DY, "15", 8.5, "end")
line([(-55, 655 + DY), (198, 655 + DY)])
text(-55, 640 + DY, "host / QSPI loader", 10.5, style="italic")
text(-55, 672 + DY, "we, addr[3:0],", 10)
text(-55, 685 + DY, "wdata[63:0]", 10)
rect(450, 596 + DY, 210, 112, "#fff", "#000", 1.3)
text(555, 614 + DY, "PC / LOOP CTRL", 12, "middle", "bold")
ff(462, 624 + DY, 50, 32, "PC", "4b")
ff(522, 624 + DY, 62, 32, "L_start", "5b")
ff(592, 624 + DY, 58, 32, "L_end", "5b")
text(555, 674 + DY, "JUMP (first cycle): pc ← dst", 9.5, "middle")
text(555, 687 + DY, "pc ≥ end or pc < start: pc ← start", 9.5, "middle")
text(555, 700 + DY, "else: pc ← pc + 1", 9.5, "middle")
line([(462, 640 + DY), (372, 640 + DY)])
vslash(420, 640 + DY, 4)
text(426, 633 + DY, "addr", 9.5)
line([(370, 744 + DY), (720, 744 + DY)])
text(545, 738 + DY, "cfg[63:0]", 10.5, "middle", weight="bold")
slash(470, 744 + DY, 64)
rect(720, 596 + DY, 230, 176, "#fff", "#000", 1.3)
text(835, 614 + DY, "DECODER", 12, "middle", "bold")
dec = ["opcode[34:30]   imm16[50:35]", "imm_v[62]   upd_res[25]   AGU[59]",
       "switch sel[20:0] = 7 × 3b", "bypass[24:21]   we[29:26]",
       "JUMP: dst[49:45]  end[44:40]", "           start[39:35]",
       "reserved: [63] [61] [60]"]
for k, s_ in enumerate(dec):
    text(732, 634 + DY + 18 * k, s_, 10)
line([(720, 692 + DY), (662, 692 + DY)], 1.2, BLUE, "5 3")
text(691, 686 + DY, "jump", 9, "middle", fill=BLUE)
line([(800, 596 + DY), (800, 572), (660, 572), (660, 504)], 1.2, BLUE, "5 3")
text(666, 566, "sel 21b", 9.5, fill=BLUE)
line([(770, 596 + DY), (770, 580), (401, 580), (401, 352)], 1.2, BLUE, "5 3")
text(408, 574, "byp 4b · we 4b", 9.5, fill=BLUE)
line([(930, 596 + DY), (930, 576), (1100, 576), (1100, 524)], 1.2, BLUE, "5 3")
text(1108, 590, "opcode · imm16 · imm_v · upd_res", 9.5, fill=BLUE)

rect(1000, 600 + DY, 360, 170, "#fff", "#000", 1.2, 4, "6 4")
text(1012, 620 + DY, "MEMORY-PE SIDE BAND", 12, weight="bold")
text(1012, 635 + DY, "(edge columns 0 and 7 only, MEM_PE = 1)", 10, style="italic")
for s_, y in [("AGU trigger ← cfg[59]", 662), ("st_data ← OP1", 692), ("ld_data, ld_v → OP1 mux", 722)]:
    text(1012, y + DY + 4, s_, 11)
line([(1200, 662 + DY), (1460, 662 + DY)])
line([(1200, 692 + DY), (1460, 692 + DY)])
line([(1460, 722 + DY), (1222, 722 + DY)])
text(1395, 654 + DY, "to AGU", 10.5, style="italic")
text(1395, 714 + DY, "8 KB DMEM", 10.5, style="italic")
text(1012, 754 + DY, "2-cycle load latency is handled by AGU / DMEM", 10, style="italic")

# ---------------------------------------------------------------- configuration word
x0, y0, bw = 120, 880, 19.5
text(x0, y0 - 12, "Configuration word (64b, one per cycle)", 13, weight="bold")
fields = [(63, 63, "P", "#eee"), (62, 62, "I", C_ALU), (61, 61, "F", "#eee"), (60, 60, "B", "#eee"),
          (59, 59, "A", C_MEM), (58, 51, "unused", "#fff"), (50, 35, "imm16", C_ALU),
          (34, 30, "opcode", C_ALU), (29, 26, "we", C_RT), (25, 25, "U", C_ALU),
          (24, 21, "byp", C_RT), (20, 18, "pred", C_RT), (17, 15, "op2", C_RT),
          (14, 12, "op1", C_RT), (11, 9, "N", C_RT), (8, 6, "W", C_RT),
          (5, 3, "S", C_RT), (2, 0, "E", C_RT)]
for hi, lo, name, col in fields:
    x = x0 + (63 - hi) * bw
    w = (hi - lo + 1) * bw
    rect(x, y0, w, 28, col, "#000", 1)
    text(x + w / 2, y0 + 18, name, 11 if w > 30 else 10, "middle", "bold")
    text(x + 2, y0 + 40, str(hi), 8.5)
    if hi != lo:
        text(x + w - 2, y0 + 40, str(lo), 8.5, "end")
jx = x0 + (63 - 50) * bw
text(jx - 6, y0 + 67, "JUMP:", 10.5, "end", "bold")
for hi, lo, name in [(50, 50, "–"), (49, 45, "dst"), (44, 40, "end"), (39, 35, "start")]:
    x = x0 + (63 - hi) * bw
    w = (hi - lo + 1) * bw
    rect(x, y0 + 50, w, 24, C_CTL, "#000", 1)
    text(x + w / 2, y0 + 67, name, 10.5, "middle", "bold")
text(x0, y0 + 96, "P pred (rsvd) · I imm-valid · F use-float (rsvd) · B ALU-bypass (rsvd) · A AGU trigger · "
     "U update RES · switch codes: 0 E_in, 1 S_in, 2 W_in, 3 N_in, 4 ALU_out, 5 ALU_res, 7 open", 10.5)
add('</g>')
text(W / 2, H - 14, "Fig. 1. Re-created PACE processing element: 16 × 64b configuration memory with loop/PC controller, "
     "6 × 7 single-cycle multi-hop router with four parking registers, and 16b INT + 8 × FP8 SIMD ALU.",
     12.5, "middle", style="italic")
add("</svg>")
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "pace_pe_block_diagram.svg")
open(out, "w").write("\n".join(o))
print("wrote", out)
