"""Generate a TunerPro XDF for the MK60E5 E9x M3 application image (7846816A).

Load against flash/bin/7846816A_00000000.bin (1 MiB, file offset = .0pa address).
Addresses below are CPU addresses; XDF addresses = CPU + APP_OFFSET (0x8000).

Usage:  python tools/make_xdf_m3.py flash/bin/7846816A_00000000.bin -o xdf/MK60E5_7846816A.xdf

Reuses the Xdf emitter from make_xdf.py. Data is byte-verified against the M3 image
(see FACTS.md "M3" entries and analysis/agents/m3*/). The vehicle-model table and the
ABS/TCS slip/decel targets are the verified payload of cycle 1; CAN/KWP sections are
filled dynamically from the M3 tables (addresses confirmed by the interface-surface agent).
"""
import argparse
import pathlib
import struct
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from make_xdf import Xdf, APP_OFFSET, OUT_HEX, OUT_INT, OUT_FLOAT  # noqa: E402

VBR = 0x40000
CAL_DIR = 0x40300
ABS = 0x4039C  # M3 ABS calibration block base
TCS = 0x40FBC  # M3 TCS calibration block base
# M3 external-interface tables (byte-verified; 1M analogues in make_xdf.py).
CAN_HDR, CAN_MSG, CAN_MSG_SIZE = 0xD7F45, 0xD7F65, 23
CAN_SIG_SIZE, CAN_VAR, CAN_VAR_SIZE = 5, 0xD88C0, 8
KWP_SERVICES, KWP_SERVICE_SIZE = 0xF30A0, 12
FCAN_HDR, FCAN_MSG = 0xF59C3, 0xF59DD  # M3 F-CAN (14 TX / 18 RX, 23-byte records)

VECTOR_NAMES = {0: "reset (0x6C906)", 1: "misaligned", 2: "access error", 3: "divide by zero",
                4: "illegal", 5: "privilege", 6: "trace", 7: "breakpoint", 8: "unrecoverable",
                9: "soft reset", 10: "INT autovector", 11: "FINT autovector", 12: "HW accelerator",
                16: "trap 0", 17: "trap 1", 18: "trap 2", 19: "trap 3",
                56: "WSS edge ch3 (D8 +9E)", 57: "WSS edge ch1 (F8 +9E)",
                58: "WSS edge ch2 (D8 +8E)", 59: "WSS edge ch0 (F8 +8E)"}

# 12-variant coding labels. Data shows variants 0..4 == 5..9; 10/11 are unique.
VAR_LABELS = [f"var{i}" + (" (=var%d)" % (i - 5) if 5 <= i <= 9 else "") for i in range(12)]


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image")
    ap.add_argument("-o", "--out", type=pathlib.Path, required=True)
    args = ap.parse_args()
    data = open(args.image, "rb").read()

    def b(cpu, n=1):
        o = cpu + APP_OFFSET
        return data[o:o + n]

    def u16(cpu):
        return struct.unpack(">H", b(cpu, 2))[0]

    def u32(cpu):
        return struct.unpack(">I", b(cpu, 4))[0]

    def s16(cpu):
        return struct.unpack(">h", b(cpu, 2))[0]

    x = Xdf()
    c_info = x.category("Info / vectors")
    c_veh = x.category("Vehicle model (coding-variant)")
    c_slip = x.category("ABS/TCS slip & decel targets")
    c_ayc = x.category("AYC / yaw control & DSC mode")
    c_wss = x.category("Wheel speed (BFU/VMO)")
    c_tx = x.category("CAN TX messages")
    c_rx = x.category("CAN RX messages")
    c_sig = x.category("CAN signals")
    c_var = x.category("CAN variables")
    c_diag = x.category("Diagnostics (KWP2000)")
    c_fcan = x.category("F-CAN messages")
    c_csi = x.category("CSI / steering")
    c_brake = x.category("Brake coding (COA/BCO)")
    c_dds = x.category("DDS / RPA")
    c_lvc = x.category("LVC")
    c_fault = x.category("Fault ids")
    c_os = x.category("OS / scheduler / ROM self-test")
    c_tcs = x.category("TCS controller (block 0x40FBC)")
    c_act = x.category("Hydraulic actuation")
    c_pm = x.category("Pressure/volume model (COA)")
    c_misc = x.category("Misc blocks (CSW/FSF)")
    c_cal = x.category("Calibration blocks (raw)")

    # ---- Vector table -------------------------------------------------------
    labels = [f"{i:3d} {VECTOR_NAMES.get(i, 'irq' if i >= 32 else 'reserved')}" for i in range(128)]
    x.column(c_info, "Vector table (handler address, bit0 = alt reg file)", VBR, 32, 128, 4, labels,
             desc="M-CORE vector table at VBR=0x40000. CPU addresses. Reset handler 0x6C906 (M3).",
             out=OUT_HEX)

    # ---- Vehicle-model variant table ---------------------------------------
    # 12 s16 per parameter, indexed by EEPROM coding variant (0x4031AA+1, 0..11).
    # Loaders: VehModel_LoadSingleTrackCoeffs 0x5DE44, VehModel_LoadAxleDerived 0x5E424.
    vn = ("M3 single-track (bicycle) model parameter, one value per 5-bit coding variant "
          "(EEPROM 0x4031AA+1, read via 0x8E066(24,1); not in flash). row[v] = base + 2*v. "
          "Loaded into RAM 0x400AA4.. by 0x5DE44/0x5E424. ")
    vrow = dict(rows=12, stride_bytes=2, labels=VAR_LABELS, signed=True)
    x.column(c_veh, "l_f  front axle -> CG", 0xD6F42, 16, units="m", eq="X/1024", decimals=4,
             desc=vn + "Q10 m. l_f+l_r = 2826/2827 (=2.760 m, E9x wheelbase). Verified.", **vrow)
    x.column(c_veh, "l_r  CG -> rear axle", 0xD6F5A, 16, units="m", eq="X/1024", decimals=4,
             desc=vn + "Q10 m. Verified.", **vrow)
    x.column(c_veh, "mass", 0xD6F72, 16, units="kg", desc=vn + "kg (1674..1947). Verified.", **vrow)
    x.column(c_veh, "Jz  yaw inertia", 0xD6F8A, 16, units="kg*m^2",
             desc=vn + "kg*m^2 (Jz/m ~ l_f*l_r confirms units). Verified.", **vrow)
    x.column(c_veh, "Cf  front cornering stiffness", 0xD6ECA, 16,
             desc=vn + "Role from loader 0x5E424 (Cr*l_r - Cf*l_f understeer term). UNITS TBD "
                       "(N/deg vs N/rad unresolved). Verified bytes.", **vrow)
    x.column(c_veh, "Cr  rear cornering stiffness", 0xD6EE2, 16,
             desc=vn + "Cr>Cf every variant (understeer). UNITS TBD. Verified bytes.", **vrow)
    x.column(c_veh, "track width front", 0xD6FA2, 16, units="m", eq="X/1024", decimals=3,
             desc=vn + "Q10 m (1575/1024 = 1.538 m = M3 front track). NOT mm (corrected cycle 7).", **vrow)
    x.column(c_veh, "track width rear", 0xD6FBA, 16, units="m", eq="X/1024", decimals=3,
             desc=vn + "Q10 m (1573/1024 = 1.536 m).", **vrow)
    x.column(c_veh, "override-enable flag", 0xD7032, 16, out=OUT_HEX,
             desc=vn + "Per-variant gate for the 0xD6E3A.. override rows; 0 for all 12 (rows dead "
                       "on this ROM). Verified.", **vrow)
    # Low-confidence override / aux rows, exposed for completeness.
    for addr, title in ((0xD6E3A, "override A front"), (0xD6E52, "override A rear"),
                        (0xD6E6A, "override B front"), (0xD6E82, "override B rear"),
                        (0xD6E9A, "override C front"), (0xD6EB2, "override C rear"),
                        (0xD6EFA, "aux const (532)"), (0xD6F12, "aux const (446)"),
                        (0xD6F2A, "l_f offset (-1204)")):
        x.column(c_veh, title, addr, 16, desc=vn + "Low confidence; role unverified.", **vrow)

    # ---- ABS/TCS slip & deceleration targets -------------------------------
    # Variant m = EEPROM 0x4031AA+1 (0..11); TCS mode = 0x4031AA+7 (0..2).
    def curve_fields(cat, base, title, note, xunits="km/h", xeq="X/100", xdec=2,
                     cunits="", ceq="X", cdec=0):
        """Emit breakpoints / intercepts / slopes columns of a piecewise-linear curve.
        Record: s16 lo, hi, n; x[n-1]; c[n] intercepts; k[n] slopes (Q10)."""
        n = s16(base + 4)
        xb, cb, kb = base + 6, base + 6 + 2 * (n - 1), base + 6 + 2 * (n - 1) + 2 * n
        x.constant(cat, f"{title}: clamp min", base, 16, signed=True, units=cunits, eq=ceq,
                   decimals=cdec, desc=note + "Lower output clamp.")
        x.constant(cat, f"{title}: clamp max", base + 2, 16, signed=True, units=cunits, eq=ceq,
                   decimals=cdec, desc=note + "Upper output clamp.")
        if n > 1:
            x.column(cat, f"{title}: breakpoints (x)", xb, 16, n - 1, 2, [f"x{i}" for i in range(n - 1)],
                     signed=True, units=xunits, eq=xeq, decimals=xdec, desc=note + "Axis breakpoints.")
        x.column(cat, f"{title}: intercepts (c)", cb, 16, n, 2, [f"c{i}" for i in range(n)],
                 signed=True, units=cunits, eq=ceq, decimals=cdec, desc=note + "Per-segment intercept.")
        x.column(cat, f"{title}: slopes (k, Q10)", kb, 16, n, 2, [f"k{i}" for i in range(n)],
                 signed=True, eq="X/1024", decimals=4, desc=note + "Per-segment slope, y += x*k/1024.")

    # ABS entry/continue slip threshold vs vref (0x40DB6; reader 0x710FC, sites 0x54F4A/55062/552DA).
    curve_fields(c_slip, 0x40DB6, "ABS entry-slip threshold",
                 "ABS entry/continue slip target vs vref (fn abs_entry_slip_eval). slip = vref - wheel "
                 "speed; threshold ~1.3-2.0 km/h. x=vref. Units 0.01 km/h. Verified. ")
    x.constant(c_slip, "ABS entry debounce count", 0x40DB4, 16, signed=True,
               desc="Compared with the u8 counter 0x408EF0 (debounce). Stock 2. med.")

    # ABS deceleration-threshold scalars (addresses verified; unit ~0.01 g UNPROVEN).
    gnote = "ABS deceleration-threshold input (builder fn not yet located). Unit ~0.01 g unproven; signed. "
    x.constant(c_slip, "ABS accel gain front", ABS + 0x27E, 16, signed=True, desc=gnote + "Stock 40.")
    x.constant(c_slip, "ABS accel gain rear", ABS + 0x280, 16, signed=True, desc=gnote + "Stock 25.")
    x.constant(c_slip, "ABS decel floor", ABS + 0x282, 16, signed=True, desc=gnote + "Stock -240.")
    x.constant(c_slip, "ABS decel base", ABS + 0x284, 16, signed=True, desc=gnote + "Stock -116.")
    x.column(c_slip, "ABS decel floor <20 km/h (per variant)", ABS + 0x2A8, 16, 12, 2, VAR_LABELS,
             signed=True, desc=gnote + "Stock -127 (var0) then -120. Variant = 0x4031AA+1.")
    x.column(c_slip, "ABS decel floor <60 km/h (per variant)", ABS + 0x2C0, 16, 12, 2, VAR_LABELS,
             signed=True, desc=gnote + "Stock -132 (var0-9), -140 (var10/11, permissive).")
    x.column(c_slip, "ABS decel ladder", ABS + 0x76C, 16, 6, 2, [f"s{i}" for i in range(6)],
             signed=True, desc=gnote + "Stock -140,-90,-40,-210,-350,-490. Grouping unverified.")
    x.column(c_slip, "ABS staged threshold set A", ABS + 0xAC2, 16, 3, 2, ["s1", "s2", "s3"],
             signed=True, desc=gnote + "Stock -62,-78,-94.")
    x.column(c_slip, "ABS staged threshold set B", ABS + 0xB02, 16, 3, 2, ["s1", "s2", "s3"],
             signed=True, desc=gnote + "Stock -25,-44,-62.")

    # ABS speed-term and g-term curve families (12 variant copies + single rear term).
    # Variants 0-9 identical; 10/11 differ (more permissive at high speed).
    for m in range(12):
        curve_fields(c_slip, 0x40412 + 0x28 * m, f"ABS front speed-term curve [var{m}]",
                     f"ABS front decel speed-term, coding variant {m}. x=vref 0.01 km/h; output "
                     "subtracted from base. Variants 0-9 identical; 10/11 permissive. ",
                     cunits="", ceq="X", cdec=0)
    curve_fields(c_slip, 0x405F2, "ABS rear speed-term curve (single)",
                 "ABS rear decel speed-term (one copy, all variants). x=vref 0.01 km/h. ")
    for m in range(12):
        curve_fields(c_slip, 0x40674 + 0x40 * m, f"ABS g-term curve [var{m}]",
                     f"ABS decel g-term, coding variant {m}. x axis likely 0.01 g. Variants 0-9 "
                     "identical; 10/11 differ. ", xunits="", xeq="X", xdec=0)

    # TCS base drive-slip threshold, set A/B x mode (0..2). Default = set B; set A when 0x402F6C bit4.
    tnote = ("M3 TCS base DRIVE-SLIP threshold = allowed rear-minus-front speed (0.01 km/h). x=vref "
             "(0x403066, min of fronts). mode = 0x4031AA+7 (0..2). Relocated to const ROM. Verified. ")
    for mode in range(3):
        curve_fields(c_slip, 0xF625C + 0x22 * mode, f"TCS drive-slip set B mode {mode} (default)",
                     tnote + "Set B used unless 0x402F6C bit4. ")
    for mode in range(3):
        curve_fields(c_slip, 0xF61F6 + 0x22 * mode, f"TCS drive-slip set A mode {mode}",
                     tnote + "Set A used when 0x402F6C bit4 set. ")
    # TCS caps (6 rows at 0xF654C + 0x22*j; reader 0xCB576 divides by 20).
    for j in range(6):
        curve_fields(c_slip, 0xF654C + 0x22 * j, f"TCS cap curve {j}",
                     f"TCS cap curve {j} (fn tcs_cap_eval 0xCB576; output /20). x=vref. "
                     "Mode index 0..2 selects rows 0-2; rows 3-5 second stage. Units med. ",
                     cunits="", ceq="X/20", cdec=1)

    # ---- ABS control tunables (cycle 2; byte-verified) ---------------------
    pnote = "ABS pressure-control constant. Pressure unit ~0.01 bar (unproven). "
    x.constant(c_slip, "ABS apply ramp per cycle", 0x403A8, 16, signed=True,
               desc=pnote + "Pressure-level apply ramp (abs_apply_ramp 0x443F4). Stock 400.")
    x.column(c_slip, "ABS dump reduction stages", 0x40E64, 16, 3, 2, ["s1", "s2", "s3"], signed=True,
             desc=pnote + "Pressure reduction per dump stage (abs_dump_stage 0x5424C). Stock 1000/1500/2000.")
    x.constant(c_slip, "ABS reapply nudge", 0x40D90, 16, signed=True, desc=pnote + "Stock 80.")
    x.constant(c_slip, "ABS decel set A enable", 0x40E94, 16, desc="1 = staged set A active. Stock 1.")
    x.constant(c_slip, "ABS decel set B enable", 0x40E9C, 16, desc="1 = staged set B active. Stock 1.")
    x.column(c_slip, "ABS cornering limit scalars", 0x40DCE, 16, 3, 2, ["a", "b", "c"], signed=True,
             desc="ABS+0x58E.. cornering limits. Stock 126/8/1748.")

    # ---- AYC / yaw control & DSC mode (cycle 2; byte-verified) -------------
    # AYC block base 0x41190. DSC mode m in {0,1,2} = RAM 0x4031B1 (= coding 0x4031AA+7).
    # m=1 is the most permissive (largest torque ceiling); m=2 tightest. Yaw units not decoded.
    MODE = ["m0 (restricted)", "m1 (most permissive)", "m2 (tightest)"]
    M4 = [f"{m}:p{p}" for m in ("m0", "m1", "m2") for p in range(4)]  # 3 modes x 4 points
    anote = ("AYC yaw-intervention calibration. target B1A 0x400B1A, measured B46 (F-CAN 0x0CD); "
             "entry |yaw err|>B6C. DSC mode 0x4031B1 selects the per-mode column. "
             "Yaw-rate LSB = 0.0028648 deg/s/count (1/20000 rad/s). ")
    x.constant(c_ayc, "AYC entry threshold base, set A", 0x413BA, 16, signed=True,
               desc=anote + "B6C = base * speed-factor/128. Stock 1396 = 4.00 deg/s yaw error.")
    x.constant(c_ayc, "AYC entry threshold base, set B", 0x413BC, 16, signed=True,
               desc=anote + "Stock 2792 = 8.00 deg/s.")
    x.column(c_ayc, "AYC hold seed (A, B)", 0x413BE, 16, 2, 2, ["set A", "set B"], signed=True,
             desc=anote + "Initial B70 hold seeds. Stock 698/2094.")
    x.column(c_ayc, "AYC hold offset per mode (B6C-B70)", 0x4141E, 16, 3, 2, MODE, signed=True,
             desc=anote + "Hold = entry - this. Stock 698/698/698.")
    x.column(c_ayc, "AYC entry ceiling per mode (B6C max)", 0x41424, 16, 3, 2, MODE, signed=True,
             desc=anote + "Entry-threshold clamp. Stock 10471/10471/8028 = 30.0/30.0/23.0 deg/s (m2 tightest).")
    x.column(c_ayc, "AYC hold ceiling per mode (B70 max)", 0x4142A, 16, 3, 2, MODE, signed=True,
             desc=anote + "Stock 9773/9773/7330.")
    x.column(c_ayc, "AYC threshold speed-factor set A x (mode x 4pt)", 0x41478, 16, 12, 2, M4,
             signed=True, units="km/h", eq="X/100", decimals=2, desc=anote + "Breakpoints for the factor curve.")
    x.column(c_ayc, "AYC threshold speed-factor set A y (mode x 4pt)", 0x41490, 16, 12, 2, M4,
             signed=True, eq="X/128", decimals=3, desc=anote + "Factor (128=1.0). Stock m0/m1 320..128.")
    x.column(c_ayc, "AYC threshold speed-factor set B x (mode x 4pt)", 0x414D8, 16, 12, 2, M4,
             signed=True, units="km/h", eq="X/100", decimals=2, desc=anote)
    x.column(c_ayc, "AYC threshold speed-factor set B y (mode x 4pt)", 0x414F0, 16, 12, 2, M4,
             signed=True, eq="X/128", decimals=3, desc=anote)
    x.column(c_ayc, "AYC P-gain base (B76, B78)", 0x413AA, 16, 2, 2, ["B76", "B78"], signed=True,
             desc=anote + "P/D gain base. Stock 47/47 (second set 36/36 at 0x413AE).")
    x.column(c_ayc, "AYC P-gain % set A x (mode x 4pt)", 0x41448, 16, 12, 2, M4, signed=True,
             units="km/h", eq="X/100", decimals=2, desc=anote + "P-gain percent curve breakpoints.")
    x.column(c_ayc, "AYC P-gain % set A y (mode x 4pt)", 0x41460, 16, 12, 2, M4, signed=True, units="%",
             desc=anote + "P-gain percent. Stock m0/m1 30/60/70/100, m2 70/80/100/100.")
    x.column(c_ayc, "AYC P-gain % mult #2 (mode x 4pt)", 0x41430, 16, 12, 2, M4, signed=True, units="%",
             desc=anote + "Second percent multiplier. Stock m0/m1 80/80/90/100.")
    x.column(c_ayc, "AYC torque ceiling x per mode (@ lat accel)", 0x411FE, 16, 6, 2,
             [f"{m}:{p}" for m in ("m0", "m1", "m2") for p in ("x0", "x1")], signed=True,
             desc=anote + "2-pt breakpoints (stock 50/80).")
    x.column(c_ayc, "AYC torque ceiling y per mode", 0x4120A, 16, 6, 2,
             [f"{m}:{p}" for m in ("m0", "m1", "m2") for p in ("@lo", "@hi")], signed=True,
             desc=anote + "Engine-torque-reduction ceiling. Stock m0 150/400, m1 200/2000, m2 180/330. "
                          "**m1 ceiling 2000 is where M-mode permissiveness lives.**")
    x.column(c_ayc, "AYC torque scale % per mode", 0x41216, 16, 3, 2, MODE, signed=True, units="%",
             desc=anote + "Stock 78/78/78.")
    x.column(c_ayc, "AYC feature-enable per mode", 0xD6DA4, 16, 3, 2, MODE,
             desc=anote + "Relocated outside the block. Stock 1/0/0 (m0 only).")
    x.column(c_ayc, "AYC observer per-variant scalar 1", 0x415F8, 16, 12, 2, VAR_LABELS, signed=True,
             desc=anote + "yaw_observer per coding-variant. Stock 1835 (all).")
    x.column(c_ayc, "AYC observer per-variant scalar 2", 0x41610, 16, 12, 2, VAR_LABELS, signed=True,
             desc=anote + "Stock 90 (all).")
    x.column(c_ayc, "AYC observer per-variant scalar 3", 0x41628, 16, 12, 2, VAR_LABELS, signed=True,
             desc=anote + "μ-dependent α_lim term. Stock 11905, except variants 1/6 = 17854.")
    # AYC yaw-moment → wheel distribution (cycle 7; byte-verified)
    dnote = ("AYC brake-moment distribution (ayc_moment_to_wheel_pressure 0x616A4). Oversteer brakes the outer "
             "FRONT; understeer the same-side REAR. Pressure ~0.1 bar / moment-count. ")
    x.constant(c_ayc, "AYC dist: understeer rear-share X (/256)", 0x4155E, 16, signed=True,
               desc=dnote + "Mode 3: rear gets X/256, front (256−X)/256. Stock 256 = rear-only.")
    x.constant(c_ayc, "AYC dist: mode-1 rear gain (/256)", 0x413C4, 16, signed=True,
               desc=dnote + "Low-yaw mode 1 secondary (rear) gain. Stock 64 (0.25); rear pressure doubled.")
    x.column(c_ayc, "AYC wheel-request rate cap (A, B)", 0x41552, 16, 2, 2, ["A", "B"], signed=True,
             desc=dnote + "Rate caps for the id-3 brake request. Stock 300/500.")
    x.constant(c_ayc, "AYC front-outer pre-fill (id 20)", 0x411B4, 16, signed=True, units="bar", eq="X/100",
               decimals=2, desc=dnote + "Stand-by pressure on the front outer wheel while armed. Stock 500 = 5 bar.")
    x.constant(c_ayc, "AYC driver-pressure gate %", 0x415E8, 16, signed=True, units="%",
               desc=dnote + "Driver brake pressure above this % enables the driver-braking distribution branch. Stock 60.")
    V4 = [f"v{v}:p{p}" for v in range(12) for p in range(4)]
    x.column(c_ayc, "AYC observer lag-blend x (variant x 4pt)", 0xD70AA, 16, 48, 2, V4, signed=True,
             units="km/h", eq="X/100", decimals=2,
             desc="yaw_observer 0x5EBC4 front slip-angle lag curve, speed axis. Variants 10/11 differ from 0-9.")
    x.column(c_ayc, "AYC observer lag-blend y (variant x 4pt, Q13)", 0xD704A, 16, 48, 2, V4, signed=True,
             eq="X/8192", decimals=4, desc="Weight on the old state (Q13). Stock v0-9 = 7229/6560/5200/3014.")

    # ---- Wheel speed: BFU + VMO + direction (cycle 2; byte-verified) -------
    bfu = "BFU block 0x41CE4. Geometry identical to the 1M. "
    x.constant(c_wss, "WSS standstill threshold", 0x41CF2, 16, signed=True, units="km/h", eq="X/100",
               decimals=2, desc=bfu + "Below this = standstill. Stock 72 = 0.72 km/h.")
    x.constant(c_wss, "WSS circumference front", 0x41CF4, 16, units="mm", desc=bfu + "Wheels 0/1. Stock 2073.")
    x.constant(c_wss, "WSS circumference rear", 0x41CF6, 16, units="mm", desc=bfu + "Wheels 2/3. Stock 2073.")
    x.constant(c_wss, "WSS tooth count front", 0x41CF8, 16, desc=bfu + "Stock 48.")
    x.constant(c_wss, "WSS tooth count rear", 0x41CFA, 16, desc=bfu + "Stock 48.")
    x.column(c_wss, "Direction invert mask (coding bit 0/1)", 0xD766C, 8, 2, 1,
             ["0x4031F4 bit8 = 0", "bit8 = 1"], out=OUT_HEX,
             desc="Per-wheel bit: invert the ASIC direction bit. Stock 05/09.")
    x.column(c_wss, "VMO monitor scalars (raw, partial decode)", 0x42430, 16, 30, 2,
             [f"+0x{0x0C + 2 * i:02X}" for i in range(30)], out=OUT_HEX,
             desc="VMO wheel-speed plausibility/timing monitor 0x42424. Fields mostly undecoded; "
                  "0x42430 window threshold 2000, 0x42466/68 percent scales 85/75.")
    # ---- Sensor-mode toggle: the sub_075A44 return constant (CODE byte) ------
    # This is a code patch, NOT a calibration field: sub_075A44 hard-returns the
    # per-wheel sensor mode. The dispatcher sub_075E38 branches 3 ways on it:
    #   mode 4 (0x6043) = VDA encoded active sensor (ASIC reply word, popcount>=3)
    #   mode 2 (0x6023) = raw edge/pulse presence (0x40339E period pair, [6..25])
    #   anything else   = immediate WSS fault latch 0x400952[w]|=0x31
    # The halfword at CPU 0x75A56 is `movi r3,<imm>`; big-endian 0x6043 -> 0x6023.
    # Editing it REQUIRES re-signing the image: tools/bmy_resign.py fix.
    # Displayed as the BMW mode NUMBER (4 or 2), not raw hex, so it is pick-friendly.
    # The stored halfword is `movi r3,imm` = 0x6000 | (imm<<4) | 3 = 24579 + 16*mode.
    # Equation (X-24579)/16 shows 4 for stock 0x6043 and 2 for 0x6023; TunerPro inverts
    # it on write, so typing 4/2 rebuilds the full opcode (0x6 nibble + r3) automatically
    # and the register/opcode bits can never be clobbered. Only 4 and 2 are valid modes.
    x.constant(c_wss, "Wheel-speed sensor MODE  [enter 4=VDA stock / 2=edge-pulse] CODE+RESIGN",
               0x75A56, 16, out=OUT_INT, eq="(X-24579)/16", units="mode",
               desc="Sensor acquisition mode returned by sub_075A44 for ALL 4 wheels. ENTER 4 or 2 ONLY. "
                    "4 = VDA encoded active sensor (stock; presence via ASIC reply popcount>=3). "
                    "2 = raw edge/pulse presence from the eTPU capture path 0x40339E (plausible if period "
                    "diff in [6..25]). Any other number -> every wheel latches a WSS DTC at cycle 100. "
                    "This edits CODE (movi r3,imm at CPU 0x75A56 / file 0x7DA56), so you MUST re-sign the "
                    "image afterward: python tools/bmy_resign.py fix. Mode 2 keeps its own plausibility "
                    "window + confidence counters -> bench-verify before relying on it.")

    # ---- CAN configuration (dynamic walk of the M3 tables) -----------------
    n_tx, n_rx = b(CAN_HDR + 0x10)[0], b(CAN_HDR + 0x11)[0]
    sig_tab = CAN_HDR + 0x0D + u16(CAN_HDR + 0x0C)  # 0xD839E on the M3
    msg_ids = [u16(CAN_MSG + CAN_MSG_SIZE * i + 2) for i in range(n_tx + n_rx)]
    for cat, first, count, tag in ((c_tx, 0, n_tx, "TX"), (c_rx, n_tx, n_rx, "RX")):
        base = CAN_MSG + CAN_MSG_SIZE * first
        lab = [f"0x{msg_ids[first + i]:03X}" for i in range(count)]
        common = dict(rows=count, stride_bytes=CAN_MSG_SIZE, labels=lab)
        x.column(cat, f"{tag} CAN id", base + 2, 16, out=OUT_HEX, desc="11-bit identifier", **common)
        x.column(cat, f"{tag} flags|DLC", base + 4, 8, out=OUT_HEX,
                 desc="High nibble = flags, low nibble = DLC", **common)
        x.column(cat, f"{tag} period", base + 6, 8, units="ms", eq="X*10",
                 desc="Cycle time in 10 ms units; 255 (2550) = event / no timeout", **common)
        x.column(cat, f"{tag} signal count", base + 10, 8, **common)
        x.column(cat, f"{tag} first signal", base + 11, 16, **common)
        x.column(cat, f"{tag} mailbox", base + 13, 8, desc="Hardware message buffer 0-31", **common)

    owner = {}
    for i, cid in enumerate(msg_ids):
        m = CAN_MSG + CAN_MSG_SIZE * i
        n, f = b(m + 10)[0], u16(m + 11)
        for s in range(f, f + n):
            owner[s] = f"{'TX' if i < n_tx else 'RX'} 0x{cid:03X}"
    n_sig = max(owner) + 1
    lab = [f"{s:3d} {owner.get(s, '?')}" for s in range(n_sig)]
    common = dict(rows=n_sig, stride_bytes=CAN_SIG_SIZE, labels=lab)
    x.column(c_sig, "Signal flags|bit length", sig_tab, 8, out=OUT_HEX,
             desc="Low 5 bits = length in bits, top 3 bits = flags", **common)
    x.column(c_sig, "Signal position", sig_tab + 1, 8, out=OUT_HEX,
             desc="Low nibble = start byte, high nibble = start bit", **common)
    x.column(c_sig, "Signal variable id", sig_tab + 3, 16, out=OUT_HEX, **common)

    n_var = max(u16(sig_tab + CAN_SIG_SIZE * s + 3) for s in range(n_sig)) + 1
    lab = [f"0x{v:03X}" for v in range(n_var)]
    common = dict(rows=n_var, stride_bytes=CAN_VAR_SIZE, labels=lab)
    x.column(c_var, "Variable type", CAN_VAR, 8, desc="Low 3 bits: 2/4 = special handling", **common)
    x.column(c_var, "Variable default", CAN_VAR + 1, 8, out=OUT_HEX, **common)
    x.column(c_var, "Variable callback", CAN_VAR + 4, 32, out=OUT_HEX,
             desc="Getter (TX) / setter (RX) function, CPU address", **common)

    # ---- Diagnostics (KWP2000 service dispatch) ----------------------------
    n_srv = 23
    lab = [f"SID 0x{b(KWP_SERVICES + KWP_SERVICE_SIZE * i)[0]:02X}" for i in range(n_srv)]
    common = dict(rows=n_srv, stride_bytes=KWP_SERVICE_SIZE, labels=lab)
    x.column(c_diag, "KWP2000 service id", KWP_SERVICES, 8, out=OUT_HEX, **common)
    x.column(c_diag, "KWP2000 service min length", KWP_SERVICES + 1, 8,
             desc="Minimum request length; 255 = not checked here", **common)
    x.column(c_diag, "KWP2000 service handler", KWP_SERVICES + 4, 32, out=OUT_HEX,
             desc="Handler function, CPU address", **common)
    x.column(c_diag, "KWP2000 service flags", KWP_SERVICES + 8, 16, out=OUT_HEX, **common)
    x.constant(c_diag, "SecurityAccess 0x27 seed XOR bytes (0xF6910)", 0xF6910, 16, out=OUT_HEX,
               desc="ID-record bytes 0xF6910/11 = 09 1B; code uses them little-endian as const 0x1B09: "
                    "seed = (u16 @0x40095C) XOR 0x1B09 (forced 0x53A1 if zero). ECU 'AZ1RAE00008'. 1M = 0x3008.")

    # ---- F-CAN message list (cycle 3; header 0xF59C3 verified) -------------
    f_tx, f_rx = b(FCAN_HDR + 0x10)[0], b(FCAN_HDR + 0x11)[0]
    f_ids = [u16(FCAN_MSG + CAN_MSG_SIZE * i + 2) for i in range(f_tx + f_rx)]
    lab = [("TX " if i < f_tx else "RX ") + f"0x{cid:03X}" for i, cid in enumerate(f_ids)]
    common = dict(rows=f_tx + f_rx, stride_bytes=CAN_MSG_SIZE, labels=lab)
    x.column(c_fcan, "F-CAN id", FCAN_MSG + 2, 16, out=OUT_HEX,
             desc="F-CAN (chassis bus) 11-bit id; RX 0x0CD/0D1/0D4 sensor cluster, 0x0C9 steering.", **common)
    x.column(c_fcan, "F-CAN flags|DLC", FCAN_MSG + 4, 8, out=OUT_HEX, **common)
    x.column(c_fcan, "F-CAN period", FCAN_MSG + 6, 8, units="ms", eq="X*10", **common)
    x.column(c_fcan, "F-CAN mailbox", FCAN_MSG + 13, 8, **common)

    # ---- CSI / steering (cycle 3; byte-verified) ---------------------------
    cnote = ("CSI block 0x40EA8. Steering ratio y/1024 (:1); x = raw steering counts (~0.043 deg/LSB, "
             "unverified). Curve set selected by coding byte 0x4031AA+5. ")
    SET3 = [f"set{s}:p{p}" for s in range(3) for p in range(4)]
    x.column(c_csi, "CSI steer-ratio x (3 sets x 4pt)", 0x40EB4, 16, 12, 2, SET3, signed=True,
             desc=cnote + "Breakpoints (steering counts). Sets 0/1 equal; set 2 differs.")
    x.column(c_csi, "CSI steer-ratio y (3 sets x 4pt)", 0x40ECC, 16, 12, 2, SET3, signed=True,
             eq="X/1024", decimals=3, desc=cnote + "Ratio :1. M3 ~15.9 centre -> 12.6.")
    x.column(c_csi, "CSI sensor sign idx2 (per variant)", 0x40EE4, 16, 12, 2, VAR_LABELS, signed=True,
             desc=cnote + "Sign/gain on cluster channel idx2 (ay). Stock -1 all.")
    x.column(c_csi, "CSI sensor sign idx0 (per variant)", 0x40F14, 16, 12, 2, VAR_LABELS, signed=True,
             desc=cnote + "Channel idx0 (yaw). Stock -1 all.")

    # ---- Brake coding COA/BCO (cycle 3; bodies byte-identical to 1M) --------
    bnote = "COA 0x41978. Pressure ~0.01 bar (unproven); volume units unknown. Brake code 0..1 per axle. "
    x.column(c_brake, "COA p-V pressure axis (shared)", 0x41B4E, 16, 10, 2, [f"p{i}" for i in range(10)],
             signed=True, desc=bnote + "Shared x axis for the volume sets. Stock 0..32700.")
    x.column(c_brake, "COA front p-V volume, code 0", 0x41B62, 16, 10, 2, [f"p{i}" for i in range(10)],
             signed=True, desc=bnote + "Front set, coding 0x4031AA+3 = 0.")
    x.column(c_brake, "COA front p-V volume, code 1", 0x41B76, 16, 10, 2, [f"p{i}" for i in range(10)],
             signed=True, desc=bnote + "Front set, code 1.")
    x.column(c_brake, "COA rear p-V volume, code 0", 0x41B8A, 16, 10, 2, [f"p{i}" for i in range(10)],
             signed=True, desc=bnote + "Rear set, coding 0x4031AA+4 = 0.")
    x.column(c_brake, "COA rear p-V volume, code 1", 0x41B9E, 16, 10, 2, [f"p{i}" for i in range(10)],
             signed=True, desc=bnote + "Rear set, code 1.")
    x.column(c_brake, "BCO coded thresholds (code0, code1)", 0x41764, 16, 14, 2,
             [f"+0x{0xC + 2 * i:02X}" for i in range(14)], signed=True,
             desc="BCO 0x41758 coding-selected thresholds +0x0C..+0x26 (pairs code0/code1). "
                  "Includes compare thresholds 60/87 and 20/76, wait counts, scale 50/150.")

    # ---- DDS / RPA (cycle 3; body byte-identical to 1M) --------------------
    x.constant(c_dds, "DDS enable override", 0x41D48, 16, signed=True,
               desc="0 = use coding bit (0x4031F4 bit4); non-zero forces DDS/RPA on. DDS block 0x41D10.")
    x.constant(c_dds, "DDS aux enable override", 0x41D4A, 16, signed=True,
               desc="0 = use coding bit (0x4031F6 bit4); non-zero forces on.")
    x.column(c_dds, "DDS scalar run (raw, mostly undecoded)", 0x41D1C, 16, 41, 2,
             [f"+0x{0x0C + 2 * i:02X}" for i in range(41)], signed=True,
             desc="DDS 0x41D10 scalar block; a few are %/speed thresholds, most roles unverified. "
                  "RPA = indirect tyre-deflation (spectral) hypothesis.")

    # ---- LVC (cycle 3; body byte-identical to 1M except 0x4226A) -----------
    x.constant(c_lvc, "LVC hold/delay count", 0x4226A, 16, signed=True,
               desc="LVC 0x41E44. The ONE M3-vs-1M calibration difference: M3=75, 1M=50 (cycles; ~0.75 s "
                    "if 10 ms). Down-counter 0x402B56. 'LVC' expansion undetermined (level/long/lat/load).")
    curve_fields(c_lvc, 0x41F10, "LVC signed-axis curve (13pt)",
                 "LVC main curve, signed x axis +/-833. Role undecoded. ", xunits="", xeq="X", xdec=0)
    x.column(c_lvc, "LVC per-coding-variant array 1", 0x422F8, 16, 33, 2,
             [f"c{i}" for i in range(33)], signed=True,
             desc="LVC array indexed by coding 0x4031AA+9 (0..32). Role unverified.")

    # ---- Fault ids (cycle 3) -----------------------------------------------
    x.column(c_fault, "WSS direction fault id per wheel", 0xF576C, 32, 4, 4,
             ["w0 (FL?)", "w1 (FR?)", "w2 (RL?)", "w3 (RR?)"], out=OUT_HEX,
             desc="fault id = group<<16 | mask16; logged by wss_direction_plausibility 0xB9330 at 175 "
                  "counts. Set via fault_set 0xB427C into latch array 0x402838.")

    # ---- OS / scheduler / ROM self-test (cycle 4; byte-verified) -----------
    tasks = ["T0 (event loop)", "T1 (2.5 ms)", "T2 (1 ms)", "T3 (10 ms)", "T4 (background)"]
    x.column(c_os, "OS task entry", 0x424E0, 32, 5, 4, tasks, out=OUT_HEX,
             desc="OSEK task entry points. Runs/frame: T1 4x, T2 10x, T3 1x.")
    x.column(c_os, "OS task priority (0 = highest)", 0x424F4, 16, 5, 2, tasks)
    x.column(c_os, "OS task autostart", 0x42514, 8, 5, 1, tasks)
    x.column(c_os, "OS task stack top", 0x424B8, 32, 5, 4, tasks, out=OUT_HEX)
    x.column(c_os, "OS task stack bottom", 0x424CC, 32, 5, 4, tasks, out=OUT_HEX)
    x.column(c_os, "Time-base slot handlers (vec60, 13-slot 10 ms frame)", 0x70ACC, 32, 13, 4,
             [f"slot {i}" for i in range(13)], out=OUT_HEX, desc="isr_timeslot 0x70A2A jump table.")
    x.column(c_os, "ROM self-test range start", 0xD71F4, 32, 3, 8,
             ["vectors/hdr", "calibration", "code+tables"], out=OUT_HEX,
             desc="Background MISR self-test ranges {start,end}. Table 0xD71F4.")
    x.column(c_os, "ROM self-test range end (expected word stored AT end)", 0xD71F8, 32, 3, 8,
             ["0x402F8", "0x4249C", "0xF691C"], out=OUT_HEX,
             desc="End (exclusive). Expected MISR u32 is stored at each end address. CAL range end = "
                  "0x4249C: after any cal edit, recompute MISR (poly 0x00400007, seed 0, BE words) over "
                  "[0x40300,0x4249C) and write it at 0x4249C, else error 0x10004. (Separate from the BMY sig.)")

    # ---- TCS controller block 0x40FBC (cycle 4; byte-verified) -------------
    tc = "M3 TCS controller (block 0x40FBC). Drive-slip in 0.01 km/h; torque in DME LSB (raw x5). "
    curve_fields(c_tcs, 0x41046, "TCS slip target vs vref",
                 tc + "tcs_slip_target 0xCCED4. 2.30 km/h to 49.6 km/h then ~v/32, cap 10 km/h. ")
    x.column(c_tcs, "TCS PI P-term clamp (min,max)", 0x41068, 16, 2, 2, ["min", "max"], signed=True,
             desc=tc + "tcs_torque_pi 0xCD1E8. Stock -2500/+2500.")
    x.column(c_tcs, "TCS PI I-term error clamp (min,max)", 0x4106E, 16, 2, 2, ["min", "max"], signed=True,
             desc=tc + "Stock -200/+200.")
    x.column(c_tcs, "TCS PI gain set", 0x41072, 16, 4, 2, ["g0", "g1", "g2", "g3"], signed=True,
             desc=tc + "tcs_pi_gain_select 0xCD070 (gain-scheduled by driveline ratio, thr 0x41172=70). "
                       "Stock 180/100/60/25.")
    x.column(c_tcs, "TCS aux limits", 0x4102C, 16, 1, 2, ["lim"], signed=True,
             desc=tc + "Stock 2000 (0x4102C); paired with 0x4106C=400.")
    x.column(c_tcs, "TCS low-pass constants", 0x41064, 16, 2, 2, ["a", "b"], signed=True,
             desc=tc + "Rear/LP filter constants. Stock 90/90.")
    x.column(c_tcs, "TCS per-mode array 1700", 0x4107E, 16, 3, 2, ["m0", "m1", "m2"], signed=True,
             desc=tc + "Per DSC mode (0x4031B1). Stock 1700 all.")
    x.column(c_tcs, "TCS per-mode array 2100", 0x41084, 16, 3, 2, ["m0", "m1", "m2"], signed=True,
             desc=tc + "Stock 2100 all.")

    # ---- Hydraulic actuation (cycle 4; COA-block scalars tunable) ----------
    an = "Hydraulic actuation. Valve current ~mA (unproven); 12 solenoid channels. "
    x.constant(c_act, "Valve sequencer start offset front", 0x41A72, 16, signed=True,
               desc=an + "COA+0xFA. valve_pulse_sequencer 0x853A8. Stock 40.")
    x.constant(c_act, "Valve sequencer start offset rear", 0x41A74, 16, signed=True, desc=an + "Stock 20.")
    x.constant(c_act, "Valve build-mode gain front", 0x41A76, 16, signed=True,
               desc=an + "Build-mode divide gain. Stock 800.")
    x.constant(c_act, "Valve build-mode gain rear", 0x41A78, 16, signed=True, desc=an + "Stock 350.")
    x.column(c_act, "Pump level cal (div, hi, lo)", 0x419D4, 16, 3, 2, ["0x419D4", "0x419D8", "0x419DA"],
             signed=True, desc=an + "pump_motor_control 0x88EC0 level params. Stock 0/100/50; "
                                    "level = clamp(0x401D2E/33, 15); PWM 4000 ticks/level (code literal).")
    x.column(c_act, "Valve channel mask table (const, patch-only)", 0xD7634, 16, 12, 2,
             [f"ch{i}" for i in range(12)], out=OUT_HEX,
             desc="Per-channel solenoid bit. ch0-3 inlet (analog), ch4-7 outlet, ch8-11 USV/HSV (inferred). "
                  "Const ROM, not a cal block. Hold/boost currents (1100/1524/1532) are code literals.")

    # ---- Pressure/volume model (COA block, cycle 5; byte-verified) ---------
    pm = ("Volume-domain hydraulic model (hydraulic_model_step 0x82EF4). Pressure ~0.01 bar (unproven: "
          "LPA plateau 130-500 => 1.3-5.0 bar); volume units unknown; valve-flow Q=isqrt(dp)*open*k/4096. ")
    x.column(c_pm, "LPA pressure curve (y)", 0x41B16, 16, 4, 2, [f"p{i}" for i in range(4)], signed=True,
             desc=pm + "Low-pressure-accumulator pressure vs its volume. Stock 0,130,130,500.")
    x.column(c_pm, "LPA volume axis (x)", 0x41B1E, 16, 4, 2, [f"x{i}" for i in range(4)], signed=True,
             desc=pm + "Stock 0,100,1000,15000.")
    x.column(c_pm, "Valve flow coeff k_in (front, rear)", 0x41B26, 16, 2, 2, ["front", "rear"], signed=True,
             desc=pm + "Inlet-valve build-flow gain. Stock 957/421.")
    x.column(c_pm, "Valve flow coeff k_cross (front, rear)", 0x41B2A, 16, 2, 2, ["front", "rear"],
             signed=True, desc=pm + "Cross-flow gain. Stock 219/421.")
    x.constant(c_pm, "Valve flow coeff k_back", 0x41B2E, 16, signed=True,
               desc=pm + "Reverse (return) inlet flow gain. Stock 705.")
    x.column(c_pm, "Valve flow coeff k_out (front, rear)", 0x41B30, 16, 2, 2, ["front", "rear"], signed=True,
             desc=pm + "Outlet/dump-flow gain. Stock 755/465.")
    x.constant(c_pm, "Pump ramp cap", 0x41B34, 16, signed=True, desc=pm + "Stock 1150.")
    x.constant(c_pm, "Pump gain %", 0x41B36, 16, signed=True, desc=pm + "Stock 100.")
    x.column(c_pm, "Pump-rate curve (y)", 0x41B38, 16, 2, 2, ["y0", "y1"], signed=True,
             desc=pm + "Stock 4300/2600.")
    x.column(c_pm, "Pump-rate curve (x)", 0x41B3C, 16, 2, 2, ["x0", "x1"], signed=True,
             desc=pm + "Stock 0/4300.")
    x.constant(c_pm, "Pump-flow filter coeff (/256)", 0x41B4C, 16, signed=True, eq="X/256", decimals=3,
               desc=pm + "Low-pass on pump flow. Stock 187 (0.73).")
    x.column(c_pm, "Volume temp-comp front (y)", 0x41AE4, 16, 3, 2, ["y0", "y1", "y2"], signed=True,
             desc=pm + "Wheel-volume temperature compensation, front. Stock 0,0,-2500; x axis 0x41AFC {0,40,80}.")
    x.column(c_pm, "Volume temp-comp rear (y)", 0x41AF0, 16, 3, 2, ["y0", "y1", "y2"], signed=True,
             desc=pm + "Rear. Stock 0,0,-1000.")

    # ---- Misc blocks CSW / FSF (cycle 5; byte-verified) --------------------
    x.constant(c_misc, "CSW DDS/RPA wheel reference K", 0x41E40, 16, signed=True,
               desc="CSW block 0x41E28 +0x18 = the only live word (reader 0x954E2-0x9601E, DDS/RPA neutral "
                    "reference). Other CSW words (20/0/7000/6000/5500/2000) have no reader. Stock 1562.")
    x.column(c_misc, "FSF speed-monitor limit y", 0xF57D6, 16, 2, 2, ["@100km/h", "@200km/h"], signed=True,
             desc="FSF block 0xF57C4. speed_dependent_accumulator_monitor 0xBAD80 limit. Stock 286/857.")
    x.column(c_misc, "FSF speed-monitor limit x", 0xF57DA, 16, 2, 2, ["x0", "x1"], signed=True,
             units="km/h", eq="X/100", decimals=2, desc="Stock 10000/20000 (100/200 km/h).")
    x.column(c_misc, "FSF mode clamp", 0xF587E, 16, 4, 2, [f"m{i}" for i in range(4)], signed=True,
             desc="Per-mode clamp (fsf_mode_clamp_users). Stock 5000/5500/6000/6500.")
    x.column(c_misc, "FSF speed-class ladder (no consumer found)", 0xF5822, 16, 14, 2,
             [f"s{i}" for i in range(14)], signed=True, units="km/h", eq="X/100", decimals=2,
             desc="14-step ladder, no code reader located (low confidence). Stock 2000..26000.")

    # ---- Calibration block directory + raw views ---------------------------
    n_blk = u32(CAL_DIR + 4)
    blocks = [(b(CAL_DIR + 12 + 12 * i, 4).rstrip(b"\0").decode("latin1"),
               u32(CAL_DIR + 16 + 12 * i), u32(CAL_DIR + 20 + 12 * i)) for i in range(n_blk)]
    lab = [t for t, _, _ in blocks]
    x.column(c_cal, "Calibration directory: block address", CAL_DIR + 16, 32, n_blk, 12, lab, out=OUT_HEX)
    x.column(c_cal, "Calibration directory: block length", CAL_DIR + 20, 32, n_blk, 12, lab)
    for tag, addr, length in blocks:
        n = (length - 12) // 2
        x.column(c_cal, f"{tag} block raw data (u16)", addr + 12, 16, n, 2,
                 [f"+0x{12 + 2 * i:03X}" for i in range(n)], out=OUT_HEX,
                 desc=f"Raw view of calibration block {tag} at {addr:#x} (len {length:#x}).")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    xml = x.render(
        "MK60E5 E9x M3 DSC 7846816A (DSCM90) - research",
        "Research definition. Load against flash/bin/7846816A_00000000.bin. XDF address = CPU "
        "address + 0x8000. Research only. The image is covered by an in-ECU background ROM "
        "self-test (MISR) and a 512-bit RSA BMY signature (file 0xFEA23 region). Do not flash "
        "edited images without recomputing both. Vehicle-model and slip/decel data byte-verified; "
        "active coding variant/mode live in EEPROM, not in flash.",
        len(data))
    xml = xml.replace("by tools/make_xdf.py", "by tools/make_xdf_m3.py")
    xml = xml.replace('desc="7846411A_00000000.bin"', 'desc="7846816A_00000000.bin"')
    args.out.write_text(xml, encoding="utf-8")
    print(f"wrote {args.out}: {len(x.items)} items, {n_blk} cal blocks")


if __name__ == "__main__":
    main()
