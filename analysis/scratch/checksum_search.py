"""Search for the .0pa $CHECKSUMME algorithm: a candidate must reproduce both files' values."""
import itertools
import pathlib
import sys

sys.path.insert(0, "tools")
import bmw_hex2bin as h  # noqa: E402

FILES = {"7846411A": ("flash/src/DSCM80/7846411A.0pa", 0x850F),
         "7846816A": ("flash/src/DSCM90/7846816A.0pa", 0x0536)}
POLYS = (0x1021, 0x8005, 0x3D65, 0x8BB7, 0xA097, 0x0589, 0xC867, 0x2F15, 0x6F63, 0x5935, 0x755B, 0x1DCF)


def views(path):
    _, data = h.parse(pathlib.Path(path))
    addrs = sorted(data)
    main = [a for a in addrs if a < 0x100000]
    out = {
        "defined": bytes(data[a] for a in addrs),
        "main_defined": bytes(data[a] for a in main),
        "app_defined": bytes(data[a] for a in main if a >= 0x48000),
        "main_span_ff": bytes(data.get(a, 0xFF) for a in range(main[0], main[-1] + 1)),
    }
    recs = []
    for line in pathlib.Path(path).read_bytes().splitlines():
        line = line.strip()
        if line.startswith(b":"):
            recs.append(bytes.fromhex(line[1:].decode()))
    out["records_all"] = b"".join(recs)
    out["record_cksums"] = bytes(r[-1] for r in recs)
    return out


_tables = {}


def _rev(v, n):
    return int(f"{v:0{n}b}"[::-1], 2)


def _table(poly, refl):
    if (poly, refl) not in _tables:
        t = []
        for i in range(256):
            if refl:
                c, rp = i, _rev(poly, 16)
                for _ in range(8):
                    c = (c >> 1) ^ rp if c & 1 else c >> 1
            else:
                c = i << 8
                for _ in range(8):
                    c = ((c << 1) ^ poly) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
            t.append(c)
        _tables[(poly, refl)] = t
    return _tables[(poly, refl)]


def crc16(data, poly, init, refl, xorout):
    t, crc = _table(poly, refl), init
    if refl:
        for b in data:
            crc = (crc >> 8) ^ t[(crc ^ b) & 0xFF]
    else:
        for b in data:
            crc = ((crc << 8) & 0xFFFF) ^ t[((crc >> 8) ^ b) & 0xFF]
    return crc ^ xorout


def simple(data):
    s = sum(data)
    wb = sum(int.from_bytes(data[i:i + 2], "big") for i in range(0, len(data) - 1, 2))
    wl = sum(int.from_bytes(data[i:i + 2], "little") for i in range(0, len(data) - 1, 2))
    x = 0
    for i in range(0, len(data) - 1, 2):
        x ^= int.from_bytes(data[i:i + 2], "big")
    return {"sum8": s & 0xFFFF, "~sum8": ~s & 0xFFFF, "-sum8": -s & 0xFFFF,
            "sumw_be": wb & 0xFFFF, "~sumw_be": ~wb & 0xFFFF, "-sumw_be": -wb & 0xFFFF,
            "sumw_le": wl & 0xFFFF, "xorw_be": x}


def main():
    assert crc16(b"123456789", 0x1021, 0xFFFF, False, 0) == 0x29B1
    assert crc16(b"123456789", 0x8005, 0, True, 0) == 0xBB3D
    V = {k: views(p) for k, (p, _) in FILES.items()}
    want = {k: c for k, (_, c) in FILES.items()}
    hits = []
    for view in V["7846411A"]:
        sv = {k: simple(V[k][view]) for k in V}
        hits += [(view, n) for n in sv["7846411A"] if all(sv[k][n] == want[k] for k in V)]
        for poly, init, refl, xo in itertools.product(POLYS, (0, 0xFFFF), (False, True), (0, 0xFFFF)):
            if crc16(V["7846411A"][view], poly, init, refl, xo) == want["7846411A"]:
                if crc16(V["7846816A"][view], poly, init, refl, xo) == want["7846816A"]:
                    hits.append((view, f"crc16 poly={poly:#06x} init={init:#06x} refl={refl} xor={xo:#06x}"))
        print(view, "done", flush=True)
    print("HITS:", hits)


if __name__ == "__main__":
    main()
