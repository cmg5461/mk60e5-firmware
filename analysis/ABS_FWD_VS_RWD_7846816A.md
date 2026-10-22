# MK60E5 M3 (7846816A) ABS on FWD vs RWD — TL;DR

CPU addresses. Scope: ABS only. TCS and MSR are dead without the SZL and are not covered. Related:
`agents/abs_full/09_chassis_sensor_use.md`, `agents/abs_full/10_vref_and_ax.md`, `agents/abs_full/08_phase_control.md` §7.

## Bottom line

M3 ABS has no drivetrain awareness: it never reads engine torque, rpm, gear or clutch, and no coding field says
which axle is driven. Its one implicit RWD assumption is that **the fronts roll freely and are the best speed
reference**. On FWD that holds except under engine braking. Separately, without the SZL the rear axle is always
select-low, which hurts any car that lifts an inside rear.

## What carries over unchanged

- **Front/rear split is by axle position, not drive.** Fronts are controlled individually, rears are select-low,
  and each axle has its own decel curves, p-V curves and dump percentages.
- **vref outside ABS** rises only when every wheel is above it and falls toward the fastest wheel. That works for
  any drive layout.
- **ABS ignores DME and gearbox signals.** There are no references to torque/rpm RAM in 0x40000–0x5DFFF, and gear
  (0x0BA) is read only by TCS/DSC.
- **Calibration is still M3-tuned** (about 50/50 weight, M3 brake bias). On a front-heavy FWD car that mismatch is
  real, but it isn't about which axle is driven.

## FWD risks (inferred, not tested)

Inside ABS, `vref_update` (0x449D0) rises only by following the fastest front. Rears are also dropped from the
fastest-wheel pick while a front is in an ABS cycle. On FWD the fronts carry the driveline, so:

1. **Engine drag on low µ (clutch in):** both fronts are dragged below road speed together. vref follows them
   down, front slip reads too small, and the fronts run deeper slip before ABS dumps.
2. **Slow front recovery:** reapply waits for the wheel to re-accelerate (`rec+0x39`). Fronts with drivetrain
   inertia attached spin up more slowly, so reapply comes late and front pressure stays low.
3. **Open front diff:** under drag the fronts are mechanically coupled, and dumping one affects the other. Front
   control assumes each wheel is independent.
4. **No SZL makes it worse:** ax never becomes trusted, so nothing catches vref sinking with the fronts.

On high µ, or with the clutch disengaged, there is essentially no difference from RWD.

## Inside rear lift on corner entry

Without the SZL, a lifted inside rear drags the loaded outside rear down with it, and the rear axle loses roughly
all its brake force while the wheel is in the air.

1. With no load, the lifted wheel locks within a few frames, and ABS starts dumping it.
2. It becomes the lead rear: highest phase score (`abs_rear_lead_select` 0x5184C) and lowest command
   (`abs_decision_resolve` 0x58B30).
3. Select-low (code 64/8, exec 0x5932A) clamps the outside rear to the lead's command plus an offset, so the
   outside rear is dumped too.
4. In the air nothing spins the wheel back up. Slip stays above the dump-again threshold (EV0.b0), so both rears
   stay dumped. No dump timeout was found.
5. At touchdown the wheel spins up, reapply starts, and the follower comes back with a pressure step.

The stock M3 *with* the SZL handles this using lateral g: rears go independent at light pedal (code 1), a
lateral-scaled partial knockdown applies above that (code 32), and the lead rear is picked by the sign of
lateral g. Without lateral g, a controlling rear is always code 64.

The 0x19E status bit "rear controlled without front" (0x408DA0 b1) should flicker during these events, so you
can spot them in logs.

## Track car: independent rears

For a dry track car where the alternative is no ABS, fully independent rears is the best of the three options.

| Option | Rear brake in corners | Inside rear lifts | Split-µ straight-line yaw | Rear lockup |
| --- | --- | --- | --- | --- |
| No ABS | Full, up to the driver | Lifted wheel locks; no loss, since it has no load | Driver-limited | Possible, leading to a spin |
| Select-low (stock, no SZL) | Limited to what the inside rear can take | Both rears dumped | Smallest | Prevented |
| Independent rears (code 1) | Each rear at its own peak | Only the lifted wheel dumps | Larger; GMA needs yaw, so nothing limits it | Prevented |

The cost of independent rears is less rear lateral margin, because the high-grip rear runs at peak slip. That
matters more on a rear-heavy car like the MR2 than on FWD.

**Patch outline:** make `abs_decision_classify` 0x51B54 output code 1 instead of 64, starting with the default at
0x51C6C. Code 1 is a normal factory mode with no exec case, so each rear runs its own loop.

**Coupling that remains, to check in logs afterwards:**

- Low-µ pair coupling at 0x48EB0 (a pressure step is skipped when the partner is flagged).
- The combined rear dump in classifier block 13 (0x409057 b6).
- The vref rear-exclusion during front ABS (reference only).

**Middle ground:** keep select-low only when both rears are in deep slip at similar speeds, and go independent
when one rear is far below vref while its partner isn't. The rear wheel-speed difference is already available
without the SZL (`abs_side_select` 0x5AEEE).
