"""Convert BMW WinKFP flash files (.0pa / .0da) to raw binaries.

The files are Intel HEX with a few BMW extensions:
  - leading '$'/';' header lines ($REFERENZ, $CHECKSUMME, ...)
  - record type 0x10: a normal data record that marks the end of a block

Outputs, next to each other in the output directory:
  <name>_<base>.bin    one image per address region (data separated by >= 1 MiB of nothing
                       starts a new region); each region is aligned to 64 KiB so file
                       offset + base = address; gaps filled with 0xFF
  <name>_segments.txt  header lines, regions written, and contiguous address ranges
"""
import argparse
import pathlib
import sys

FILL = 0xFF
ALIGN = 0x10000
MERGE_GAP = 0x100000


def parse(path):
    header = []
    data = {}
    upper = 0
    line_no = 0
    for raw in path.read_bytes().splitlines():
        line_no += 1
        line = raw.decode("ascii", "replace").strip()
        if not line:
            continue
        if not line.startswith(":"):
            header.append(line)
            continue
        rec = bytes.fromhex(line[1:])
        count, addr, rtype = rec[0], int.from_bytes(rec[1:3], "big"), rec[3]
        payload = rec[4:4 + count]
        if len(rec) != count + 5:
            sys.exit(f"{path}:{line_no}: length mismatch")
        if sum(rec) & 0xFF:
            sys.exit(f"{path}:{line_no}: bad checksum")
        if rtype in (0x00, 0x10):
            base = upper + addr
            for i, b in enumerate(payload):
                a = base + i
                if a in data and data[a] != b:
                    sys.exit(f"{path}:{line_no}: conflicting data at 0x{a:08X}")
                data[a] = b
        elif rtype == 0x02:  # extended segment address
            upper = (upper & 0xFFFF0000) | (int.from_bytes(payload, "big") << 4)
        elif rtype == 0x04:  # extended linear address
            upper = int.from_bytes(payload, "big") << 16
        elif rtype == 0x01:
            break
        else:
            sys.exit(f"{path}:{line_no}: unknown record type 0x{rtype:02X}")
    return header, data


def crc16_arc(data):
    """CRC-16/ARC (poly 0x8005 reflected, init 0, xorout 0): the .0pa $CHECKSUMME value,
    computed over all data bytes in address order."""
    crc = 0
    for b in data:
        crc ^= b
        for _ in range(8):
            crc = (crc >> 1) ^ 0xA001 if crc & 1 else crc >> 1
    return crc


def ranges(addrs):
    out = []
    for a in sorted(addrs):
        if out and a == out[-1][1] + 1:
            out[-1][1] = a
        else:
            out.append([a, a])
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", type=pathlib.Path)
    ap.add_argument("-o", "--outdir", type=pathlib.Path, default=pathlib.Path("."))
    args = ap.parse_args()
    args.outdir.mkdir(parents=True, exist_ok=True)

    for path in args.files:
        header, data = parse(path)
        rs = ranges(data)
        regions = []
        for start, end in rs:
            if regions and start - regions[-1][1] < MERGE_GAP:
                regions[-1][1] = end
            else:
                regions.append([start, end])

        crc = crc16_arc(bytes(data[a] for a in sorted(data)))
        declared = next((l.split()[1] for l in header if l.startswith("$CHECKSUMME")), None)
        status = "no $CHECKSUMME" if declared is None else (
            "OK" if int(declared, 16) == crc else f"MISMATCH (header {declared})")
        print(f"{path.name}: CRC-16/ARC {crc:04X} {status}")

        stem = path.stem
        lines = [f"source: {path}", *header, "", f"{len(data)} bytes defined, fill 0x{FILL:02X}",
                 f"CRC-16/ARC over data in address order: {crc:04X} ({status})", "",
                 "regions (file, base, size)"]
        for start, end in regions:
            base = start // ALIGN * ALIGN
            size = -(-(end + 1 - base) // ALIGN) * ALIGN
            image = bytearray([FILL]) * size
            for a, b in data.items():
                if base <= a < base + size:
                    image[a - base] = b
            name = f"{stem}_{base:08X}.bin"
            (args.outdir / name).write_bytes(image)
            lines.append(f"  {name}  0x{base:08X}  0x{size:X}")

        lines += ["", "start       end         length"]
        lines += [f"0x{s:08X}  0x{e:08X}  0x{e - s + 1:X}" for s, e in rs]
        (args.outdir / f"{stem}_segments.txt").write_text("\n".join(lines) + "\n")
        print(f"{path.name}: {len(rs)} ranges in {len(regions)} regions")


if __name__ == "__main__":
    main()
