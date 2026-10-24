#!/usr/bin/env python3
"""Bootleg hydraulic simulation of the 7846816A (M3) volume model: two circuits, two wheels each.

Circuit 0 = wheels 0/1 (FL, FR, front p-V curve), circuit 1 = wheels 2/3 (RL, RR, rear curve), as in ROM map
0xDA1B8.  Each circuit has one shared low-pressure accumulator (LPA).  The master cylinder is a pressure source
(driver ramp).  Calibration tables come from the stock image.

Flow law (valve_flow 0x818B6): Q = sqrt(dp) * open * k / 4096 counts per 10 ms, dp in 0.01 bar, open = level * 8.
  inlet   master -> wheel   k_in 0x41B26[axle],  open = inlet_open_effective 0x81938 (build only): level * 8 minus a
                            dp-dependent cracking offset, interp(dp, axis 0xDA5D6 {0,50,100,150,200 bar}, front 0xDA5E0
                            {19,10,7,6,4} / rear 0xDA5EA {14,10,9,7,5}), clamped 0..80.  A low level at a small dp does
                            not open the model valve at all.  --no-cracking restores the plain level * 8.
  back    wheel -> node     check valve around a closed inlet: k_back 0x41B2E (705), open 80; halved when the wheel is
                            < 5 bar above the node.  An open (build) inlet carries reverse flow through k_in.
  outlet  wheel -> LPA      k_out 0x41B30[axle],   open = outlet level * 8; halved when wheel is < 5 bar above LPA
  master port net flow per circuit (CSV *_master_net_cm3s) = change in (wheel volume + LPA volume) per step, i.e. fluid
          crossing the master/USV boundary; positive = into the circuit (negative while the pump returns LPA fluid to the master).
Scope: ABS only.  The USV is never actuated: it is an always-open orifice (k_back 705, opening 80) between the master and a
circuit node, with a check valve around it so the node is never below driver pressure.  The HSV does not exist: the pump
can only draw from its circuit's LPA (fed by the outlets).  The node feeds the wheel inlets (build wheels exchange fluid both
ways through k_in; closed-inlet wheels can only leak back through the check valve around the inlet).  Node pressure is solved
each step from pump discharge = USV flow + net wheel inflow, so a pump discharging through the USV raises the node above
master pressure and every wheel with an open inlet follows it.  (The firmware model sends passive-mode pump flow to the
master and ignores this; it re-seeds PM from the sensors.)

Pump (pump_supply_store_update 0x82824, lpa_pump_draw 0x825B6):
  flow estimate  every frame while the motor runs: target = interp(sum of circuit pressure / 2 over circuits delivering,
                 0..250 bar -> 4300..2600), flow_est += (target - flow_est) * 187/256; decays to 0 when stopped (assumed)
  delivery       pump volume per frame = min(interp(flow_est, 0..4300 -> 0..340 counts), LPA volume); LPA draw = the same
  motor          runs while any LPA volume > 0.  The firmware's motor on/off decision is not traced.
  Not modelled   HSV share, supply store and the 0x88A18 demand paths (all active-build / prefill features).

Metered build (wheel_volume_delta 0x8216E, request mode 2 with a rate other than 9000): the model does not use the flow
law.  Once per 10 ms frame the wheel volume goes to V = pV(min(p_wheel + rate * level / 10, driver pressure)), i.e. the
pressure rises by rate * level / 10 per frame whatever the differential or the caliper, and 0 at level 0.  `rate` is
the arbitrated request rate in 0.01 bar per frame (cal 0x40D5E = 300 front); that `dp` in the firmware routine is the
request rate is inferred.  There is no current-to-flow law anywhere in the firmware model: the physical valve current
(sequencer feed-forward + learned offset) is not simulated, only the open-step count n it is paired with.

Sequencer feed-forward (valve_pulse_sequencer 0x853A8, --sweep-inlet): for a metered build,
  I_hold = inlet_current_for_dp(supply - PM)  (per-unit self-calibration, EEPROM block 16, zero in the default image;
                                               pass --inlet-cal to get currents, else only the k ratio is printed)
  y      = interp(dp, 0 / 20 / 80 bar -> 0 / y2/4 / y2 %), y2 = COA 0x41A72 (40) front / 0x41A74 (20) rear
  C      = brake compliance dV/dp per bar at PM, from the coded p-V curve (curve_slope_fwd 0x852B6)
  D      = C * dp / (G + temp), G = COA 0x41A76 (800) front / 0x41A78 (350) rear
  k      = clamp(100 - rate * y / D, 100 - y, 100) %,  I_build = I_hold * k / 100
  n      = clamp((target - PM) * 10 / rate, 0, 10) open steps of the 10 ms frame (valve_cmd = 2n)
The 5 ms fast loop (setpoint ramp, learned current offset, rate/10 closing band) is described in
INLET_VALVE_CONTROL_7846816A.md and not simulated.

Phases ("t:state[:level[:rate]]", comma separated, seconds): build[:L] | meter:L:RATE | hold | dump[:L]
(L = 0..10, default 10; meter RATE in 0.01 bar per frame, default 300).
Example: --phases "0:build,0.6:hold,0.8:dump,1.0:build"; per-wheel overrides --fl --fr --rl --rr.
Reynolds number uses d_eff implied by k, the volume unit and Cd (see FACTS.md).

Inlet sweep: `--sweep-inlet --pd 60 --pw 30 [--axle front|rear] [--curve-scale 0.5]` holds the driver pressure and
steps one wheel's inlet level 1..10 from a given wheel pressure; see sweep_inlet().
"""
import argparse
import csv
import math
import struct
import sys
from pathlib import Path

ROM = Path(__file__).resolve().parent.parent / "flash/bin/7846816A_00000000.bin"
FRAME = 0.010  # s, firmware model step
WHEELS = ("FL", "FR", "RL", "RR")


def load_rom(path):
    d = Path(path).read_bytes()

    def s16(a, n):
        return list(struct.unpack(">%dh" % n, d[a + 0x8000:a + 0x8000 + 2 * n]))
    return dict(
        axis=s16(0x41B4E, 10),
        curve=[[s16(0x41B62, 10), s16(0x41B76, 10)], [s16(0x41B8A, 10), s16(0x41B9E, 10)]],  # [axle][set]
        lpa_v=s16(0x41B1E, 4), lpa_p=s16(0x41B16, 4),
        k_in=s16(0x41B26, 2), k_back=s16(0x41B2E, 1)[0], k_out=s16(0x41B30, 2),
        oe_axis=s16(0xDA5D6, 5), oe=[s16(0xDA5E0, 5), s16(0xDA5EA, 5)],  # inlet_open_effective offset, [axle]
        ic_axis=s16(0xDA158, 5),  # inlet_current_for_dp axis
        y2=s16(0x41A72, 2), gain=s16(0x41A76, 2),  # COA: valve start offset y2, build-mode gain G, [axle]
    )


def interp(x, xs, ys):
    if x <= xs[0]:
        return ys[0]
    for i in range(1, len(xs)):
        if x <= xs[i]:
            if xs[i] == xs[i - 1]:
                return ys[i]
            return ys[i - 1] + (ys[i] - ys[i - 1]) * (x - xs[i - 1]) / (xs[i] - xs[i - 1])
    return ys[-1]


def valve_flow(dp, k, op, dt):
    """counts moved in dt; the firmware value is per 10 ms frame, dp in 0.01 bar"""
    return min(math.sqrt(abs(dp)) * op * k / 4096.0, 2000.0) * dt / FRAME


def inlet_open_effective(rom, axle, level, dp, cracking=True):
    """inlet_open_effective 0x81938: level * 8 minus the dp-dependent cracking offset, capped at 80 (floor 0 assumed).
    dp = driver - wheel pressure, 0.01 bar.  The 0x401706[w] 'no offset' flag is not modelled."""
    op = level * 8.0
    if cracking and level > 0:
        op -= interp(dp, rom["oe_axis"], rom["oe"][axle])
    return min(max(op, 0.0), 80.0)


def compliance(curve, axis, p):
    """curve_slope_fwd 0x852B6 with scale 100: brake compliance dV/dp in counts per bar at p (0.01 bar).  Forward
    difference over 5 bar; 0 outside the axis."""
    if p < axis[0] or p > axis[-1] - 500:
        return 0.0
    return (interp(p + 500, axis, curve) - interp(p, axis, curve)) / 5.0


def sequencer_ff(rom, axle, curve, dp, pm, rate, target=None, temp=0, hold_ma=None):
    """valve_pulse_sequencer 0x853A8 build branch.  dp = supply - PM and pm in 0.01 bar, rate in 0.01 bar per frame.
    Returns dict(y, C, D, k, n, i_hold, i_build).  hold_ma = I_hold at this dp if known (unit-specific self-cal)."""
    y2 = rom["y2"][axle]
    y = interp(dp, [0, 2000, 8000], [0, y2 / 4.0, y2])
    C = compliance(curve, rom["axis"], pm)
    D = C * dp / (rom["gain"][axle] + temp)
    k = 100 - y if D <= 0 else min(max(100 - rate * y / D, 100 - y), 100)
    n = None if target is None else min(max((target - pm) * 10.0 / rate, 0), 10)
    return dict(y=y, C=C, D=D, k=k, n=n, i_hold=hold_ma, i_build=None if hold_ma is None else hold_ma * k / 100.0)


class Pump:
    """shared pump state (one motor, two circuits)"""

    def __init__(self):
        self.flow_est = 0.0
        self.motor = False


class Circuit:
    def __init__(self, axle, rom, a):
        self.axle, self.rom, self.a = axle, rom, a
        self.curve, self.axis = [v * a.curve_scale for v in rom["curve"][axle][a.curve_set]], rom["axis"]
        self.k_in, self.k_out, self.k_back = rom["k_in"][axle], rom["k_out"][axle], rom["k_back"]
        self.meter_dv = [0.0, 0.0]  # volume still to deliver this frame for metered-build wheels, counts
        p0 = (a.p0_front if axle == 0 else a.p0_rear) * 100
        self.V = [self.vol(p0)] * 2
        self.lpa_v = a.lpa0
        self.lpa_p = interp(self.lpa_v, rom["lpa_v"], rom["lpa_p"])
        self.pvf = 0.0
        self.draw = 0.0

    def vol(self, p):
        return max(interp(p, self.axis, self.curve), 0.0)

    def pres(self, V):
        return interp(V, self.curve, self.axis)

    def diam(self, k):  # m, effective orifice at full opening
        cda = 80 * k / 4096.0 * self.a.unit * 1e-9 / FRAME / math.sqrt(2000.0 / self.a.rho)
        return math.sqrt(4 * cda / self.a.cd / math.pi)

    def to_cm3s(self, counts, dt):
        return counts * self.a.unit * 1e-3 / dt

    def re(self, counts, dt, k):
        qv = abs(counts) * self.a.unit * 1e-9 / dt
        return 4 * qv / (math.pi * self.diam(k) * self.a.nu)

    # ---- 10 ms pump model: the pump can only draw from the LPA (HSV does not exist, outlets feed the LPA)
    def frame(self, pump):
        if not pump.motor:
            self.pvf = 0.0
        else:
            d = interp(pump.flow_est, [0, 4300], [0, 340])
            self.pvf = min(d, self.lpa_v)
        self.draw = self.pvf

    def pres_c(self, pd):
        return max(self.pres(self.V[0]), self.pres(self.V[1]), pd)

    def open_eff(self, lvl, dp):
        return inlet_open_effective(self.rom, self.axle, lvl, dp, self.a.cracking)

    def begin_frame(self, pd, st, lvl, rate):
        """Metered build (wheel_volume_delta, mode 2, rate != 9000): once per 10 ms frame the wheel volume target is
        pV(min(p + rate * level / 10, driver pressure)); the step then delivers dt/FRAME of it."""
        for i in range(2):
            self.meter_dv[i] = 0.0
            if st[i] == "meter" and lvl[i] > 0:
                p = self.pres(self.V[i])
                tgt = min(p + rate[i] * lvl[i] / 10.0, max(pd, p))
                self.meter_dv[i] = max(self.vol(tgt) - self.V[i], 0.0)

    def node_flows(self, pn, pd, p, st, lvl, dt):
        """flows (counts this step) at circuit-node pressure pn: per-wheel signed net into the wheel, USV to master"""
        net = [0.0, 0.0]
        for i in range(2):
            if st[i] == "meter" and lvl[i] > 0:
                net[i] = self.meter_dv[i] * dt / FRAME
            elif st[i] == "build" and lvl[i] > 0:
                if pn >= p[i]:
                    net[i] = valve_flow(pn - p[i], self.k_in, self.open_eff(lvl[i], pn - p[i]), dt)
                else:
                    net[i] = -valve_flow(pn - p[i], self.k_in, lvl[i] * 8, dt)
            elif p[i] > pn:  # inlet closed: check valve around the inlet
                q = valve_flow(p[i] - pn, self.k_back, 80, dt)
                net[i] = -(q / 2 if p[i] - pn < 500 else q)
        usv = valve_flow(pn - pd, self.k_back, 80, dt) * (1 if pn >= pd else -1)
        return net, usv

    def step(self, pd, st, lvl, dt):
        """The USV is a fixed orifice (k_back, fully open) between the master and the circuit node; the node feeds the
        wheel inlets.  Node pressure is solved each step from pump discharge = USV flow + net wheel inflow, floored at
        driver pressure (check valve around the USV).  Returns per-wheel flows, USV flow and node pressure."""
        f = dt / FRAME
        p = [self.pres(v) for v in self.V]
        qp = self.pvf * f  # pump discharge into the node this step
        pn = pd
        net, usv = self.node_flows(pn, pd, p, st, lvl, dt)
        if sum(net) + usv < qp:  # need a higher node pressure to pass the pump flow
            lo, hi = pd, pd + 20000.0
            for _ in range(40):
                mid = 0.5 * (lo + hi)
                net, usv = self.node_flows(mid, pd, p, st, lvl, dt)
                if sum(net) + usv < qp:
                    lo = mid
                else:
                    hi = mid
            pn = hi
            net, usv = self.node_flows(pn, pd, p, st, lvl, dt)
        out = [dict(inl=max(net[i], 0.0), back=max(-net[i], 0.0), outl=0.0, back_k=self.k_in if st[i] == "build"
                    else self.k_back) for i in range(2)]
        for i in range(2):
            out[i]["back"] = min(out[i]["back"], self.V[i])
        dumped = 0.0
        for i in range(2):
            if st[i] == "dump" and lvl[i] >= 1:
                dpo = p[i] - self.lpa_p
                if dpo >= 1:
                    q = valve_flow(dpo, self.k_out, lvl[i] * 8, dt)
                    if dpo < 500:
                        q /= 2
                    out[i]["outl"] = min(q, max(self.V[i] - self.vol(self.lpa_p), 0.0))
                    dumped += out[i]["outl"]
        v0 = sum(self.V) + self.lpa_v
        for i in range(2):
            self.V[i] = min(max(self.V[i] + out[i]["inl"] - out[i]["back"] - out[i]["outl"], 0.0), 30000.0)
        self.lpa_v = min(max(self.lpa_v + dumped - self.draw * f, 0.0), self.rom["lpa_v"][-1])
        self.lpa_p = interp(self.lpa_v, self.rom["lpa_v"], self.rom["lpa_p"])
        return out, sum(self.V) + self.lpa_v - v0, usv, pn


def parse_phases(s):
    out = []
    for item in s.split(","):
        f = item.strip().split(":")
        out.append((float(f[0]), f[1], int(f[2]) if len(f) > 2 else 10, int(f[3]) if len(f) > 3 else 300))
    return sorted(out)


def phase_at(ph, t):
    cur = ph[0]
    for p in ph:
        if p[0] <= t:
            cur = p
    return cur[1], cur[2], cur[3]


def ramp_inlet(a, rom):
    """One wheel on a held driver pressure (--pd) from --pw; every 10 ms frame an integer inlet level 0..10 (valve_cmd =
    2 * level, the open-step count n of the sequencer) is chosen to follow a setpoint ramp of --ramp-rate bar/s.  The
    level is held for the whole frame and the physical flow law with the cracking offset (inlet_open_effective) is
    integrated in 1 ms steps.  Controllers (--controller):
      predict   pick the level whose predicted end-of-frame pressure (same flow law, so no model error) is closest to the
                setpoint at the end of the frame the level takes effect in; the best case for quantised levels
      firmware  the sequencer's open-step rule n = clamp((target - PM) * 10 / rate, 0, 10) with target = the setpoint at
                the end of the frame and rate = the ramp per frame; it assumes the metered model (pressure rise = rate *
                n / 10), not the flow law, so it shows what that rule does on this plant
    --cmd-delay N frames between the decision and the level taking effect (decisions use the measured pressure at the
    start of the frame).  The sensor is ideal (no lag or noise).  Writes one row per frame to --csv."""
    axle = 0 if a.axle == "front" else 1
    curve = [v * a.curve_scale for v in rom["curve"][axle][a.curve_set]]
    axis, k_in = rom["axis"], rom["k_in"][axle]
    pd = a.pd * 100
    pres = lambda V: interp(V, curve, axis)
    vol = lambda p: max(interp(p, axis, curve), 0.0)
    step = FRAME / 10  # 1 ms
    per_frame = a.ramp_rate * FRAME  # bar per frame

    def run_frame(V, level):
        q_tot = 0.0
        for _ in range(10):
            p = pres(V)
            dp = pd - p
            q = valve_flow(dp, k_in, inlet_open_effective(rom, axle, level, dp, a.cracking), step) if dp > 0 else 0.0
            V += q
            q_tot += q
        return V, q_tot

    V = vol(a.pw * 100)
    queue = [0] * a.cmd_delay  # levels decided but not yet in effect
    rows = []
    for k in range(a.ramp_frames):
        p0 = pres(V)
        sp_end = lambda j: min(a.pw + per_frame * (j + 1), a.pd) * 100
        # state after the in-flight commands, to predict the frame the new command lands in
        Vp = V
        for lv in queue:
            Vp, _ = run_frame(Vp, lv)
        pp = pres(Vp)
        tgt = sp_end(k + a.cmd_delay)
        if a.controller == "predict":
            best = min(range(11), key=lambda lv: (abs(pres(run_frame(Vp, lv)[0]) - tgt), lv))
        else:
            best = int(min(max(round((tgt - pp) * 10.0 / (per_frame * 100)), 0), 10))
        queue.append(best)
        applied = queue.pop(0)
        dp0 = pd - p0
        V1, q = run_frame(V, applied)
        p1 = pres(V1)
        rows.append(dict(frame=k, t_s=round(k * FRAME, 3), setpoint_end_bar=round(sp_end(k) / 100, 2),
                         p_start_bar=round(p0 / 100, 2), p_end_bar=round(p1 / 100, 2),
                         err_end_bar=round((p1 - sp_end(k)) / 100, 2), cmd_level=best, valve_cmd=2 * best,
                         applied_level=applied, applied_valve_cmd=2 * applied,
                         opening_eff=round(inlet_open_effective(rom, axle, applied, dp0, a.cracking), 1),
                         dp_start_bar=round(dp0 / 100, 2), flow_counts=round(q, 1),
                         rise_bar=round((p1 - p0) / 100, 2), rate_bar_s=round((p1 - p0), 1)))
        V = V1
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)
    ramp = [r for r in rows if r["p_start_bar"] < a.pd - 5 and r["setpoint_end_bar"] < a.pd]
    lv = [r["applied_level"] for r in ramp]
    errs = [r["err_end_bar"] for r in ramp]
    t_to = next((r["t_s"] + FRAME for r in rows if r["p_end_bar"] >= a.pd - 5), None)
    print("# %s inlet, curve x%.2f, driver %.0f bar, start %.0f bar, target %g bar/s (%.2f bar/frame), controller %s, "
          "cmd delay %d frame(s), cracking %s" % (a.axle, a.curve_scale, a.pd, a.pw, a.ramp_rate, per_frame, a.controller,
                                                 a.cmd_delay, "on" if a.cracking else "off"))
    if ramp:
        mean_rate = (ramp[-1]["p_end_bar"] - ramp[0]["p_start_bar"]) / (len(ramp) * FRAME)
        print("# ramp frames %d: mean rate %.0f bar/s, end-of-frame error mean %.2f / min %.2f / max %.2f bar, "
              "rms %.2f bar, levels used %s, level changes %d, frames at level 0: %d, time to within 5 bar of the driver %s s"
              % (len(ramp), mean_rate, sum(errs) / len(errs), min(errs), max(errs),
                 math.sqrt(sum(e * e for e in errs) / len(errs)), sorted(set(lv)),
                 sum(1 for i in range(1, len(lv)) if lv[i] != lv[i - 1]), lv.count(0), t_to))


def sweep_inlet(a, rom):
    """One wheel on a held driver pressure (--pd) from --pw, inlet level 1..10, no pump / outlet / second wheel.
    Table 1: the flow-law branch (build with full-build request, or any non-metered build): effective opening, flow, the
    pressure rise per 10 ms frame it gives through the caliper compliance, and the time to approach the driver pressure.
    Table 2: the metered-build branch of wheel_volume_delta: rise = rate * level / 10 per frame.
    Table 3: sequencer feed-forward (y, C, D, k, n) for a few rates at this dp and PM."""
    axle = 0 if a.axle == "front" else 1
    curve = [v * a.curve_scale for v in rom["curve"][axle][a.curve_set]]
    axis, k_in = rom["axis"], rom["k_in"][axle]
    pd, pw = a.pd * 100, a.pw * 100
    pres = lambda V: interp(V, curve, axis)
    vol = lambda p: max(interp(p, axis, curve), 0.0)
    targets = [pd - 500, pd - 200, pd - 100]
    rows = []
    print("# %s inlet, k_in %d, p-V curve set %d x %.2f, driver %.1f bar, wheel %.1f bar, cracking %s" % (
        a.axle, k_in, a.curve_set, a.curve_scale, a.pd, a.pw, "on" if a.cracking else "off"))
    print("# compliance at the start: %.0f counts/bar (curve_slope_fwd)" % compliance(curve, axis, pw))
    print("\n[1] flow-law branch, 10 ms frames (Q = sqrt(dp) * open * k / 4096)")
    print("level  open   Q_counts/frame  bar/frame  frames to %s" % "  ".join("%.1f bar" % (t / 100) for t in targets))
    for L in range(1, 11):
        V, p = vol(pw), pw
        first, hit = None, [None] * len(targets)
        for fr in range(1, 301):
            dp = pd - p
            q = valve_flow(dp, k_in, inlet_open_effective(rom, axle, L, dp, a.cracking), FRAME) if dp > 0 else 0.0
            if first is None:
                first = q
            V += q
            p = pres(V)
            for j, t in enumerate(targets):
                if hit[j] is None and p >= t:
                    hit[j] = fr
        d0 = pd - pw
        bpf = (pres(vol(pw) + first) - pw) / 100
        rows.append((L, inlet_open_effective(rom, axle, L, d0, a.cracking), first, bpf, hit))
        print("%3d  %5.1f  %12.0f  %9.2f  %s" % (L, rows[-1][1], first, bpf, "  ".join(
            "%9s" % (h if h else ">300") for h in hit)))
    print("\n[2] metered branch (rate %d = %.1f bar/frame): pressure rise = rate * level / 10 per frame, capped at the driver"
          % (a.meter_rate, a.meter_rate / 100))
    print("level  bar/frame  frames to %.1f bar" % ((pd - 500) / 100))
    for L in range(1, 11):
        p, fr = pw, 0
        while p < pd - 500 and fr < 300:
            tgt = min(p + a.meter_rate * L / 10.0, pd)
            p = pres(vol(tgt))
            fr += 1
        print("%3d  %9.2f  %10s" % (L, a.meter_rate * L / 1000.0, fr if fr < 300 else ">300"))
    print("\n[3] sequencer feed-forward at dp %.1f bar, PM %.1f bar (D = C * dp / G, k = clamp(100 - rate * y / D, 100 - y, 100))"
          % ((pd - pw) / 100, pw / 100))
    print("rate bar/frame     y%%     C   D      k%%   current vs I_hold%s" % ("   I_build mA" if a.inlet_cal else ""))
    hold_ma = None
    if a.inlet_cal:
        f = [float(x) for x in a.inlet_cal.split(",")]
        hold_ma = interp(pd - pw, rom["ic_axis"], f)
    for rate in (100, 150, 300, 500, 600):
        r = sequencer_ff(rom, axle, curve, pd - pw, pw, rate, target=pw + 500, hold_ma=hold_ma)
        extra = "   %9.0f" % r["i_build"] if hold_ma is not None else ""
        print("%5d  %9.1f  %5.1f %5.0f %4.0f  %6.1f   -%4.1f%%%s" % (rate, rate / 100, r["y"], r["C"], r["D"], r["k"], 100 - r["k"], extra))
    r = sequencer_ff(rom, axle, curve, pd - pw, pw, a.meter_rate, target=pw + 500)
    print("open steps n for a 5 bar rung at rate %d: %.1f of 10 (clamped)" % (a.meter_rate, r["n"]))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", default=str(ROM))
    ap.add_argument("--duration", type=float, default=1.5, help="s")
    ap.add_argument("--dt", type=float, default=0.001, help="integration step s (0.01 = firmware frame)")
    ap.add_argument("--pd0", type=float, default=0.0, help="initial driver pressure, bar")
    ap.add_argument("--rate", type=float, default=100.0, help="driver rate, bar/s (negative = release)")
    ap.add_argument("--pd-max", type=float, default=200.0)
    ap.add_argument("--pd-min", type=float, default=0.0)
    ap.add_argument("--p0-front", type=float, default=None, help="initial caliper bar (default = pd0)")
    ap.add_argument("--p0-rear", type=float, default=None)
    ap.add_argument("--lpa0", type=float, default=0.0, help="initial LPA volume, counts")
    ap.add_argument("--no-pump", action="store_true", help="motor never runs")
    ap.add_argument("--phases", default="0:build", help="valve phases, all wheels")
    for w in WHEELS:
        ap.add_argument("--" + w.lower(), default=None, help="phases for %s only" % w)
    ap.add_argument("--curve-set", type=int, default=0, choices=(0, 1), help="p-V curve set (coding bytes 3/4)")
    ap.add_argument("--unit-mm3", type=float, default=0.1, help="mm^3 per count")
    ap.add_argument("--cd", type=float, default=0.7)
    ap.add_argument("--rho", type=float, default=1050.0, help="kg/m^3")
    ap.add_argument("--nu-cst", type=float, default=10.0, help="kinematic viscosity mm^2/s (DOT4 ~10 at 25-30C)")
    ap.add_argument("--curve-scale", type=float, default=1.0,
                    help="scale of the p-V volumes (caliper stiffness; the MR2 patches use 0.5 front, 0.7 rear)")
    ap.add_argument("--no-cracking", action="store_true", help="inlet opening = level * 8 (no inlet_open_effective offset)")
    ap.add_argument("--sweep-inlet", action="store_true", help="inlet level 1..10 at fixed --pd / --pw, then exit")
    ap.add_argument("--ramp-inlet", action="store_true",
                    help="follow a setpoint ramp (--ramp-rate) with integer inlet levels at fixed --pd / --pw, then exit")
    ap.add_argument("--ramp-rate", type=float, default=150.0, help="ramp: target pressure rate, bar/s")
    ap.add_argument("--ramp-frames", type=int, default=30, help="ramp: number of 10 ms frames")
    ap.add_argument("--controller", default="predict", choices=("predict", "firmware"), help="ramp: level selection rule")
    ap.add_argument("--cmd-delay", type=int, default=0, help="ramp: frames between the decision and the level taking effect")
    ap.add_argument("--meter-rate", dest="meter_rate", type=int, default=300, help="sweep: metered request rate, 0.01 bar/frame")
    ap.add_argument("--inlet-cal", default=None,
                    help="sweep: this unit's inlet hold currents f[w] at dp 0/20/50/90/140 bar, mA, comma separated "
                         "(EEPROM block 16; not in the default image)")
    ap.add_argument("--pd", type=float, default=60.0, help="sweep: held driver pressure, bar")
    ap.add_argument("--pw", type=float, default=30.0, help="sweep: initial wheel pressure, bar")
    ap.add_argument("--axle", default="front", choices=("front", "rear"), help="sweep: which inlet / curve")
    ap.add_argument("--print-every", type=float, default=0.05)
    ap.add_argument("--csv", default=None, help="write the full trace here (one row per --csv-every)")
    ap.add_argument("--csv-every", type=float, default=0.005)
    ap.add_argument("--plot", default=None, help="PNG path")
    a = ap.parse_args()
    a.unit, a.nu = a.unit_mm3, a.nu_cst * 1e-6
    a.cracking = not a.no_cracking
    a.p0_front = a.pd0 if a.p0_front is None else a.p0_front
    a.p0_rear = a.pd0 if a.p0_rear is None else a.p0_rear

    rom = load_rom(a.rom)
    if a.sweep_inlet:
        return sweep_inlet(a, rom)
    if a.ramp_inlet:
        return ramp_inlet(a, rom)
    circ = [Circuit(0, rom, a), Circuit(1, rom, a)]
    pump = Pump()
    ph = [parse_phases(getattr(a, w.lower()) or a.phases) for w in WHEELS]
    print("# d_eff mm (Cd %.2f, %.3g mm3/count): front in %.3f out %.3f | rear in %.3f out %.3f | back %.3f" % (
        a.cd, a.unit, 1e3 * circ[0].diam(circ[0].k_in), 1e3 * circ[0].diam(circ[0].k_out),
        1e3 * circ[1].diam(circ[1].k_in), 1e3 * circ[1].diam(circ[1].k_out), 1e3 * circ[0].diam(circ[0].k_back)))
    print("t_s   pd   | FL     FR     | RL     RR     | LPA_f bar  mm3 | LPA_r bar  mm3")

    cols = ["t_s", "driver_bar"]
    for w in WHEELS:
        cols += [w + s for s in ("_p_bar", "_V_counts", "_V_mm3", "_inlet_cm3s", "_back_cm3s", "_outlet_cm3s",
                                 "_Re_inlet", "_Re_outlet", "_Re_back")]
    for c in ("F", "R"):
        cols += ["LPA_%s_bar" % c, "LPA_%s_counts" % c, "LPA_%s_mm3" % c,
                 "%s_master_net_cm3s" % c, "%s_pump_vol_counts_per_frame" % c,
                 "%s_node_bar" % c, "%s_usv_cm3s" % c, "%s_usv_Re" % c]
    cols += ["pump_flow_est", "pump_motor"]
    rows, peak = [], {}
    n = int(round(a.duration / a.dt))
    next_print = next_csv = 0.0
    for i in range(n + 1):
        t = i * a.dt
        pd = min(max(a.pd0 + a.rate * t, a.pd_min), a.pd_max) * 100
        sls = [[phase_at(ph[2 * c + j], t) for j in range(2)] for c in (0, 1)]
        if i % max(int(round(FRAME / a.dt)), 1) == 0:
            for c in (0, 1):
                circ[c].t = t
            pump.motor = (not a.no_pump) and any(C.lpa_v > 0 for C in circ)
            if pump.motor:
                x = sum(C.pres_c(pd) / 2 for C in circ if C.pvf != 0)
                tgt = interp(x, [0, 25000], [4300, 2600])
            else:
                tgt = 0.0
            pump.flow_est += (tgt - pump.flow_est) * 187 / 256
            for c in (0, 1):
                circ[c].frame(pump)
                circ[c].begin_frame(pd, [s_[0] for s_ in sls[c]], [s_[1] for s_ in sls[c]], [s_[2] for s_ in sls[c]])
            pump.motor = (not a.no_pump) and any(C.lpa_v > 0 for C in circ)
        res, nets, usvs, nodes = [], [], [], []
        for c in (0, 1):
            o, nv, uq, pn = circ[c].step(pd, [s_[0] for s_ in sls[c]], [s_[1] for s_ in sls[c]], a.dt)
            res.append(o)
            nets.append(nv)
            usvs.append(uq)
            nodes.append(pn)
        if t + 1e-9 >= next_csv or t + 1e-9 >= next_print:
            row = [round(t, 5), round(pd / 100, 3)]
            for c in (0, 1):
                C = circ[c]
                for j in range(2):
                    o = res[c][j]
                    k_out_ = C.k_out
                    row += [round(C.pres(C.V[j]) / 100, 3), round(C.V[j], 1), round(C.V[j] * a.unit, 1),
                            round(C.to_cm3s(o["inl"], a.dt), 3), round(C.to_cm3s(o["back"], a.dt), 3),
                            round(C.to_cm3s(o["outl"], a.dt), 3),
                            round(C.re(o["inl"], a.dt, C.k_in)), round(C.re(o["outl"], a.dt, k_out_)),
                            round(C.re(o["back"], a.dt, o["back_k"]))]
            for c in (0, 1):
                row += [round(circ[c].lpa_p / 100, 3), round(circ[c].lpa_v, 1), round(circ[c].lpa_v * a.unit, 1),
                        round(circ[c].to_cm3s(nets[c], a.dt), 3), round(circ[c].pvf, 1),
                        round(nodes[c] / 100, 3),
                        round(circ[c].to_cm3s(usvs[c], a.dt), 3), round(circ[c].re(usvs[c], a.dt, circ[c].k_back))]
            row += [round(pump.flow_est, 1), int(pump.motor)]
            for name, idx in zip(cols, range(len(cols))):
                if name.endswith(("_Re_inlet", "_Re_outlet", "_Re_back")):
                    peak[name] = max(peak.get(name, 0), row[idx])
            if t + 1e-9 >= next_csv:
                rows.append(row)
                next_csv += a.csv_every
            if t + 1e-9 >= next_print:
                ip = {w: cols.index(w + "_p_bar") for w in WHEELS}
                print("%.3f %6.2f | %6.2f %6.2f | %6.2f %6.2f | %5.2f %7.1f | %5.2f %7.1f" % (
                    t, pd / 100, row[ip["FL"]], row[ip["FR"]], row[ip["RL"]], row[ip["RR"]],
                    row[cols.index("LPA_F_bar")], row[cols.index("LPA_F_mm3")],
                    row[cols.index("LPA_R_bar")], row[cols.index("LPA_R_mm3")]))
                next_print += a.print_every
    print("# peak Re (sampled): " + ", ".join(
        "%s %s %.0f" % (w, k, peak.get(w + "_Re_" + k, 0)) for w in ("FL", "RL") for k in ("inlet", "outlet", "back")))
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            cw = csv.writer(f)
            cw.writerow(cols)
            cw.writerows(rows)
    if a.plot:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        T = [r[0] for r in rows]
        fig, ax = plt.subplots(2, 1, figsize=(9, 7), sharex=True)
        ax[0].plot(T, [r[1] for r in rows], "k--", label="driver")
        for w in WHEELS:
            ax[0].plot(T, [r[cols.index(w + "_p_bar")] for r in rows], label=w)
        ax[0].set_ylabel("bar")
        ax[0].legend()
        ax[0].grid(alpha=.3)
        for w in WHEELS:
            ax[1].plot(T, [r[cols.index(w + "_V_counts")] for r in rows], label=w)
        ax[1].set_ylabel("volume, counts")
        ax[1].set_xlabel("s")
        ax[1].legend()
        ax[1].grid(alpha=.3)
        fig.tight_layout()
        fig.savefig(a.plot, dpi=110)


if __name__ == "__main__":
    sys.exit(main())
