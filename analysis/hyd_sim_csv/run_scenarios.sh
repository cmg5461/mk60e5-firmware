#!/bin/sh
# Regenerates the CSVs in this directory with tools/hyd_sim.py (volume unit 0.1 mm3, Cd 0.7, nu 10 cSt).
# ABS only: the USV is an always-open orifice (k_back 705, opening 80), there is no HSV; pump per tools/hyd_sim.py docstring.
cd "$(dirname "$0")/../.." || exit 1
S="python3 tools/hyd_sim.py --print-every 1"
O=analysis/hyd_sim_csv
$S --duration 1.2 --rate 100 --phases "0:build" --csv $O/apply_100barps.csv >/dev/null
$S --duration 0.3 --rate 1000 --pd-max 100 --phases "0:build" --csv $O/apply_1000barps_panic.csv >/dev/null
# release with the inlets open: wheel -> inlet -> node -> USV -> master
$S --duration 0.3 --pd0 100 --rate -1000 --phases "0:build" --csv $O/release_1000barps.csv >/dev/null
# dumps from 100 bar, driver held; the pump drains the LPA (share 0)
$S --duration 0.8 --pd0 100 --rate 0 --phases "0:dump:10" --csv $O/dump_full_from_100bar.csv >/dev/null
$S --duration 0.8 --pd0 100 --rate 0 --phases "0:dump:4" --csv $O/dump_level4_from_100bar.csv >/dev/null
# circuit coupling: FL dumps 0.10-0.14 s, driver held at 100 bar
C="--duration 0.5 --pd0 100 --rate 0 --fl 0:build,0.1:dump,0.14:hold --rl 0:hold --rr 0:hold"
$S $C --fr "0:build" --no-pump --csv $O/circuit_FLdump_FRopen_nopump.csv >/dev/null
$S $C --fr "0:build" --csv $O/circuit_FLdump_FRopen_pump.csv >/dev/null
$S $C --fr "0:hold" --csv $O/circuit_FLdump_FRhold_pump.csv >/dev/null
# FL dumps, holds, then reapplies; FR inlet open throughout; driver held at 100 bar
$S --duration 0.8 --pd0 100 --rate 0 --fl "0:build,0.1:dump,0.14:hold,0.3:build" \
   --fr "0:build" --rl 0:hold --rr 0:hold --csv $O/circuit_FL_dump_reapply.csv >/dev/null
# inlet level sweep (section 8.1 of HYDRAULIC_MODEL_7846816A.md): driver 60 bar, wheel 30 bar
python3 tools/hyd_sim.py --sweep-inlet --pd 60 --pw 30 > $O/inlet_sweep_front_60_30.txt
python3 tools/hyd_sim.py --sweep-inlet --pd 60 --pw 30 --curve-scale 0.5 > $O/inlet_sweep_front_60_30_mr2.txt
python3 tools/hyd_sim.py --sweep-inlet --pd 60 --pw 30 --axle rear --curve-scale 0.7 > $O/inlet_sweep_rear_60_30_mr2.txt
# discrete-level reapply ramp (section 8.2): 150 bar/s from 35 bar caliper, 70 bar driver; the CSV logs the commanded level
R="python3 tools/hyd_sim.py --ramp-inlet --pd 70 --pw 35 --ramp-rate 150"
$R --curve-scale 0.5 --csv $O/ramp150_front_mr2.csv > /dev/null
$R --curve-scale 1.0 --csv $O/ramp150_front_m3.csv > /dev/null
$R --curve-scale 0.5 --cmd-delay 1 --csv $O/ramp150_front_mr2_delay1.csv > /dev/null
$R --curve-scale 0.5 --controller firmware --csv $O/ramp150_front_mr2_fwrule.csv > /dev/null
