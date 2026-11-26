"""Programs for tb/tb_directed.sv (assembled with pace_asm)."""
import os, sys
sys.path.insert(0, os.path.dirname(__file__))
from pace_asm import word
B = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'build')
os.makedirs(B, exist_ok=True)
NOPW = word('NOP')
LOOP1 = word('JUMP', jdst=1, ls=1, le=1)          # word0: set a 1-entry loop at CM[1]


def dump(name, words):
    words = words + [NOPW] * (16 - len(words))
    with open(os.path.join(B, name), 'w') as f:
        f.writelines(f"{w:016x}\n" for w in words)


# --- Test 1: multi-hop. PE0 counts, PE1 is a pure pass-through, PE2 adds 100.
dump('t1_pe0.hex', [LOOP1, word('ADD', imm=1, upd=True, op1='ALURES', east='ALURES')])
dump('t1_pe1.hex', [LOOP1, word('NOP', east='W')])                 # W_in -> E_out, no register
dump('t1_pe2.hex', [LOOP1, word('ADD', imm=100, upd=True, op1='W', east='ALUOUT')])
# --- Test 2: FP8 x8 SIMD accumulate: res <- res + W_in (1.0 in every lane)
dump('t2_pe.hex',  [LOOP1, word('VADD', upd=True, op1='ALURES', op2='W')])
# --- Test 3: memory-PE side band: AGU trigger + store data + load return into op1
dump('t3_pe.hex',  [LOOP1, word('ADD', imm=1, upd=True, op1='ALURES', agu=True)])
# --- Test 4: parking register: latch N_in once, then reuse it from the register
dump('t4_pe.hex',  [word('NOP', we=('N',)),
                    word('JUMP', jdst=2, ls=2, le=2),
                    word('ADD', imm=0, upd=True, op1='N', bypass=('N',), south='N')])
print("directed programs written to", B)
