#!/usr/bin/env python
"""Visualize MK60E5 (M3 7846816A) ABS curves as a self-contained HTML page
(inline SVG, no deps). Uses the exact firmware curve evaluator:
    i = count of breakpoints x[j] with X >= x[j]
    y = c[i] + ((X * k[i]) >> 10)           # Q10 slope, arithmetic shift
    y = clamp(y, lo, hi)
Curves read from a bin image; pass --yaml to preview edits (applied in-memory via
tools/cal_yaml.py apply to a temp image first). Plots the ABS entry-slip threshold
(km/h + slip %), the per-variant speed-term and g-term decel curves.

Usage:
  python tools/cal_plot.py --out plot.html
  python tools/cal_plot.py --yaml flash/cal/e36.yaml --variant 0 --out plot.html
"""
import argparse, os, struct, subprocess, sys, tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_IMG = os.path.join(os.path.dirname(HERE), "flash", "bin", "7846816A_00000000.bin")

ENTRY_SLIP = 0x48db6           # entry GATE: slip-SPEED, arms ABS (~1.5 km/h)
GROSS_SLIP = 0xdece2           # real slip limit: slip-speed curve == ~11% of vref (peak-mu)
SPEED_TERM = (0x48412, 0x28)   # base, per-variant stride
G_TERM     = (0x48674, 0x40)
LAT_A      = 0x48e0a           # cornering lateral-g pressure term A (primary, +5 bar boost >0.8 g)
LAT_B      = 0x48e26           # cornering lateral-g pressure term B (companion)

def load_curve(buf, base):
    r = lambda off: struct.unpack(">h", buf[off:off+2])[0]
    lo, hi, n = r(base), r(base+2), r(base+4)
    o = base + 6
    xs = [r(o+2*i) for i in range(n-1)];               o += 2*(n-1)
    cs = [r(o+2*i) for i in range(n)];                 o += 2*n
    ks = [r(o+2*i) for i in range(n)]
    return lo, hi, n, xs, cs, ks

def eval_curve(c, x):
    lo, hi, n, xs, cs, ks = c
    x = int(x)
    i = 0
    while i < n-1 and x >= xs[i]: i += 1
    y = cs[i] + ((x * ks[i]) >> 10)      # python >> floors like M-CORE asr
    return max(lo, min(hi, y))

def svg(title, xlabel, ylabel, series, xmax, ymin, ymax, note=""):
    """series: list of (label, color, [(x,y)...]). Returns an <svg> figure."""
    W, H, ml, mr, mt, mb = 820, 480, 68, 22, 48, 56
    pw, ph = W-ml-mr, H-mt-mb
    def sx(x): return ml + pw*(x/xmax if xmax else 0)
    def sy(y):
        return mt + ph*(1 - ((y-ymin)/(ymax-ymin) if ymax != ymin else 0))
    parts = ['<svg viewBox="0 0 %d %d" role="img" aria-label="%s" style="width:100%%;height:auto">' % (W, H, title)]
    parts.append('<text x="%d" y="28" class="t">%s</text>' % (ml, title))
    # axes
    parts.append('<line x1="%d" y1="%d" x2="%d" y2="%d" class="ax"/>' % (ml, mt, ml, mt+ph))
    parts.append('<line x1="%d" y1="%d" x2="%d" y2="%d" class="ax"/>' % (ml, mt+ph, ml+pw, mt+ph))
    # y gridlines/labels (4)
    for g in range(5):
        yv = ymin + (ymax-ymin)*g/4
        yy = sy(yv)
        parts.append('<line x1="%d" y1="%.1f" x2="%d" y2="%.1f" class="gr"/>' % (ml, yy, ml+pw, yy))
        parts.append('<text x="%d" y="%.1f" class="yl">%.4g</text>' % (ml-6, yy+4, yv))
    # x labels (0..xmax, 5)
    for g in range(6):
        xv = xmax*g/5; xx = sx(xv)
        parts.append('<text x="%.1f" y="%d" class="xl">%.4g</text>' % (xx, mt+ph+18, xv))
    parts.append('<text x="%d" y="%d" class="al">%s</text>' % (ml+pw//2, H-6, xlabel))
    parts.append('<text x="14" y="%d" class="al" transform="rotate(-90 14 %d)">%s</text>' % (mt+ph//2, mt+ph//2, ylabel))
    for label, color, pts in series:
        d = " ".join("%.1f,%.1f" % (sx(x), sy(y)) for x, y in pts)
        parts.append('<polyline points="%s" fill="none" stroke="%s" stroke-width="2.2"/>' % (d, color))
    # legend
    lx = ml+pw-150
    for j, (label, color, _) in enumerate(series):
        ly = mt+8+16*j
        parts.append('<line x1="%d" y1="%d" x2="%d" y2="%d" stroke="%s" stroke-width="3"/>' % (lx, ly, lx+20, ly, color))
        parts.append('<text x="%d" y="%d" class="lg">%s</text>' % (lx+26, ly+4, label))
    if note:
        parts.append('<text x="%d" y="%d" class="nt">%s</text>' % (ml, mt+ph+34, note))
    parts.append('</svg>')
    return "".join(parts)

def build(buf, variant):
    entry = load_curve(buf, ENTRY_SLIP)
    gross = load_curve(buf, GROSS_SLIP)
    st = load_curve(buf, SPEED_TERM[0] + variant*SPEED_TERM[1])
    gt = load_curve(buf, G_TERM[0] + variant*G_TERM[1])
    figs = []
    # GROSS-slip limit as % of vref — the real peak-slip curve
    gpc = [(v, (eval_curve(gross, v*100)/100.0)/v*100) for v in range(10, 301, 2)]
    figs.append(svg("ABS gross-slip limit (% of vref)  [the slip curve]", "vref (km/h)", "slip (%)",
                    [("slip%", "var(--a)", gpc)], 300, 0, max(14, max(y for _, y in gpc)*1.1),
                    note="peak-mu race tyre ~8-12%  (stock ~11%% above 55 km/h)"))
    # GROSS-slip as slip speed (km/h) — how it's actually stored
    gks = [(v, eval_curve(gross, v*100)/100.0) for v in range(0, 301, 2)]
    figs.append(svg("ABS gross-slip limit (slip speed)", "vref (km/h)", "slip speed (km/h)",
                    [("km/h", "var(--b)", gks)], 300, 0, max(6, max(y for _, y in gks)*1.1),
                    note="flat ~6 km/h <55, slope 0.11 above = ~11%% ratio"))
    # ENTRY gate (small, arms ABS) — slip speed
    thr = [(v, eval_curve(entry, v*100)/100.0) for v in range(1, 301, 2)]
    figs.append(svg("ABS entry gate (arms ABS)", "vref (km/h)", "slip speed (km/h)",
                    [("km/h", "var(--b)", thr)], 300, 0, max(3, max(y for _, y in thr)*1.1),
                    note="small trigger ~1.3-2 km/h; NOT the peak-slip limit"))
    # speed-term (g) vs vref
    stv = [(v, eval_curve(st, v*100)/100.0) for v in range(0, 301, 2)]
    figs.append(svg("ABS speed-term [var%d] (decel threshold deepen)" % variant,
                    "vref (km/h)", "term (g)", [("g", "var(--a)", stv)], 300,
                    min(0, min(y for _, y in stv)*1.1), max(0.1, max(y for _, y in stv))))
    # g-term (g) vs |decel|
    gtv = [(d, eval_curve(gt, d*100)/100.0) for d in [i/50.0 for i in range(0, 101)]]
    figs.append(svg("ABS g-term [var%d] (decel threshold vs decel)" % variant,
                    "|decel| (g)", "term (g)", [("g", "var(--b)", gtv)], 2.0,
                    min(0, min(y for _, y in gtv)*1.1), max(0.1, max(y for _, y in gtv))))
    # cornering lateral-g pressure term (bar) vs |lateral g| — curve output == bar directly
    latA = load_curve(buf, LAT_A); latB = load_curve(buf, LAT_B)
    la = [(cnt/100.0, eval_curve(latA, cnt)) for cnt in range(0, 131, 2)]
    lb = [(cnt/100.0, eval_curve(latB, cnt)) for cnt in range(0, 131, 2)]
    ymax = max(60, max(y for _, y in la)*1.15, max(y for _, y in lb)*1.15)
    figs.append(svg("ABS cornering lateral-g pressure term", "|lateral accel| (g)", "pressure term (bar)",
                    [("A 0x40E0A", "var(--a)", la), ("B 0x40E26", "var(--b)", lb)], 1.3, 0, ymax,
                    note="RISES with g (lateral-load term, NOT a knockdown); A +5 bar >0.8 g; role ceiling/ref UNCONFIRMED"))
    return figs

HTML = """<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>MK60E5 ABS Curves</title><style>
:root{--bg:#f7f7f5;--fg:#1a1a1a;--mut:#666;--grid:#ddd;--a:#c0392b;--b:#2471a3;--card:#fff}
@media(prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#15171a;--fg:#e8e8e8;--mut:#9aa;--grid:#333;--a:#ff6b5e;--b:#5aa9e6;--card:#1e2126;color-scheme:dark}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,sans-serif;padding:20px 16px}
h1{font-size:18px;margin:0 0 4px}.sub{color:var(--mut);margin:0 0 18px;font-size:13px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%%,620px),1fr));gap:20px;max-width:1360px;margin:0 auto}
figure{margin:0;background:var(--card);border:1px solid var(--grid);border-radius:10px;padding:12px}
.t{fill:var(--fg);font-size:17px;font-weight:600}.ax{stroke:var(--fg);stroke-width:1.3}
.gr{stroke:var(--grid);stroke-width:1}.yl,.xl{fill:var(--mut);font-size:13px;text-anchor:end}
.xl{text-anchor:middle}.al{fill:var(--mut);font-size:14px;text-anchor:middle}
.lg{fill:var(--fg);font-size:14px}.nt{fill:var(--mut);font-size:12px}
</style></head><body>
<h1>MK60E5 ABS curves &mdash; %(src)s</h1>
<p class="sub">variant %(variant)d &middot; firmware evaluator y = clamp(c[i] + (x&middot;k[i])&gt;&gt;10)</p>
<div class="grid">%(figs)s</div></body></html>"""

def main():
    ap = argparse.ArgumentParser(description="Plot MK60E5 ABS curves to HTML")
    ap.add_argument("--in", dest="img", default=DEFAULT_IMG)
    ap.add_argument("--yaml", help="apply this cal YAML in-memory before plotting")
    ap.add_argument("--variant", type=int, default=0, help="coding variant 0..11 for speed/g term")
    ap.add_argument("--out", default="cal_plot.html")
    a = ap.parse_args()
    src = os.path.basename(a.img)
    if a.yaml:
        tmp = tempfile.mktemp(suffix=".bin")
        r = subprocess.run([sys.executable, os.path.join(HERE, "cal_yaml.py"),
                            "--in", a.img, "apply", a.yaml, "--out", tmp],
                           capture_output=True, text=True)
        if r.returncode != 0:
            sys.exit("cal_yaml apply failed:\n" + r.stdout + r.stderr)
        buf = bytearray(open(tmp, "rb").read()); os.remove(tmp)
        src = os.path.basename(a.yaml)
    else:
        buf = bytearray(open(a.img, "rb").read())
    figs = build(buf, a.variant)
    open(a.out, "w", encoding="utf-8").write(
        HTML % {"src": src, "variant": a.variant, "figs": "".join("<figure>%s</figure>" % f for f in figs)})
    print("wrote %s" % a.out)

if __name__ == "__main__":
    main()
