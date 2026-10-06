# MK60E5 M-car DSC firmware notes

## Sources
| Car | WinKFP family | ZB / file | Flash procedure |
|---|---|---|---|
| E9x M3 | DSCM90 | 7846816A.0pa | 080100DSC81.ipo (per E85_v74 KFCONF10.DA2) |
| E82 1M | DSCM80 | 7846411A.0pa | 080100DSC81.ipo |

Originals in `flash/src/`, from `Desktop\inpa\Daten\E89\E89\data`. Converted with
`tools/bmw_hex2bin.py` (Intel HEX + BMW type-0x10 end-of-block records; every record checksum
verified, round-trip compared). Header `$CHECKSUMME` algorithm not identified (not a 16-bit sum).

## CPU: Motorola/Freescale M*CORE, big-endian, 16-bit instructions
Physical chip: Freescale with ATE logo (Continental Teves custom part); exact part number TBD.

Evidence (1M image):
- GCC-style frames: 1264x `subi r0,N ; stm rX-r15,(r0)` and `ldm rX-r15,(r0) ; addi r0,N ; jmp r15`
- `jmp r15` (0x00CF, return) is the 3rd most common halfword
- Ruled out: ARM/Thumb either endianness, PowerPC classic and VLE (no r1 frames), SH/SH-2A,
  ColdFire, H8S, FR, TriCore, V850, C166

## Address map (1M, 7846411A)
- `.0pa` addresses are **0x8000 above CPU addresses** for the application block:
  jsri literal targets land on function starts only with this correction
  (1031/1647 directly after `jmp r15`, vs 9 without).
  File 0x48000-0xFE78B = CPU 0x40000-0xF678B.
- RAM referenced at 0x0040_0000+ (e.g. 0x00408Dxx variables).
- File 0x3AC-0x8EF: small position-independent routine (addresses relative to r8);
  dispatches on a command code, masks with 0x000FFFFF, touches 0x00F60000 -- looks like a
  flash-driver style helper. Not affected by the 0x8000 offset question (PIC).
- File 0xDF812C-0xDF84AF: small scattered blocks; differ from M3 in only 12 bytes.
- File 0xFFFF00-0xFFFF07: `00 01 02 03 04 05 06 07`, identical in M3 and 1M.

## Listings
`tools/mcore_dis.py` (opcode table from binutils mcore-opc.h). Linear sweep, so data tables
also decode as instructions. Labels are jsri targets, prologue sites, and bsr targets that look
like function starts.

    python tools/mcore_dis.py flash/bin/7846411A_00000000.bin --base=-0x8000 --start 0x40000 --end 0xF678C

- `7846411A_main.lst` -- application, CPU addresses
- `7846411A_lowblock.lst` -- 0x3AC block, file addresses
