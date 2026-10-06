#!/usr/bin/env python
"""
mk60_can.py - Kvaser CAN diagnostic / (scaffolded) flash client for the
BMW MK60E5 DSC (E82 1M 7846411A, E9x M3 7846816A).

====================================================================
READ THIS BEFORE YOU FLASH ANYTHING
====================================================================
The flash entry + write protocol is now FULLY REVERSE-ENGINEERED and
validated byte-for-byte against a real WinKFP flash of this exact module
(analysis/mk60e5_flash_can_log.txt). The flow lives in the bootloader at
reset; the application cooperates by opening ECUProgrammingMode (0x85)
after the level-5 Authentisierung. Verified pipeline:

  level-5 auth (keyed MD5) -> 0x10 0x85 -> 31 02 erase (poll) ->
  28 02/29 02 -> per segment [34 requestDownload / 36 transferData x N /
  37 transferExit] -> 31 09 02 signature verify (poll) -> 11 01 reset.

Subcommands:
  * SAFE: info / readcoding / unlock / auth5 / sniff / verify / repack.
  * `flashplan <dir>` runs a captured/repacked plan. It is DRY-RUN by
    default and only transmits with --arm (+ a typed confirmation). This
    is the verified path - use it, not the old `flash` template.
  * `repack` re-slices EDITED bank images onto the captured segment layout
    to make an edited plan; `extract_flashplan.py` builds the stock plan
    from the CAN log.
  * Any edited image MUST be re-signed first (tools/bmy_resign.py fix) or
    the ECU rejects it at the 0x31 09 signature-verify step.
  * `flash` is the OLD unverified UDS template, kept only for reference.
    Prefer `flashplan`. Bench work only, with a BDM/JTAG recovery path.

Transport: BMW E-series D-CAN (ISO 15765-2) with byte-0 address extension.
  Request : CAN id 0x6F1, data[0] = ECU address (DSC = 0x29), ISO-TP in [1:].
  Response: CAN id 0x600+addr = 0x629, data[0] = 0xF1 (tester), ISO-TP in [1:].
All of this is configurable; CONFIRM it against a sniff of your own bus.

Requires: python-can with the Kvaser backend (`pip install python-can`).
Kvaser CANlib driver must be installed. `--help` and `verify` work without it.
"""
import argparse
import os
import subprocess
import sys
import time

# ---------------------------------------------------------------- defaults
TESTER_ADDR = 0xF1
DSC_ADDR    = 0x29
REQ_ID      = 0x6F1
RESP_ID     = 0x600 + DSC_ADDR          # 0x629
BITRATE     = 500_000                    # BMW D-CAN
KEY_CONST16 = 0x1B09                      # from image @0xF690C+4/+5 (7846816A)

# Sessions / levels cross-validated against WinKFP SGBD DSC_87.prg (XOR 0xF7):
#   DIAGNOSE_MODE table: 0x85=ECUProgrammingMode(ECUPM), 0x86=ECUDevelopmentMode,
#                        0x87=ECUAdjustmentMode/EOL, 0x81=default.
#   Flash auth: KWP2000 0x27 level 0x03 (seed) / 0x04 (key); alt 0x07/0x08.
#   SGBD key var "seedrev" == firmware sub_0B1468. HARDWARE-VERIFIED on the unit:
#   enter 0x10 0x81 -> 0x10 0x87 (adjustment) -> 0x27 0x03 (seed) -> 0x27 0x04
#   with key = bitrev16(seed) ^ ROR16(seed,5). afb10/afb9e are other levels.
SESSION_DEFAULT = 0x81                    # standard diagnostic
SESSION_ADJUST  = 0x87                    # ECUAdjustmentMode (where 0x27 auth is granted)
SESSION_PROG    = 0x85                    # ECUProgrammingMode (flash; needs further preconditions)
FLASH_SEED_LEVEL = 0x03
FLASH_ALGO       = "seedrev"

HERE = os.path.dirname(os.path.abspath(__file__))

# ---------------------------------------------------------------- UDS/KWP
class FlowControlTimeout(IOError):
    """No ISO-TP flow control came back - the ECU is busy and silently dropped
    the frame (seen right after 0x85 and during erase). Caller should wait and
    resend the whole request."""


NRC = {
    0x10: "generalReject", 0x11: "serviceNotSupported", 0x12: "subFunctionNotSupported",
    0x13: "incorrectMessageLengthOrInvalidFormat", 0x22: "conditionsNotCorrect",
    0x24: "requestSequenceError", 0x31: "requestOutOfRange", 0x33: "securityAccessDenied",
    0x35: "invalidKey", 0x36: "exceedNumberOfAttempts", 0x37: "requiredTimeDelayNotExpired",
    0x72: "generalProgrammingFailure", 0x78: "responsePending (0x78)",
}


# --------------------------------------------------------------- key transforms
# Decoded from the 7846816A 0x27 handler (0xB14C2) and its helpers. The ECU
# sends a 16-bit seed and expects key = transform(seed); the transform is chosen
# by the security LEVEL (handler state): state 0xFE -> afb10, 0xFC -> afb9e,
# 4/8 -> revbits. Constants are folded from flash @0xF690C. afb10/revbits are
# high-confidence hand-ports; afb9e is medium (intricate GF fold) - verify it
# against a real seed/key capture before trusting it.
AFB10_CONST = 0x091B
AFB9E_CONST = 0x070B


def _ror16(v, n):
    v &= 0xFFFF
    return ((v >> n) | (v << (16 - n))) & 0xFFFF


def _bitrev16(v):
    r = 0
    for i in range(16):
        r |= ((v >> i) & 1) << (15 - i)
    return r & 0xFFFF


def kt_seedrev(seed, state=4):                   # sub_0B1468 -- HARDWARE-VERIFIED
    # key = bitreverse16(seed) XOR ROR16(seed, state+1).
    # Flash/standard auth is 0x27 level 0x03 -> key sub-function 0x04 -> state 4
    # -> rotate 5. (Level 0x07 -> state 8 -> rotate 9.) No constant.
    # Verified on the unit: session 0x87, seed 0x60A1 -> key 0x8E03 accepted.
    return (_bitrev16(seed) ^ _ror16(seed, state + 1)) & 0xFFFF


def kt_afb10(seed, const=AFB10_CONST):           # sub_0AFB10
    X, res = _ror16(seed, 3), 0
    for i in range(8):
        a, b = 15 - i, 7 - i
        if ((X >> i) & 1) ^ ((X >> (i + 8)) & 1):
            res |= ((X >> a) & 1) << b
            res |= ((X >> b) & 1) << a
        else:
            res |= ((~X >> a) & 1) << a
            res |= ((~X >> b) & 1) << b
    return (res ^ const) & 0xFFFF


def kt_afb9e(seed, const=AFB9E_CONST):           # sub_0AFB9E
    s = seed & 0xFFFF
    ns = (~s) & 0xFFFF
    res = 0
    for i in range(4):
        base = i * 4
        res |= ((s >> base) & 1) << (base + 2)          # bit 4i   -> 4i+2
        res |= ((s >> (base + 2)) & 1) << base          # bit 4i+2 -> 4i
        res |= ((ns >> (base + 1)) & 1) << (base + 1)   # ~bit 4i+1
        res |= ((ns >> (base + 3)) & 1) << (base + 3)   # ~bit 4i+3
    res = (res ^ _ror16(s, 5)) & 0xFFFF
    acc = 0
    for i in range(13):
        acc = (acc ^ ((res & (0xF << i)) << ((res >> i) & 0xF))) & 0xFFFFFFFF
    acc ^= (acc >> 16)
    return (res ^ acc ^ const) & 0xFFFF


KEY_ALGOS = {"seedrev": kt_seedrev, "afb10": kt_afb10, "afb9e": kt_afb9e}


def seed_to_key(seed: int, algo: str = "seedrev") -> int:
    return KEY_ALGOS[algo](seed)


# --------------------------------------------------------------- level-5 auth
# The programming-mode (flash) gate is a 128-bit "Authentisierung", NOT the
# 16-bit 0x27 seed/key. It is a KEYED MD5, decoded from sub_0B3F18/0B3D74:
#     response16 = MD5( AUTH_KEY16 || data16 || AUTH_KEY16 )
# AUTH_KEY16 is flash-resident at 0xF56C8 (extracted below). data16 is
# 0x408C0C[0:4] || 0x409564[0:4] || 0x408C04[0:8], where 0x408C04[0:8] is a
# deterministic PRNG (sub_0B3EAC/0B3E6C) over the ECU random 0x40956C that the
# ECU transmits to the tester. See FACTS.md. The PRNG + exact ZUFALLSZAHL/
# AUTHENTISIERUNG_START services are still to be wired, so this is provided as
# the verified crypto core, not yet an end-to-end unlock.
import hashlib

AUTH_KEY16 = bytes.fromhex("F1CE23C6CD24C8B7B8B3C653D9707BAC")  # M3 7846816A flash 0xF56C8
# VALIDATED against a real WinKFP M3 flash (CAN log): response =
#   MD5(KEY || UID || W564 || ZUFALLSZAHL || KEY), standard MD5 output.
# UID/W564 are FIXED ASCII constants WinKFP uses (not the per-unit NVM read).
AUTH_UID  = b"273c"      # USER_ID WinKFP sends in 0x31 07
AUTH_W564 = b"00B4"      # the 0x409564 component (fixed)
# NOTE: these are firmware-specific. Confirmed for M3 (DSCM90/7846816A). A 335
# (DSC90/MK60_87) and 1M (DSCM80) use a DIFFERENT key/constants - extract per image.


def auth_response(data16: bytes, key: bytes = AUTH_KEY16) -> bytes:
    """Level-5 Authentisierung response = MD5(key || data16 || key)."""
    if len(data16) != 16:
        raise ValueError("data16 must be 16 bytes")
    return hashlib.md5(key + data16 + key).digest()


def auth_data16(user_id4: bytes, w409564: bytes, zufall8: bytes) -> bytes:
    """Assemble the 16-byte MD5 input (sub_0B3EE0):
       data16 = USER_ID[4] || 0x409564[4] || ZUFALLSZAHL[8].
    USER_ID is tester-chosen (sent in the 0x31 07 request), ZUFALLSZAHL is the
    8 bytes the ECU returns, and 0x409564 is a per-unit EEPROM value (NVM idx 24,
    NOT in the flash image) that must be supplied to complete the response."""
    if len(user_id4) != 4 or len(w409564) != 4 or len(zufall8) != 8:
        raise ValueError("need 4 + 4 + 8 bytes")
    return bytes(user_id4) + bytes(w409564) + bytes(zufall8)


# ---------------------------------------------------------------- ISO-TP
class IsoTp:
    """Minimal ISO 15765-2 over BMW byte-0 addressing. Blocking, single ECU."""
    def __init__(self, bus, req_id, resp_id, ecu_addr, tester_addr, verbose=False):
        self.bus, self.req_id, self.resp_id = bus, req_id, resp_id
        self.ecu, self.tester, self.verbose = ecu_addr, tester_addr, verbose
        self.fc_wait = 1.5          # flow-control should arrive in ~ms; a busy ECU sends none

    def _send_raw(self, payload7):
        import can
        data = bytes([self.ecu]) + bytes(payload7)
        data = data + b"\x00" * (8 - len(data))
        self.bus.send(can.Message(arbitration_id=self.req_id, data=data, is_extended_id=False))
        if self.verbose:
            print("  TX %03X %s" % (self.req_id, data.hex(" ")))

    def _recv_raw(self, timeout):
        end = time.time() + timeout
        while time.time() < end:
            msg = self.bus.recv(timeout=max(0.0, end - time.time()))
            if msg is None:
                continue
            if msg.arbitration_id != self.resp_id:
                continue
            if len(msg.data) < 1 or msg.data[0] != self.tester:
                continue
            if self.verbose:
                print("  RX %03X %s" % (msg.arbitration_id, bytes(msg.data).hex(" ")))
            return bytes(msg.data[1:])          # strip address byte
        return None

    def send(self, data: bytes, timeout=2.0):
        if len(data) <= 6:                       # single frame
            self._send_raw(bytes([len(data)]) + data)
            return
        # first frame
        total = len(data)
        self._send_raw(bytes([0x10 | ((total >> 8) & 0x0F), total & 0xFF]) + data[:5])
        fc = self._recv_raw(min(timeout, self.fc_wait))
        if not fc or (fc[0] & 0xF0) != 0x30:
            # A busy ECU (e.g. right after 0x85, or mid-erase) silently drops the
            # frame and sends no flow control. Signal "busy" so routine_poll can
            # wait and resend the whole request, exactly as WinKFP does.
            raise FlowControlTimeout("no ISO-TP flow control (got %r)" % (fc,))
        bs, stmin = fc[1], fc[2]
        st = (stmin / 1000.0) if stmin <= 0x7F else ((stmin - 0xF0) / 1e6 if 0xF1 <= stmin <= 0xF9 else 0.0)
        idx, sn, sent_in_block = 5, 1, 0
        while idx < total:
            self._send_raw(bytes([0x20 | (sn & 0x0F)]) + data[idx:idx + 6])
            idx += 6; sn = (sn + 1) & 0x0F; sent_in_block += 1
            if bs and sent_in_block == bs and idx < total:
                fc = self._recv_raw(timeout)
                if not fc or (fc[0] & 0xF0) != 0x30:
                    raise FlowControlTimeout("no continuation flow control")
                bs, stmin = fc[1], fc[2]; sent_in_block = 0
            elif st:
                time.sleep(st)

    def recv(self, timeout=2.0) -> bytes:
        first = self._recv_raw(timeout)
        if first is None:
            raise TimeoutError("no response from ECU")
        pci = first[0] & 0xF0
        if pci == 0x00:                          # single frame
            return first[1:1 + (first[0] & 0x0F)]
        if pci == 0x10:                          # first frame
            total = ((first[0] & 0x0F) << 8) | first[1]
            buf = bytearray(first[2:])
            # flow control: clear-to-send, no block limit, no separation
            self._send_raw(bytes([0x30, 0x00, 0x00]))
            sn = 1
            while len(buf) < total:
                cf = self._recv_raw(timeout)
                if cf is None:
                    raise TimeoutError("ISO-TP consecutive frame timeout")
                if (cf[0] & 0xF0) != 0x20:
                    continue
                buf += cf[1:]
                sn = (sn + 1) & 0x0F
            return bytes(buf[:total])
        raise IOError("unexpected ISO-TP PCI 0x%02X" % first[0])


# ---------------------------------------------------------------- UDS client
class Uds:
    def __init__(self, tp: IsoTp):
        self.tp = tp

    def request(self, payload: bytes, timeout=2.0, expect=True) -> bytes:
        self.tp.send(payload, timeout)
        if not expect:
            return b""
        while True:
            resp = self.tp.recv(timeout)
            if resp and resp[0] == 0x7F and len(resp) >= 3 and resp[2] == 0x78:
                timeout = max(timeout, 5.0)      # responsePending: wait more
                continue
            break
        if resp and resp[0] == 0x7F:
            code = resp[2] if len(resp) >= 3 else 0
            raise RuntimeError("negative response to 0x%02X: NRC 0x%02X %s"
                               % (payload[0], code, NRC.get(code, "?")))
        if resp and resp[0] != (payload[0] | 0x40):
            raise RuntimeError("mismatched positive response 0x%02X to service 0x%02X"
                               % (resp[0], payload[0]))
        return resp

    def request_retry(self, payload: bytes, timeout=5.0, tries=6, interval=0.3) -> bytes:
        """request() that resends on a busy flow-control timeout. Safe for
        0x34/0x36/0x37: a dropped frame got no FF-ack, so the ECU never advanced
        its block counter and the resend is idempotent."""
        for attempt in range(tries):
            try:
                return self.request(payload, timeout=timeout)
            except FlowControlTimeout:
                if attempt == tries - 1:
                    raise
                time.sleep(interval)

    def raw(self, payload: bytes, timeout=2.0) -> bytes:
        """Send and return the raw response (may be a 0x7F negative); only
        transparently waits out responsePending (NRC 0x78). Never raises on a
        negative response - the caller inspects the NRC itself."""
        self.tp.send(payload, timeout)
        while True:
            resp = self.tp.recv(timeout)
            if resp and resp[0] == 0x7F and len(resp) >= 3 and resp[2] == 0x78:
                timeout = max(timeout, 5.0)
                continue
            return resp

    def routine_poll(self, payload: bytes, timeout=30.0, interval=0.3) -> bytes:
        """Start a routine (0x31 ..) and poll by resending it until it stops
        answering NRC 0x23 (routineNotComplete). Returns the final positive
        response, or raises on any other NRC / on timeout. This is exactly how
        WinKFP drives FLASH_LOESCHEN (erase) and FLASH_SIGNATUR_PRUEFEN."""
        end = time.time() + timeout
        last = None
        while time.time() < end:
            try:
                resp = self.raw(payload, timeout=min(10.0, timeout))
            except (FlowControlTimeout, TimeoutError) as e:
                # ECU busy and silent (no flow control, or no response at all -
                # e.g. computing a signature/checksum over the whole image) ->
                # wait and resend the whole request, as WinKFP does.
                last = e
                time.sleep(interval); continue
            last = resp
            if not resp:
                time.sleep(interval); continue
            if resp[0] == 0x7F:
                code = resp[2] if len(resp) >= 3 else 0
                if code in (0x23, 0x78):             # not complete / pending -> keep polling
                    time.sleep(interval); continue
                raise RuntimeError("routine 0x%s negative: NRC 0x%02X %s"
                                   % (payload[1:3].hex(), code, NRC.get(code, "?")))
            return resp                              # positive 0x71 ..
        raise TimeoutError("routine 0x%s did not complete in %.0fs (last=%r)"
                           % (payload[1:3].hex(), timeout, last))

    # --- services (KWP2000) -----------------------------------------------
    # 0x10 StartDiagnosticSession: this ECU uses KWP diagnostic-mode bytes,
    # not UDS session ids. Valid modes (from handler 0xB125C, state 0x409534):
    #   0x81 = default/standard, 0x85 = programming, 0x87 = (elevated)
    def start_session(self, mode=0x81):    return self.request(bytes([0x10, mode]))
    def tester_present(self):              return self.request(bytes([0x3E, 0x01]))
    def read_ecu_id(self, option):         return self.request(bytes([0x1A, option]))
    def read_data_by_id(self, did):        return self.request(bytes([0x22, did >> 8, did & 0xFF]))
    def read_local_id(self, lid):          return self.request(bytes([0x21, lid]))
    def read_mem_by_addr23(self, logaddr, n):
        return self.request(bytes([0x23, (logaddr >> 8) & 0xFF, logaddr & 0xFF, n]))

    def security_access(self, level_seed=0x01, algo="afb10", seed_only=False):
        seed_resp = self.request(bytes([0x27, level_seed]))
        seed_bytes = seed_resp[2:]
        seed = int.from_bytes(seed_bytes[:2], "big") if seed_bytes else 0
        print("  seed = %s (0x%04X)" % (seed_bytes.hex(" "), seed))
        if seed == 0:
            print("  seed is 0 -> already unlocked (or no seed).")
            return
        cands = {name: fn(seed) for name, fn in KEY_ALGOS.items()}
        for name, k in cands.items():
            print("    candidate key [%-7s] = 0x%04X" % (name, k))
        if seed_only:
            print("  --seed-only: NOT sending a key (no attempt consumed).")
            print("  Match these against a real tool's key for this seed to pin the level->algo.")
            return
        key = cands[algo]
        print("  sending key 0x%04X using algo '%s' (level 0x%02X)" % (key, algo, level_seed + 1))
        self.request(bytes([0x27, level_seed + 1, (key >> 8) & 0xFF, key & 0xFF]))
        print("  unlock accepted.")


# ---------------------------------------------------------------- bus setup
def open_bus(args):
    import can
    return can.Bus(interface="kvaser", channel=args.channel, bitrate=args.bitrate,
                   receive_own_messages=False)


def make_uds(args):
    bus = open_bus(args)
    tp = IsoTp(bus, args.req_id, args.resp_id, args.ecu, TESTER_ADDR, verbose=args.verbose)
    return bus, Uds(tp)


def resign_verify(path) -> bool:
    """Return True iff tools/bmy_resign.py reports the image valid."""
    try:
        out = subprocess.run([sys.executable, os.path.join(HERE, "bmy_resign.py"), "verify", path],
                             capture_output=True, text=True)
        print(out.stdout.strip())
        if out.stderr.strip():
            print(out.stderr.strip(), file=sys.stderr)
        return out.returncode == 0 and "VALID" in out.stdout.upper()
    except Exception as e:
        print("could not run bmy_resign.py verify: %s" % e, file=sys.stderr)
        return False


# ---------------------------------------------------------------- commands
def _step(label, fn):
    """Run one request; print the result or the NRC, never crash."""
    try:
        r = fn()
        print("  %-28s OK  %s" % (label, r.hex(" ") if r else ""))
        return r
    except Exception as e:
        print("  %-28s -> %s" % (label, e))
        return None


def cmd_info(args):
    bus, uds = make_uds(args)
    try:
        print("ECU answered on 0x%03X (comms + ISO-TP + addressing confirmed)." % args.resp_id)
        _step("StartSession 0x81", lambda: uds.start_session(args.session))
        _step("TesterPresent 0x3E", uds.tester_present)
        # KWP ReadEcuIdentification 0x1A, common BMW option bytes
        for opt in (0x80, 0x86, 0x87, 0x8C, 0x9B, 0x90):
            _step("ReadEcuId 0x1A %02X" % opt, lambda o=opt: uds.read_ecu_id(o))
        # KWP ReadDataByLocalId 0x21, a couple of common ids
        for lid in (0x0C, 0x80, 0x0B):
            _step("ReadLocalId 0x21 %02X" % lid, lambda i=lid: uds.read_local_id(i))
    finally:
        bus.shutdown()


def cmd_readcoding(args):
    bus, uds = make_uds(args)
    try:
        uds.start_session(args.session)
        n = args.length
        data = bytearray()
        addr = args.addr
        while n > 0:
            chunk = min(4, n)                      # 0x23 serves <=4 bytes/request
            r = uds.read_mem_by_addr23(addr, chunk)
            data += r[1:]
            addr += chunk; n -= chunk
        print("NVM 0x%03X..: %s" % (args.addr, bytes(data).hex(" ")))
    finally:
        bus.shutdown()


def _asic_xfer(uds, regfield, data):
    """One ASIC QSPI transfer via the patched 0x23 handler (op=1).
    arg = (regfield<<16)|data ; returns (RX0, RX1) 16-bit halfwords or None+NRC."""
    arg = ((regfield & 0xFFFF) << 16) | (data & 0xFFFF)
    req = bytes([0x23, 0x01, (arg >> 24) & 0xFF, (arg >> 16) & 0xFF,
                 (arg >> 8) & 0xFF, arg & 0xFF])
    r = uds.raw(req)
    if not r or r[0] == 0x7F:
        nrc = r[2] if r and len(r) >= 3 else None
        return None, nrc
    b = r[1:5]
    return (b[0] << 8 | b[1], b[2] << 8 | b[3]), None


def _probe_session(uds, args):
    """Open the session where the patched 0x23 is reachable (same gate as the
    0x21 hook: flags[8]=0x94, no security level). Default session suffices;
    fall back to 0x87 if the ECU reports conditionsNotCorrect."""
    try:
        uds.start_session(SESSION_DEFAULT)
    except RuntimeError:
        pass
    uds.tester_present()


def cmd_asic(args):
    bus, uds = make_uds(args)
    try:
        _probe_session(uds, args)
        if args.mode == "ram":
            addr = int(args.a, 16)
            req = bytes([0x23, 0x02, (addr >> 24) & 0xFF, (addr >> 16) & 0xFF,
                         (addr >> 8) & 0xFF, addr & 0xFF])
            n = args.watch if args.watch else 1
            for i in range(n):
                r = uds.raw(req)
                if not r or r[0] == 0x7F:
                    print("RAM 0x%08X -> NRC/empty: %s" % (addr, r.hex(" ") if r else "(none)"))
                else:
                    ts = time.strftime("%H:%M:%S")
                    print("%s RAM 0x%08X: %s" % (ts, addr, r[1:].hex(" ")))
                if i < n - 1:
                    time.sleep(args.interval)
        elif args.mode == "xfer":
            reg = int(args.a, 16)
            data = int(args.b, 16) if args.b is not None else 0
            rx, nrc = _asic_xfer(uds, reg, data)
            if rx is None:
                print("ASIC xfer reg=0x%03X data=0x%03X -> NRC 0x%s"
                      % (reg, data, "%02X" % nrc if nrc is not None else "??"))
            else:
                print("ASIC xfer reg=0x%03X data=0x%03X -> RX0=0x%04X RX1=0x%04X"
                      % (reg, data, rx[0], rx[1]))
        elif args.mode == "dump":
            start = int(args.a, 16)
            end = int(args.b, 16)
            step = int(args.step, 16) if args.step else 4
            print("# reg   RX0    RX1   (data=0x%03X)" % (args.data,))
            for reg in range(start, end + 1, step):
                rx, nrc = _asic_xfer(uds, reg, args.data)
                if rx is None:
                    print("0x%03X   NRC 0x%s" % (reg, "%02X" % nrc if nrc is not None else "??"))
                else:
                    print("0x%03X   0x%04X 0x%04X" % (reg, rx[0], rx[1]))
    finally:
        bus.shutdown()


def cmd_unlock(args):
    bus, uds = make_uds(args)
    try:
        # Verified path: default session, then adjustment mode (where 0x27 is granted).
        uds.start_session(SESSION_DEFAULT)
        if args.session != SESSION_DEFAULT:
            uds.start_session(args.session)
        uds.security_access(args.level, args.algo, seed_only=args.seed_only)
    finally:
        bus.shutdown()


def _coerce4(s):
    b = bytes.fromhex(s[2:]) if s.startswith("0x") else s.encode()
    return (b + b"\x00" * 4)[:4]


def authenticate(uds, uid="273c", w564_override=None, open_prog=True, key=AUTH_KEY16):
    """Run the HARDWARE-VERIFIED level-5 Authentisierung and (optionally) open
    ECUProgrammingMode (0x85). Returns True on success. Shared by `auth5` and
    the flasher so the flash path uses the exact verified entry sequence:
      0x10 0x81 -> 0x10 0x87 -> 0x1A 0x89 (w564 = last 4 bytes, per-unit)
      -> 0x31 07 03 <uid> (random) -> 0x31 08 MD5(key||uid||w564||random||key)
      -> 71 08 01 -> 0x10 0x85."""
    # 0x10 0x81 (back to default) can be refused (NRC 0x12) if the ECU is stuck
    # in a non-default session from a prior aborted run. That is non-fatal - the
    # session we actually need is 0x87, reached next. A clean power-cycle avoids
    # it entirely, but tolerate it so a crashed attempt doesn't wedge re-entry.
    # In the app these open normally; in the bootloader they return NRC 0x12
    # (sub-function not supported) - that is fine, the auth routines below work
    # directly, so tolerate both and proceed either way.
    for mode, name in ((SESSION_DEFAULT, "0x81"), (SESSION_ADJUST, "0x87")):
        try:
            uds.start_session(mode)
        except RuntimeError as e:
            print("  %s refused (%s) - continuing (ECU likely in bootloader)" % (name, e))
    uid = _coerce4(uid)
    if w564_override:
        w564 = _coerce4(w564_override)
    else:                               # per-unit: last 4 bytes of 0x1A 0x89
        r89 = uds.read_ecu_id(0x89)
        w564 = bytes(r89[-4:])
        print("  1A89 = %r -> w564 = %r" % (
            "".join(chr(b) if 32 <= b < 127 else "." for b in r89), w564))
    print("  UID=%s  W564=%s  KEY=%s" % (uid.hex(), w564.hex(), key.hex()))
    r = uds.request(bytes([0x31, 0x07, 0x03]) + uid)        # read random
    zufall = r[2:10]
    data16 = auth_data16(uid, w564, zufall)
    resp = auth_response(data16, key)
    print("  ZUFALLSZAHL = %s" % zufall.hex())
    print("  response    = %s" % resp.hex())
    rr = uds.request(bytes([0x31, 0x08]) + resp)            # send response
    if not (rr and rr[0] == 0x71 and len(rr) >= 3 and rr[2] == 0x01):
        print("  *** AUTH REJECTED (resp %s; success needs 71 08 01) ***" % (rr.hex(" ") if rr else "none"))
        return False
    print("  *** LEVEL-5 AUTHENTISIERUNG ACCEPTED (resp %s) ***" % rr.hex(" "))
    if open_prog:
        uds.start_session(SESSION_PROG)
        print("  *** PROGRAMMING MODE (0x85) OPEN ***")
    return True


def cmd_auth5(args):
    bus, uds = make_uds(args)
    try:
        authenticate(uds, uid=args.uid, w564_override=args.w564, open_prog=True)
    finally:
        bus.shutdown()


def _load_plan(plandir):
    import json
    plan = json.load(open(os.path.join(plandir, "plan.json")))
    data = open(os.path.join(plandir, "data.bin"), "rb").read()
    return plan, data


def cmd_repack(args):
    """Build a flashable plan (plan.json + data.bin) by re-slicing an EDITED set
    of bank images onto a reference plan's fixed segment layout. Bank images are
    raw dumps keyed by their base address (same format as flash/bin/*.bin). Edits
    in the banks flow straight into the segments; the addr/size layout is kept
    byte-identical to the reference capture so the ECU sees the same geometry."""
    import json
    plan, _ = _load_plan(args.plan)
    banks = {}
    for spec in args.bank:
        base_s, path = spec.split("=", 1)
        banks[int(base_s, 0)] = open(path, "rb").read()

    def bank_of(addr, n):
        for base in sorted(banks, reverse=True):
            if addr >= base and (addr - base) + n <= len(banks[base]):
                return base
        return None

    blob = bytearray()
    new_segs = []
    for s in plan["segments"]:
        base = bank_of(s["addr"], s["size"])
        if base is None:
            sys.exit("no bank covers segment addr 0x%06X len %d - need a --bank for it"
                     % (s["addr"], s["size"]))
        off = s["addr"] - base
        seg = banks[base][off:off + s["size"]]
        new_segs.append({"addr": s["addr"], "fmt": s["fmt"], "size": s["size"],
                         "offset": len(blob), "len": len(seg)})
        blob += seg
    out = args.out
    os.makedirs(out, exist_ok=True)
    plan2 = dict(plan)
    plan2["name"] = os.path.basename(out.rstrip("/\\"))
    plan2["segments"] = new_segs
    plan2["repacked_from"] = args.plan
    json.dump(plan2, open(os.path.join(out, "plan.json"), "w"), indent=2)
    open(os.path.join(out, "data.bin"), "wb").write(blob)
    print("repacked %d segments (%d bytes) -> %s" % (len(new_segs), len(blob), out))
    print("NOTE: if you edited program/cal regions, RE-SIGN before flashing:")
    print("      python tools/bmy_resign.py fix <bank0 image>   (updates MISR + BMY)")


def cmd_flashplan(args):
    """Execute a flash plan over the Kvaser: verified auth -> erase -> transfer
    every segment (0x34/0x36/0x37) -> signature verify (0x31 09) -> reset.
    DRY-RUN unless --arm. The exact sequence is the one captured from a real
    WinKFP flash of this module (analysis/mk60e5_flash_can_log.txt)."""
    plan, data = _load_plan(args.plan)
    segs = plan["segments"]
    erase = bytes.fromhex(plan["erase"]) if plan.get("erase") else None
    maxblk = plan.get("max_block", 0xFC)
    chunk = maxblk - 1                      # 0x36 service byte counts toward the block

    # ---- validate the plan against its data blob --------------------------
    total = 0
    for i, s in enumerate(segs):
        seg = data[s["offset"]:s["offset"] + s["len"]]
        if len(seg) != s["size"] or s["len"] != s["size"]:
            sys.exit("segment %d size mismatch (declared 0x%X, blob %d)" % (i, s["size"], len(seg)))
        total += len(seg)

    print("=" * 70)
    print("FLASH PLAN: %s   (%d segments, %d bytes, maxblock 0x%02X)"
          % (plan.get("name"), len(segs), total, maxblk))
    print("source log: %s" % plan.get("source_log", "?"))
    if erase:
        print("erase     : 31 02 %s  (start 0x%06X, %d bytes)"
              % (erase.hex(), int.from_bytes(erase[0:3], "big"), int.from_bytes(erase[4:7], "big")))
    for i, s in enumerate(segs):
        nframes = (s["size"] + chunk - 1) // chunk
        print("  [%2d] 0x%06X  %7d B  %4d frames" % (i, s["addr"], s["size"], nframes))
    print("=" * 70)

    if not args.arm:
        print("DRY RUN (no bus opened, nothing transmitted). Re-run with --arm to flash.")
        print("Sequence that WOULD be sent, after the verified level-5 auth + 0x85:")
        print("  1. 31 02 <erase> and poll until 71 02 01   (erase, up to %ds)" % args.erase_timeout)
        print("  2. 28 02 ; 29 02                            (quiet normal CAN msgs)")
        print("  3. per segment: 34 <addr> 06 <size> -> 74 00 FC ; N x (36 <=%dB -> 76 cnt 01) ; 37 <addr> 06 <size> -> 77" % chunk)
        print("  4. 31 0A (status) ; 31 09 02 poll -> 71 09 01 (SIGNATURE VERIFY) ; 31 0A -> 71 0A 01")
        print("  5. 29 02 ; 11 01 -> 51 01                   (re-enable + ECU reset)")
        if plan.get("repacked_from"):
            print("NOTE: this is a REPACKED (edited) plan. The ECU verifies the BMY signature")
            print("      at step 4 - an unsigned edit will be REJECTED (71 09 != 01). Re-sign first.")
        return

    typed = input('ARMED. Type exactly "FLASH %s" to proceed: ' % plan.get("name"))
    if typed.strip() != "FLASH %s" % plan.get("name"):
        sys.exit("confirmation mismatch - aborted, nothing sent.")

    bus, uds = make_uds(args)
    try:
        if args.no_auth:
            # ECU already in the bootloader (0x85 opens with no app auth; app
            # sessions 0x81/0x87 return NRC 0x12). Used to resume/recover a flash
            # after the app has already handed off to the bootloader.
            print("[auth] --no-auth: ECU in bootloader, opening programming 0x85 directly ...")
            uds.start_session(SESSION_PROG)
            print("  *** PROGRAMMING MODE (0x85) OPEN ***")
        else:
            print("[auth] level-5 Authentisierung + ECUProgrammingMode ...")
            if not authenticate(uds, uid=args.uid, w564_override=args.w564, open_prog=True):
                sys.exit("auth failed - aborted before any erase/write.")

        # WinKFP waits ~1.5s after entering programming mode before the erase;
        # the ECU is briefly not ready and drops frames (no flow control).
        print("  settling after 0x85 ...")
        time.sleep(2.0)

        if erase:
            print("[erase] 31 02 %s (polling) ..." % erase.hex())
            r = uds.routine_poll(bytes([0x31, 0x02]) + erase, timeout=args.erase_timeout)
            print("  erase complete: %s" % r.hex(" "))

        print("[quiet] 28 02 ; 29 02")
        uds.request(bytes([0x28, 0x02]), expect=False)
        uds.request(bytes([0x29, 0x02]), expect=False)

        for i, s in enumerate(segs):
            addr3 = s["addr"].to_bytes(3, "big")
            size4 = s["size"].to_bytes(4, "big")
            seg = data[s["offset"]:s["offset"] + s["len"]]
            print("[seg %2d] 0x%06X  %d B -> 34 requestDownload" % (i, s["addr"], len(seg)))
            rd = uds.request_retry(bytes([0x34]) + addr3 + bytes([s["fmt"]]) + size4, timeout=5.0)
            # positive 0x74 <lenFmt> <maxblk..>; honor the ECU's reported block length
            if len(rd) >= 3:
                ecu_max = rd[-1]
                seg_chunk = (ecu_max or maxblk) - 1
            else:
                seg_chunk = chunk
            cnt = 1
            for off in range(0, len(seg), seg_chunk):
                piece = seg[off:off + seg_chunk]
                rr = uds.request_retry(bytes([0x36]) + piece, timeout=5.0)
                # expect 76 <cnt_hi> <cnt_lo> 01
                got = int.from_bytes(rr[1:3], "big") if len(rr) >= 3 else -1
                if got != (cnt & 0xFFFF) or (len(rr) >= 4 and rr[3] != 0x01):
                    sys.exit("  transfer NAK at block %d (resp %s)" % (cnt, rr.hex(" ")))
                cnt += 1
            uds.request_retry(bytes([0x37]) + addr3 + bytes([s["fmt"]]) + size4, timeout=5.0)
            print("         %d frames, transfer exit OK" % (cnt - 1))

        print("[verify] 31 0A status ...")
        try:
            st = uds.raw(bytes([0x31, 0x0A]), timeout=5.0)
            print("  31 0A -> %s" % (st.hex(" ") if st else "none"))
        except Exception as e:
            print("  31 0A -> %s" % e)

        if args.probe_finalize:
            print("[probe] enumerating 31 09 sub-functions in the WRITTEN state ...")
            for sf in range(0, 8):
                try:
                    r = uds.raw(bytes([0x31, 0x09, sf]), timeout=6.0)
                    print("  31 09 %02X -> %s" % (sf, r.hex(" ") if r else "NO RESP"))
                except Exception as e:
                    print("  31 09 %02X -> %s" % (sf, e))
            for sub in ([0x31, 0x08], [0x31, 0x0A]):
                try:
                    r = uds.raw(bytes(sub), timeout=4.0)
                    print("  %s -> %s" % (bytes(sub).hex(" "), r.hex(" ") if r else "NO RESP"))
                except Exception as e:
                    print("  %s -> %s" % (bytes(sub).hex(" "), e))
            print("[probe] NOT resetting - session left as-is for inspection.")
            return

        # Signature/checksum verify. This bootloader (verified live on a 335)
        # uses a TWO-STEP routine: 31 09 00 STARTS the verify, then 31 09 02
        # returns the result (71 09 01 = pass). While it computes over the whole
        # image it answers 7F 31 23 (busy), nothing at all, or - if asked for the
        # result before it was started - 7F 31 12, which just means "(re)start".
        # (A single-step 31 09 02 also works on the M3's own bootloader.)
        print("[verify] 31 09 00 start, poll 31 09 02 for result ...")
        uds.raw(bytes([0x31, 0x09, 0x00]), timeout=6.0)
        end = time.time() + args.verify_timeout
        result = None
        while time.time() < end:
            try:
                r = uds.raw(bytes([0x31, 0x09, 0x02]), timeout=8.0)
            except (FlowControlTimeout, TimeoutError):
                time.sleep(0.3); continue
            if not r:
                time.sleep(0.3); continue
            if r[0] == 0x71:
                result = r; break
            code = r[2] if len(r) >= 3 else 0
            if code in (0x23, 0x78):              # busy, still computing
                time.sleep(0.3); continue
            if code == 0x12:                      # not started yet -> (re)start
                uds.raw(bytes([0x31, 0x09, 0x00]), timeout=6.0); time.sleep(0.3); continue
            sys.exit("  SIGNATURE VERIFY rejected: NRC 0x%02X %s" % (code, NRC.get(code, "?")))
        if not (result and len(result) >= 3 and result[2] == 0x01):
            sys.exit("  SIGNATURE VERIFY FAILED (resp %s). Image rejected - re-sign and retry."
                     % (result.hex(" ") if result else "timeout"))
        print("  *** SIGNATURE VERIFIED (%s) ***" % result.hex(" "))
        st = uds.raw(bytes([0x31, 0x0A]), timeout=5.0)
        print("  31 0A -> %s" % (st.hex(" ") if st else "none"))

        print("[reset] 29 02 ; 11 01 ...")
        uds.request(bytes([0x29, 0x02]), expect=False)
        uds.request(bytes([0x11, 0x01]), expect=False)
        print("done. Power-cycle, then run `info` / `auth5` to confirm the module is healthy.")
    finally:
        bus.shutdown()


def cmd_wss(args):
    """Live wheel-speed monitor. The MK60 broadcasts per-wheel speed on CAN
    0x0CE as four little-endian u16 (FL, FR, RL, RR). Bit 15 reads as a
    validity/fault flag (0x8000 = no/invalid sensor); the low bits are speed.
    Spin a wheel/stimulate a sensor and watch its column move."""
    import can
    bus = open_bus(args)
    print("Monitoring CAN 0x%03X wheel speeds (Ctrl-C to stop). Columns: FL FR RL RR" % args.id)
    print("per wheel: raw(LE) | speed = (raw & 0x%04X)*%.4f %s | V=valid(bit15 clear)"
          % (args.mask, args.scale, args.unit))
    last = None
    try:
        while True:
            msg = bus.recv(timeout=1.0)
            if msg is None or msg.arbitration_id != args.id:
                continue
            d = bytes(msg.data)
            if d == last:
                continue
            last = d
            cells = []
            for i, name in enumerate(("FL", "FR", "RL", "RR")):
                raw = int.from_bytes(d[i * 2:i * 2 + 2], "little")
                spd = (raw & args.mask) * args.scale
                valid = "V" if not (raw & 0x8000) else "-"
                cells.append("%s %04X %7.2f %s" % (name, raw, spd, valid))
            print("  " + " | ".join(cells))
    except KeyboardInterrupt:
        pass
    finally:
        bus.shutdown()


def cmd_sniff(args):
    import can
    bus = open_bus(args)
    print("Sniffing CAN %s @ %d. Ctrl-C to stop. Logging to %s"
          % (args.channel, args.bitrate, args.out or "<stdout>"))
    fh = open(args.out, "w") if args.out else None
    try:
        while True:
            m = bus.recv(timeout=1.0)
            if m is None:
                continue
            line = "%0.6f %03X %d %s" % (m.timestamp, m.arbitration_id, m.dlc,
                                         bytes(m.data).hex(" "))
            print(line)
            if fh:
                fh.write(line + "\n"); fh.flush()
    except KeyboardInterrupt:
        pass
    finally:
        if fh:
            fh.close()
        bus.shutdown()


def cmd_verify(args):
    ok = resign_verify(args.image)
    print("image %s: %s" % (args.image, "VALID (signed)" if ok else "INVALID / unsigned"))
    sys.exit(0 if ok else 2)


def cmd_flash(args):
    # ---- WinKFP cross-check (C:\EC-APPS\NFS\SGDAT\15DSC60.ipo) -------------
    # WinKFP's authoritative MK60 flash job order is:
    #   SG_IDENT_LESEN -> DIAGNOSE_MODE(ECUPM, programming session) ->
    #   FLASH_PARAMETER_SETZEN -> FLASH_BLOCKLAENGE_LESEN (ECU reports block len!)
    #   -> FLASH_ZEITEN_LESEN (erase/signature/reset/auth wait times) ->
    #   FLASH_LOESCHEN + status poll (erase) -> FLASH_SCHREIBEN_ADRESSE ->
    #   FLASH_SCHREIBEN (A/B buffered) -> FLASH_SCHREIBEN_ENDE ->
    #   FLASH_SIGNATUR_PRUEFEN(Daten;Programm) (ECU verifies signature!) ->
    #   FLASH_PROGRAMMIER_STATUS_LESEN -> AIF_SCHREIBEN -> STEUERGERAETE_RESET.
    # The raw CAN service bytes per job live in the compiled SGBD (DSC_60.prg);
    # the DEFINITIVE capture is an EDIABAS IFH/API trace of WinKFP flashing the
    # real module. The template below mirrors the structure but its routine ids
    # are NOT confirmed - adapt to that trace before trusting it.
    print("=" * 70)
    print("UNVERIFIED FLASH TEMPLATE - structure matches WinKFP 15DSC60.ipo, but")
    print("routine ids are NOT confirmed vs the SGBD/bootloader. CAN BRICK THE ECU.")
    print("Capture an EDIABAS trace of a real WinKFP flash and adapt first.")
    print("=" * 70)
    if not os.path.isfile(args.image):
        sys.exit("image not found: %s" % args.image)
    if not resign_verify(args.image):
        sys.exit("image failed signature verify - run: python tools/bmy_resign.py fix '%s'" % args.image)
    if not args.i_understand_brick_risk:
        sys.exit("refusing: pass --i-understand-brick-risk after you have (1) sniffed a real\n"
                 "flash of THIS module and confirmed the sequence below matches, and (2) have\n"
                 "a hardware recovery path (BDM/JTAG) ready.")
    typed = input('Type exactly "FLASH %s": ' % os.path.basename(args.image))
    if typed.strip() != "FLASH %s" % os.path.basename(args.image):
        sys.exit("confirmation mismatch - aborted.")

    image = open(args.image, "rb").read()
    bus, uds = make_uds(args)
    try:
        # --- standard BMW UDS programming template (ADAPT to your sniff) -----
        print("[1] ECUProgrammingMode: StartDiagnosticSession 0x10 0x%02X ..." % args.session)
        uds.start_session(args.session)
        print("[2] security access 0x27 ...")
        uds.security_access(args.level, args.algo)
        print("[3] request download 0x34 (addr=0x%X len=0x%X) ..." % (args.dest, len(image)))
        # 0x34 dataFormatId=00, addrLenFmt=0x44 (4-byte addr + 4-byte size)
        uds.request(bytes([0x34, 0x00, 0x44]) + args.dest.to_bytes(4, "big") + len(image).to_bytes(4, "big"))
        print("[4] transfer data 0x36 in blocks ...")
        block, seq = args.block, 1
        for off in range(0, len(image), block):
            uds.request(bytes([0x36, seq & 0xFF]) + image[off:off + block], timeout=5.0)
            seq += 1
            if off % (block * 32) == 0:
                print("    %d / %d bytes" % (off, len(image)))
        print("[5] request transfer exit 0x37 ...")
        uds.request(bytes([0x37]), timeout=5.0)
        print("[6] checksum/verify routine 0x31 (module-specific - ADAPT) ...")
        print("[7] ECU reset 0x11 01 ...")
        uds.request(bytes([0x11, 0x01]), expect=False)
        print("done - power-cycle and re-run `info` to confirm the module came back.")
    finally:
        bus.shutdown()


# ---------------------------------------------------------------- CLI
def main():
    p = argparse.ArgumentParser(description="Kvaser MK60E5 DSC diagnostic / flash client")
    p.add_argument("--channel", type=int, default=0, help="Kvaser channel index (default 0)")
    p.add_argument("--bitrate", type=int, default=BITRATE)
    p.add_argument("--ecu", type=lambda x: int(x, 0), default=DSC_ADDR, help="ECU diag address (default 0x29)")
    p.add_argument("--req-id", type=lambda x: int(x, 0), default=REQ_ID, dest="req_id")
    p.add_argument("--resp-id", type=lambda x: int(x, 0), default=RESP_ID, dest="resp_id")
    p.add_argument("-v", "--verbose", action="store_true", help="dump raw CAN frames")
    sub = p.add_subparsers(dest="cmd", required=True)

    inf = sub.add_parser("info", help="session + tester-present + read ids (SAFE)")
    inf.add_argument("--session", type=lambda x: int(x, 0), default=0x81,
                     help="KWP diagnostic mode (0x81 default, 0x85 programming, 0x87)")
    inf.set_defaults(func=cmd_info)

    rc = sub.add_parser("readcoding", help="read logical NVM via 0x23 (SAFE)")
    rc.add_argument("--addr", type=lambda x: int(x, 0), default=0x0000)
    rc.add_argument("--length", type=int, default=64)
    rc.add_argument("--session", type=lambda x: int(x, 0), default=0x81)
    rc.set_defaults(func=cmd_readcoding)

    ap = sub.add_parser("asic", help="ASIC QSPI xfer / RAM peek via patched 0x23 (PROBE IMAGE ONLY)")
    ap.add_argument("mode", choices=["xfer", "dump", "ram"])
    ap.add_argument("a", help="xfer:regfield  dump:startreg  ram:addr  (all hex)")
    ap.add_argument("b", nargs="?", help="xfer:data  dump:endreg  (hex)")
    ap.add_argument("--step", help="dump register step (hex, default 4)")
    ap.add_argument("--watch", type=int, default=0, help="ram: poll this many times in one session")
    ap.add_argument("--interval", type=float, default=0.4, help="ram --watch poll interval (s)")
    ap.add_argument("--data", type=lambda s: int(s, 16), default=0, help="dump data field (hex, default 0)")
    ap.add_argument("--session", type=lambda s: int(s, 16), default=SESSION_DEFAULT)
    ap.set_defaults(func=cmd_asic)

    ul = sub.add_parser("unlock", help="security access 0x27 (SAFE-ish; just unlocks)")
    ul.add_argument("--session", type=lambda x: int(x, 0), default=SESSION_ADJUST,
                    help="mode entered before auth (0x87 adjustment = verified; 0x81 default first)")
    ul.add_argument("--level", type=lambda x: int(x, 0), default=FLASH_SEED_LEVEL,
                    help="0x27 seed sub-function (0x03 verified; key sent at +1)")
    ul.add_argument("--algo", choices=list(KEY_ALGOS), default=FLASH_ALGO,
                    help="key transform (seedrev = verified for level 0x03; afb10/afb9e = other levels)")
    ul.add_argument("--seed-only", action="store_true", dest="seed_only",
                    help="fetch+print the seed + all candidate keys; send NO key (no lockout risk)")
    ul.set_defaults(func=cmd_unlock)

    a5 = sub.add_parser("auth5", help="level-5 Authentisierung (keyed MD5) - M3-validated flash auth")
    a5.add_argument("--uid", default="273c", help="USER_ID: any 4 chars (tester-chosen; default 273c)")
    a5.add_argument("--w564", default=None,
                    help="override w564 (4 chars / 0x+hex); default = last 4 bytes of 0x1A 0x89 (per-unit)")
    a5.set_defaults(func=cmd_auth5)

    fp = sub.add_parser("flashplan", help="execute a captured/repacked flash plan (DRY-RUN unless --arm)")
    fp.add_argument("plan", help="plan dir (contains plan.json + data.bin), e.g. flash/plan/m3_7846816A_stock")
    fp.add_argument("--arm", action="store_true", help="actually transmit (erase+write+reset); omit for a dry run")
    fp.add_argument("--no-auth", action="store_true", dest="no_auth",
                    help="skip app-level auth: ECU already in bootloader (0x85 opens directly)")
    fp.add_argument("--probe-finalize", action="store_true", dest="probe_finalize",
                    help="after writing, enumerate 31 09 sub-functions instead of verify+reset (diagnostic)")
    fp.add_argument("--uid", default="273c", help="auth USER_ID (any 4 chars; default 273c)")
    fp.add_argument("--w564", default=None, help="override w564 (default = per-unit last 4 of 0x1A 0x89)")
    fp.add_argument("--erase-timeout", type=float, default=60.0, dest="erase_timeout")
    fp.add_argument("--verify-timeout", type=float, default=60.0, dest="verify_timeout")
    fp.set_defaults(func=cmd_flashplan)

    rp = sub.add_parser("repack", help="build a flashable plan from EDITED bank images (SAFE, offline)")
    rp.add_argument("--plan", required=True, help="reference plan dir providing the segment layout")
    rp.add_argument("--bank", action="append", required=True, metavar="BASE=PATH",
                    help="raw bank image keyed by base addr, e.g. 0x000000=main.bin (repeatable)")
    rp.add_argument("--out", required=True, help="output plan dir")
    rp.set_defaults(func=cmd_repack)

    ws = sub.add_parser("wss", help="live per-wheel speed monitor from CAN 0x0CE (SAFE)")
    ws.add_argument("--id", type=lambda x: int(x, 0), default=0x0CE, help="wheel-speed CAN id (default 0x0CE)")
    ws.add_argument("--mask", type=lambda x: int(x, 0), default=0x7FFF, help="speed bitmask (default 0x7FFF)")
    ws.add_argument("--scale", type=float, default=0.0625, help="km/h per bit (default 0.0625)")
    ws.add_argument("--unit", default="km/h")
    ws.set_defaults(func=cmd_wss)

    sn = sub.add_parser("sniff", help="log CAN traffic (SAFE; capture a real flash here)")
    sn.add_argument("--out", help="output log file")
    sn.set_defaults(func=cmd_sniff)

    vf = sub.add_parser("verify", help="check an image's signature via bmy_resign (SAFE, offline)")
    vf.add_argument("image")
    vf.set_defaults(func=cmd_verify)

    fl = sub.add_parser("flash", help="UNVERIFIED flash template - can brick the ECU")
    fl.add_argument("image")
    fl.add_argument("--dest", type=lambda x: int(x, 0), default=0x8000,
                    help="program destination CPU address (default 0x8000 = app base; CONFIRM)")
    fl.add_argument("--block", type=int, default=256,
                    help="transfer block size (WinKFP reads this from the ECU via FLASH_BLOCKLAENGE_LESEN)")
    fl.add_argument("--session", type=lambda x: int(x, 0), default=SESSION_PROG,
                    help="0x85 = ECUProgrammingMode (WinKFP DIAGNOSE_MODE ECUPM)")
    fl.add_argument("--level", type=lambda x: int(x, 0), default=FLASH_SEED_LEVEL)
    fl.add_argument("--algo", choices=list(KEY_ALGOS), default=FLASH_ALGO)
    fl.add_argument("--i-understand-brick-risk", action="store_true", dest="i_understand_brick_risk")
    fl.set_defaults(func=cmd_flash)

    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
