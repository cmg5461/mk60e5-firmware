#!/usr/bin/env python
"""extract_flashplan.py - reconstruct the complete MK60E5 flash plan (erase
params + ordered download segments with their data) from a real WinKFP flash
CAN log, and emit a portable flash-plan the flasher can replay.

The log is a decimal Kvaser capture (Chn Identifier DLC D0..D7 Time Dir).
Diagnostic CAN ids: tester 0x6F1 (1777), ECU 0x629 (1577). BMW byte-0 ISO-TP
(byte0 = addr ext, byte1 = PCI). We reassemble the tester->ECU KWP2000 stream
and pull every RequestDownload(0x34)/TransferData(0x36)/RequestTransferExit(0x37)
plus the erase routine (0x31 02) and the finalize routines.

Output (default flash/plan/<name>/):
  plan.json  - erase params, ordered segment list (addr/fmt/size/offset/len),
               and the finalize/reset routine bytes, all as hex.
  data.bin   - concatenated segment payloads; each segment's `offset`/`len`
               index into this blob.

Usage:
  python tools/extract_flashplan.py <flash_can_log.txt> [--name m3_stock]
                                     [--outdir flash/plan]
"""
import argparse
import json
import os
import sys

TESTER, ECU = 1777, 1577


def rows(path):
    with open(path) as fh:
        for ln in fh:
            p = ln.split()
            if len(p) < 4 or p[0] != "0":
                continue
            try:
                cid, dlc = int(p[1]), int(p[2])
            except (ValueError, IndexError):
                continue
            if cid not in (TESTER, ECU):
                continue
            data = []
            for tok in p[3:]:
                if "." in tok:
                    break
                data.append(int(tok))
            yield cid, data[:dlc]


class IsoTpReasm:
    """BMW byte-0 ISO-TP reassembly (one direction)."""
    def __init__(self):
        self.buf, self.need = [], 0

    def feed(self, data):
        if len(data) < 2:
            return None
        pci = data[1]
        typ = pci >> 4
        if typ == 0:                      # single frame
            return bytes(data[2:2 + (pci & 0xF)])
        if typ == 1:                      # first frame
            self.need = ((pci & 0xF) << 8) | data[2]
            self.buf = list(data[3:])
            return None
        if typ == 2:                      # consecutive
            self.buf += data[2:]
            if len(self.buf) >= self.need:
                return bytes(self.buf[:self.need])
        return None                       # flow control / incomplete


def reassemble(path):
    """Yield ('TX'|'RX', kwp_message_bytes) in order."""
    tx, rx = IsoTpReasm(), IsoTpReasm()
    for cid, data in rows(path):
        r = (tx if cid == TESTER else rx).feed(data)
        if r:
            yield ("TX" if cid == TESTER else "RX"), r


def build_plan(path):
    msgs = list(reassemble(path))
    erase = None
    segments = []           # dicts: addr, fmt, size, data(bytearray)
    finalize = []           # raw tester routine/reset msgs after last segment
    cur = None              # current open segment
    seen_first_download = False
    last_exit_idx = -1

    for i, (d, m) in enumerate(msgs):
        if d != "TX" or not m:
            continue
        s = m[0]
        if s == 0x31 and len(m) >= 2 and m[1] == 0x02 and erase is None:
            # erase: 31 02 <addr:3> <fmt:1> <size:3>
            erase = m[2:]
        elif s == 0x34:
            # 34 <addr:3> <fmt:1> <size:4>
            addr = int.from_bytes(m[1:4], "big")
            fmt = m[4]
            size = int.from_bytes(m[5:9], "big")
            cur = {"addr": addr, "fmt": fmt, "size": size, "data": bytearray()}
            segments.append(cur)
            seen_first_download = True
        elif s == 0x36 and cur is not None:
            cur["data"] += m[1:]
        elif s == 0x37 and cur is not None:
            cur = None
            last_exit_idx = i
        elif seen_first_download and cur is None and s in (0x31, 0x11, 0x29, 0x28):
            if i > last_exit_idx:
                finalize.append(m.hex())

    return erase, segments, finalize


def main():
    ap = argparse.ArgumentParser(description="reconstruct MK60E5 flash plan from a WinKFP CAN log")
    ap.add_argument("log")
    ap.add_argument("--name", default="stock")
    ap.add_argument("--outdir", default=os.path.join("flash", "plan"))
    args = ap.parse_args()

    erase, segments, finalize = build_plan(args.log)

    print("erase routine 31 02 : %s" % (erase.hex() if erase else "NONE"))
    if erase and len(erase) >= 7:
        print("  start=0x%06X fmt=0x%02X total=0x%06X (%d bytes)"
              % (int.from_bytes(erase[0:3], "big"), erase[3],
                 int.from_bytes(erase[4:7], "big"),
                 int.from_bytes(erase[4:7], "big")))
    print("segments            : %d" % len(segments))
    total = 0
    ok = True
    for n, s in enumerate(segments):
        match = "OK" if len(s["data"]) == s["size"] else "*** SIZE MISMATCH ***"
        if len(s["data"]) != s["size"]:
            ok = False
        total += len(s["data"])
        print("  [%2d] addr=0x%06X fmt=0x%02X size=0x%X (%d)  data=%d  %s"
              % (n, s["addr"], s["fmt"], s["size"], s["size"], len(s["data"]), match))
    print("total programmed    : %d bytes (0x%X)" % (total, total))
    print("finalize msgs       : %s" % " ".join(finalize))
    if not ok:
        print("WARNING: segment size mismatch - do not flash this plan")

    outdir = os.path.join(args.outdir, args.name)
    os.makedirs(outdir, exist_ok=True)
    blob = bytearray()
    seg_meta = []
    for s in segments:
        off = len(blob)
        blob += s["data"]
        seg_meta.append({"addr": s["addr"], "fmt": s["fmt"], "size": s["size"],
                         "offset": off, "len": len(s["data"])})
    plan = {
        "name": args.name,
        "source_log": os.path.basename(args.log),
        "erase": erase.hex() if erase else None,
        "max_block": 0xFC,
        "segments": seg_meta,
        "finalize": finalize,
    }
    with open(os.path.join(outdir, "plan.json"), "w") as fh:
        json.dump(plan, fh, indent=2)
    with open(os.path.join(outdir, "data.bin"), "wb") as fh:
        fh.write(blob)
    print("wrote %s  (plan.json + data.bin, %d bytes)" % (outdir, len(blob)))


if __name__ == "__main__":
    main()
