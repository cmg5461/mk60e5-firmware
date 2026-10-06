#!/usr/bin/env python3
"""
bmy_resign.py  -  recompute the integrity data in an MK60E5 DSC image.

For static reverse-engineering of the owner's own E82 1M / E9x M3 DSC firmware.
After editing the application region of a flat image, two integrity values no
longer match and the image would be rejected:
  1. the in-ECU ROM self-test MISR words (hardware signature unit 0xD50200), and
  2. the trailing BMY block's 512-bit RSA signature (checked by the bootloader).
This tool recomputes both. The MISR words lie INSIDE the region the BMY signature
hashes, so a full fix must recompute the MISR words FIRST, then the BMY signature.

--- BMY signature (verified byte-exact against stock 7846411A and 7846816A) ---
    H = reverse( MD5( image[HASH_START : BMY_start] ) )     # 128-bit, MD5 read little-endian
    m = 0x00 * 48  ||  H                                     # 512-bit message, no PKCS#1 padding
    s = m ^ d (mod n)                                        # raw RSA, 512-bit key, e = 7
    stored as sixteen 32-bit words, big-endian within each word, in REVERSE word
    order (least-significant limb first in memory).

--- ROM self-test MISR (verified: reproduces all three stored words) ---
    32-bit word-wise MISR (poly 0x00400007), seed 0, no final XOR / no reflection.
    For each big-endian 32-bit word w of a range, ascending:
        s = ((s << 1) ^ (0x00400007 if (s>>31)&1 else 0)) & 0xFFFFFFFF   # LFSR step first
        s ^= w                                                           # then xor the word
    Range table at CPU 0xD7584: three {start, end} pairs (BE u32, end exclusive).
    The expected value for each range is the BE u32 stored AT its end address.

  Addressing: in these flat .bin images, bin offset = CPU address + 0x8000.
  HASH_START = 0x48000 == CPU 0x40000 (first byte after the 0x0-0x47FFF bootloader).

Usage:
    python tools/bmy_resign.py fix     <image.bin> [-o out.bin] [-k rsa-sig.json]
    python tools/bmy_resign.py sign    <image.bin> [-o out.bin] [-k rsa-sig.json]   # BMY only
    python tools/bmy_resign.py misr    <image.bin> [-o out.bin]                     # MISR only
    python tools/bmy_resign.py verify  <image.bin> [-k rsa-sig.json]
    python tools/bmy_resign.py selftest <stock1.bin> [stock2.bin ...]

`fix`     : recompute MISR words then BMY signature (the full, consistent pass).
`sign`    : BMY signature only.  `misr`: MISR words only.
`verify`  : report MISR-word and BMY-signature validity (public key only).
`selftest`: re-fix each stock image and confirm nothing changes (encoder proof).
"""
import sys, os, json, struct, hashlib, argparse

CPU_TO_BIN     = 0x8000       # bin offset = CPU address + 0x8000
HASH_START     = 0x48000      # == CPU 0x40000; start of the BMY-signed application region
MARKER         = b'BMY\x01'
SIG_OFFSET     = 12           # bytes from the BMY marker to the 64 signature bytes
SIG_LEN        = 64
MISR_POLY      = 0x00400007
MISR_TABLE_CPU = 0xD7584      # three 8-byte {start,end} entries, BE u32, end exclusive
MISR_N_RANGES  = 3


# ---------- key ----------
def load_key(path):
    cfg = json.load(open(path))
    n = int(cfg['modulus_hex'], 16)
    e = int(cfg['public_exponent'])
    d = int(cfg['private_exponent_hex'], 16) if cfg.get('private_exponent_hex') else None
    return n, e, d


# ---------- BMY signature ----------
def find_bmy(data):
    off = data.find(MARKER)
    if off < 0:
        raise ValueError("no BMY\\x01 marker found")
    sig_at = off + SIG_OFFSET
    if sig_at + SIG_LEN > len(data):
        raise ValueError("BMY block runs past end of image")
    return off, sig_at


def app_digest(data, bmy_start):
    """H = reverse(MD5(app region)) -> 16 bytes, as embedded in the RSA plaintext."""
    return hashlib.md5(data[HASH_START:bmy_start]).digest()[::-1]


def message_int(h16):
    """m = 0x00*48 || H  (big-endian 512-bit integer)."""
    return int.from_bytes(b'\x00' * 48 + h16, 'big')


def encode_sig(s):
    """integer s -> 64 stored bytes: 16 big-endian u32 words, least-significant word first."""
    return b''.join(struct.pack('>I', (s >> (32 * i)) & 0xFFFFFFFF) for i in range(16))


def decode_sig(sig):
    """64 stored bytes -> integer s (inverse of encode_sig)."""
    words = struct.unpack('>16I', sig)
    return sum(w << (32 * i) for i, w in enumerate(words))


def sign_image(data, n, e, d):
    """Return (new bytearray, H, new 64-byte sig) with a corrected BMY signature."""
    if d is None:
        raise ValueError("key file has no private_exponent_hex; cannot sign")
    bmy_start, sig_at = find_bmy(data)
    h16 = app_digest(data, bmy_start)
    m = message_int(h16)
    if m >= n:
        raise ValueError("message >= modulus; wrong key or corrupt digest")
    s = pow(m, d, n)
    new_sig = encode_sig(s)
    if pow(decode_sig(new_sig), e, n) != m:          # self-check
        raise AssertionError("internal: produced signature does not verify")
    out = bytearray(data)
    out[sig_at:sig_at + SIG_LEN] = new_sig
    return out, h16, new_sig


def verify_bmy(data, n, e):
    """Return (is_valid, recovered_digest_or_None)."""
    bmy_start, sig_at = find_bmy(data)
    s = decode_sig(data[sig_at:sig_at + SIG_LEN])
    if s >= n:
        return False, None
    recovered = pow(s, e, n).to_bytes(64, 'big')
    expected = message_int(app_digest(data, bmy_start)).to_bytes(64, 'big')
    return recovered == expected, recovered[48:]


# ---------- ROM self-test MISR ----------
def misr(data):
    """32-bit word-wise MISR over big-endian words of `data` (length must be a multiple of 4)."""
    if len(data) % 4:
        raise ValueError("MISR range length not a multiple of 4")
    s = 0
    for i in range(0, len(data), 4):
        w = (data[i] << 24) | (data[i+1] << 16) | (data[i+2] << 8) | data[i+3]
        s = ((s << 1) ^ (MISR_POLY if (s >> 31) & 1 else 0)) & 0xFFFFFFFF
        s ^= w
    return s


def find_misr_table(data):
    """Locate the MISR range table. The first entry's start is the application base
    (CPU 0x40000); entries are ascending and in-bounds. Falls back to MISR_TABLE_CPU.
    (1M: 0xD7584; M3: 0xD71F4 -- the cal blocks are larger, so the table moved.)"""
    base = MISR_TABLE_CPU + CPU_TO_BIN
    if base + 4 <= len(data) and struct.unpack('>I', data[base:base + 4])[0] == 0x40000:
        return MISR_TABLE_CPU
    for cpu in range(0xD0000, 0xE0000, 4):
        o = cpu + CPU_TO_BIN
        if o + 8 * MISR_N_RANGES > len(data):
            break
        try:
            starts = [struct.unpack('>I', data[o + 8 * i:o + 8 * i + 4])[0] for i in range(MISR_N_RANGES)]
            ends = [struct.unpack('>I', data[o + 8 * i + 4:o + 8 * i + 8])[0] for i in range(MISR_N_RANGES)]
        except struct.error:
            continue
        if starts[0] == 0x40000 and starts[1] < starts[2] < ends[2] < 0x100000 \
           and all(0 < s < e for s, e in zip(starts, ends)):
            return cpu
    return MISR_TABLE_CPU  # fall back; the sanity checks below will report if it is wrong


def read_misr_ranges(data):
    """Read the three {start_cpu, end_cpu} range pairs from the on-image table."""
    base = find_misr_table(data) + CPU_TO_BIN
    ranges = []
    for i in range(MISR_N_RANGES):
        start_cpu, end_cpu = struct.unpack('>II', data[base + 8*i: base + 8*i + 8])
        sb, eb = start_cpu + CPU_TO_BIN, end_cpu + CPU_TO_BIN
        # sanity: aligned, ordered, in-bounds, and result word has room
        if (start_cpu % 4) or (end_cpu % 4) or not (0 < start_cpu < end_cpu) \
           or eb + 4 > len(data) or sb >= len(data):
            raise ValueError(f"MISR range {i} looks wrong: start={start_cpu:#x} end={end_cpu:#x} "
                             f"(wrong table offset or not an MK60E5 image?)")
        ranges.append((start_cpu, end_cpu))
    # no range may contain another range's stored result word (else a fixpoint problem)
    for _, e_cpu in ranges:
        rb = e_cpu + CPU_TO_BIN
        for s2, e2 in ranges:
            if (s2 + CPU_TO_BIN) <= rb < (e2 + CPU_TO_BIN):
                raise ValueError("a MISR result word falls inside a MISR range; unexpected layout")
    return ranges


def fix_misr(data):
    """Recompute and write all three MISR result words. Returns (new bytearray, changes)."""
    out = bytearray(data)
    changes = []
    for start_cpu, end_cpu in read_misr_ranges(out):
        sb, eb = start_cpu + CPU_TO_BIN, end_cpu + CPU_TO_BIN
        val = misr(out[sb:eb])
        old = struct.unpack('>I', out[eb:eb + 4])[0]
        out[eb:eb + 4] = struct.pack('>I', val)
        changes.append((start_cpu, end_cpu, old, val))
    return out, changes


def verify_misr(data):
    """Return list of (start_cpu, end_cpu, computed, stored, ok)."""
    res = []
    for start_cpu, end_cpu in read_misr_ranges(data):
        sb, eb = start_cpu + CPU_TO_BIN, end_cpu + CPU_TO_BIN
        computed = misr(data[sb:eb])
        stored = struct.unpack('>I', data[eb:eb + 4])[0]
        res.append((start_cpu, end_cpu, computed, stored, computed == stored))
    return res


# ---------- combined ----------
def fix_image(data, n, e, d):
    """MISR words first (they are inside the hashed region), then the BMY signature."""
    out, misr_changes = fix_misr(data)
    out, h16, new_sig = sign_image(out, n, e, d)
    return out, misr_changes, h16, new_sig


# ---------- CLI ----------
def _write(dst, out):
    open(dst, 'wb').write(out)


def main():
    ap = argparse.ArgumentParser(description="Recompute MK60E5 MISR words and the BMY RSA signature.")
    sub = ap.add_subparsers(dest='cmd', required=True)
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    default_key = os.path.join(here, 'rsa-sig.json')

    for name in ('fix', 'sign'):
        p = sub.add_parser(name); p.add_argument('image'); p.add_argument('-o', '--out'); p.add_argument('-k', '--key', default=default_key)
    p = sub.add_parser('misr');     p.add_argument('image'); p.add_argument('-o', '--out')
    p = sub.add_parser('verify');   p.add_argument('image'); p.add_argument('-k', '--key', default=default_key)
    p = sub.add_parser('selftest'); p.add_argument('images', nargs='+'); p.add_argument('-k', '--key', default=default_key)
    a = ap.parse_args()

    if a.cmd == 'verify':
        n, e, _ = load_key(a.key)
        data = open(a.image, 'rb').read()
        print(f"{a.image}:")
        all_ok = True
        for s_cpu, e_cpu, comp, stored, ok in verify_misr(data):
            all_ok &= ok
            print(f"  MISR [{s_cpu:#07x},{e_cpu:#07x}) stored={stored:08X} computed={comp:08X}  {'OK' if ok else 'MISMATCH'}")
        ok, dig = verify_bmy(data, n, e)
        all_ok &= ok
        print(f"  BMY signature: {'VALID' if ok else 'INVALID'}"
              + (f"  (app MD5-rev = {dig.hex()})" if dig is not None else "  (s >= n)"))
        return 0 if all_ok else 1

    if a.cmd == 'misr':
        data = open(a.image, 'rb').read()
        out, changes = fix_misr(data)
        dst = a.out or a.image
        _write(dst, out)
        print(f"MISR-fixed {a.image} -> {dst}")
        for s_cpu, e_cpu, old, new in changes:
            print(f"  [{s_cpu:#07x},{e_cpu:#07x}) {old:08X} -> {new:08X}"
                  + ("  (unchanged)" if old == new else ""))
        return 0

    if a.cmd in ('fix', 'sign'):
        n, e, d = load_key(a.key)
        data = open(a.image, 'rb').read()
        if a.cmd == 'sign':
            out, h16, new_sig = sign_image(data, n, e, d)
            misr_changes = None
        else:
            out, misr_changes, h16, new_sig = fix_image(data, n, e, d)
        dst = a.out or a.image
        _write(dst, out)
        print(f"{a.cmd} {a.image} -> {dst}")
        if misr_changes is not None:
            for s_cpu, e_cpu, old, new in misr_changes:
                print(f"  MISR [{s_cpu:#07x},{e_cpu:#07x}) {old:08X} -> {new:08X}"
                      + ("  (unchanged)" if old == new else ""))
        bmy_start, _ = find_bmy(data)
        print(f"  app region [{HASH_START:#07x},{bmy_start:#07x})  MD5-rev = {h16.hex()}")
        print(f"  BMY signature = {new_sig.hex()}")
        # confirm what we wrote is fully consistent
        chk = open(dst, 'rb').read()
        mok = all(r[4] for r in verify_misr(chk))
        bok, _ = verify_bmy(chk, n, e)
        print(f"  post-write verify: MISR {'OK' if mok else 'FAIL'}, BMY {'VALID' if bok else 'FAIL'}")
        return 0 if (mok and bok) else 1

    if a.cmd == 'selftest':
        n, e, d = load_key(a.key)
        all_ok = True
        for img in a.images:
            data = open(img, 'rb').read()
            _, sig_at = find_bmy(data)
            orig_sig = data[sig_at:sig_at + SIG_LEN]
            orig_misr = [struct.unpack('>I', data[c + CPU_TO_BIN:c + CPU_TO_BIN + 4])[0]
                         for _, c in read_misr_ranges(data)]
            out, misr_changes, _, new_sig = fix_image(data, n, e, d)
            new_misr = [c[3] for c in misr_changes]
            sig_match = new_sig == orig_sig
            misr_match = new_misr == orig_misr
            all_ok &= sig_match and misr_match
            print(f"{img}: MISR reproduces stock: {misr_match}; BMY reproduces stock: {sig_match}")
            if not sig_match:
                print(f"   sig orig={orig_sig.hex()}\n   sig new ={new_sig.hex()}")
            if not misr_match:
                print(f"   misr orig={[f'{v:08X}' for v in orig_misr]} new={[f'{v:08X}' for v in new_misr]}")
        return 0 if all_ok else 1


if __name__ == '__main__':
    sys.exit(main())
