//! Golden-reference driver for the re-created PACE PE RTL.
//! Uses pace-sim's own `PE` and `FP8` types so the RTL is checked against
//! the lab's behavioural model, not against a re-implementation.
//!
//!   pace-pe-golden fp8  <out.txt>
//!       all 65536 (a,b) pairs: "aa bb add mul" (hex)
//!   pace-pe-golden pe   <prog.hex> <inputs.hex> <trace.txt>
//!       prog.hex  : 16 lines, one 64-bit configuration word each
//!       inputs.hex: one line per cycle: "N S W E" 64-bit hex words
//!       trace.txt : per cycle "pc alu outN outS outW outE op1 op2 res qN qS qW qE ls le"
use pace_sim::isa::{
    binary::binary::BinaryIO,
    configuration::{Configuration, Program},
    fp8::FP8,
    operation::OpCode,
    pe::PE,
};
use std::io::Write;

fn hex64(s: &str) -> u64 {
    u64::from_str_radix(s.trim(), 16).expect("bad hex")
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    match args.get(1).map(|s| s.as_str()) {
        Some("fp8") => {
            let mut f = std::io::BufWriter::new(std::fs::File::create(&args[2]).unwrap());
            for a in 0u16..256 {
                for b in 0u16..256 {
                    let fa = FP8::from(a as u8);
                    let fb = FP8::from(b as u8);
                    let s: u8 = (fa + fb).into();
                    let m: u8 = (fa * fb).into();
                    writeln!(f, "{:02x} {:02x} {:02x} {:02x}", a, b, s, m).unwrap();
                }
            }
        }
        Some("pe") => {
            let prog_txt = std::fs::read_to_string(&args[2]).unwrap();
            let confs: Vec<Configuration> = prog_txt
                .lines()
                .filter(|l| !l.trim().is_empty())
                .map(|l| Configuration::from_binary(&hex64(l).to_le_bytes().to_vec()).unwrap())
                .collect();
            assert_eq!(confs.len(), 16, "program must have 16 words");
            let mut pe = PE::new(Program { configurations: confs });
            let inputs = std::fs::read_to_string(&args[3]).unwrap();
            let mut out = std::io::BufWriter::new(std::fs::File::create(&args[4]).unwrap());
            for (cyc, line) in inputs.lines().filter(|l| !l.trim().is_empty()).enumerate() {
                let w: Vec<u64> = line.split_whitespace().map(hex64).collect();
                let conf = pe.current_conf().clone();
                let pc = pe.pc;
                pe.signals.wire_north_in = Some(w[0]);
                pe.signals.wire_south_in = Some(w[1]);
                pe.signals.wire_west_in = Some(w[2]);
                pe.signals.wire_east_in = Some(w[3]);
                let op = conf.operation;
                // pace-sim panics on x/0; the RTL defines x/0 := 0xFFFF.
                let divisor = op.immediate.unwrap_or(pe.regs.reg_op2 as u16);
                if op.op_code == OpCode::DIV && divisor == 0 {
                    pe.signals.wire_alu_out = Some(0xFFFF);
                } else {
                    pe.update_alu_out();
                }
                pe.update_router_output()
                    .unwrap_or_else(|e| panic!("cycle {cyc}: router: {e}"));
                let s = pe.signals;
                pe.update_registers(None)
                    .unwrap_or_else(|e| panic!("cycle {cyc}: regs: {e}"));
                let r = pe.regs;
                writeln!(
                    out,
                    "{:x} {:016x} {:016x} {:016x} {:016x} {:016x} {:016x} {:016x} {:016x} {:016x} {:016x} {:016x} {:016x} {:x} {:x}",
                    pc,
                    s.wire_alu_out.unwrap_or(0),
                    s.wire_north_out.unwrap_or(0),
                    s.wire_south_out.unwrap_or(0),
                    s.wire_west_out.unwrap_or(0),
                    s.wire_east_out.unwrap_or(0),
                    r.reg_op1, r.reg_op2, r.reg_res,
                    r.reg_north_in, r.reg_south_in, r.reg_west_in, r.reg_east_in,
                    r.reg_loop_start, r.reg_loop_end
                )
                .unwrap();
                pe.next_conf();
            }
        }
        _ => eprintln!("usage: pace-pe-golden fp8 <out> | pe <prog> <inputs> <trace>"),
    }
}
