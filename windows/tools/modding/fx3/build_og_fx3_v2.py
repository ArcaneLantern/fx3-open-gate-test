"""Build the FX3 7.02 coprocessor design `ogsq_fx3_v2`: open gate at 23.98p / 24p (drive mode 0x8c0, as `ogsq_fx3_v1`) AND at 29.97p / 25p
(drive mode 0x820), with the stored records of both modes in their NTSC (60 Hz) and PAL (50 Hz) forms.

  C:/Python313/python.exe -B build/build_og_fx3_v2.py

Why (owner, 2026-11-26: "expand the 24p open gate ... to also be for 25p, 30p"; 50p and above were left out on the owner's choice, because the only
full-height sensor read-out, sensor mode 0x01 at 312-313 units of 1/36 MHz a row, needs about 26 ms for 2832 rows: the camera's own 0xe011 runs it at
36.7 fps at most). What the camera does, read from the firmware and seen on cameras:
  - 23.98p (NTSC) and 24p (PAL) use drive mode 0x8c0 (index 12): `ogsq_fx3_v1`, which works on FX3s (2026-11-24).
  - 29.97p (NTSC) and 25p (PAL) use drive mode 0x820 (index 10): the 30p family of the drive-mode selector (frame-rate code 2), as the A7S III notes
    read it and as a tester found on an FX3 in PAL (the repo's FX3-PAL25-MODE-0x820-REPORT-2026-11-25.md): with v1 at 25p the picture was the 16:9
    band stretched; with the v1 cells moved to row 10 and a 25 fps row it recorded open gate at 25.00 fps (13 min 41 s take).
  - 0x820 and 0x8c0 share the picture-record pair 0xbb31d8 / 0xbb3d90, which v1 already writes. So v2 = v1 + the same cells on row 10.
  - The stored records are computed by the camera at start-up from the 60 Hz or the 50 Hz timing table (whichever system it is set to). v1 carries the
    NTSC record of 0x8c0 only, so its L5 refuses a camera set to PAL (the record holds neither the stock nor the new NTSC bytes). v2 carries both
    modes in both systems and the helper takes the variant the camera holds (readcheck.c MULTI_REC, as the FX30 kit).

How each part is made and checked (every check must pass or nothing is written):
  row 12     build_og_fx3.fx_cells (v1's cells, from build_og_s3_v3.cells on the FX3 tables) must equal v1's 19 cells byte for byte
  row 10     the same recipe on row 10 (this file's cells(), a copy of build_og_s3_v3.cells with the row, the mode's own stock values and the timing
             rows as parameters):
               59.94 system 266, 4508, P 161, E 74 -> 313, 3828, P 29, E 23 = 1,201,200 units = 29.970 fps
               50 system    268, 5364, P 149, E 68 -> 313, 4600, P 23, E 1  = 1,440,000 units = 25.000 fps (the tester's row, which ran)
             both by the rule of every stock row (E < P, P odd and a divisor of VMAX, 4 | VMAX, E/P the reduced fraction) and with VMAX at least
             the 2998 lines the full-height read-out takes; HMAX 313 as v1's rows and the tester's
             Every cell of row 10 other than the 59.94-system timing row and the read-out table's 59.94 frame-length field must equal the tester's
             contributed design (modding/designs/ogsq_fx3_pal25_mode0x820_contrib.json), which ran
  records    the pair: v1's two records, unchanged (shared by 0x820 and 0x8c0: build/emu_record_selector.py)
  stored     build/emu_drvparam.py fx3_702 with every cell applied, run with the 60 Hz table (NTSC) and with the 50 Hz table in its place (PAL):
             only 0x820 and 0x8c0 change; plus the vertical sampling ratio 16/19; run-time bytes left alone (build_og_s3_v3.RUNTIME). NTSC 0x8c0 must
             equal v1's record; PAL 0x820 must equal the tester's at every offset of the site list. One list of offsets for both modes and both systems;
             per mode the four byte sets (NTSC stock / new, PAL stock / new) must all differ, so the helper can tell which the camera holds
Design only: nothing is written to a firmware file, nothing is sent to a camera.
"""
import hashlib
import json
import struct
import sys
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import build_og_fx3 as V1  # noqa: E402
import build_og_s3_v3 as V3  # noqa: E402
import emu_drvparam  # noqa: E402
import emu_record_selector  # noqa: E402

NAME, BUILD, BASE = "ogsq_fx3_v2", "fx3_702", V1.BASE
T, ROW, K_FRAME, SRC = V1.T_FX3, V3.ROW, V3.K_FRAME, 37         # SRC: index of drive mode 0xe011, the sensor's own full-height mode
LINES = 122 + 22 + 6 + 8 + 2832 + 8                              # 2998: the frame must hold the full-height read-out at one row per line
# per mode: index, the timing rows (new HMAX, VMAX, P, E; stock HMAX, VMAX, P, E; system; units), the rates they give
MODES = {
    0x8C0: {"index": 12, "rates": "23.98p (NTSC), 24p (PAL)",
            "tim": (313, 4788, 57, 34, 266, 5628, 67, 53, "59.94 system", 1501500), "tim_b": (313, 4780, 239, 193, 268, 5580, 93, 76, "50 system", 1500000)},
    0x820: {"index": 10, "rates": "29.97p (NTSC), 25p (PAL)",
            "tim": (313, 3828, 29, 23, 266, 4508, 161, 74, "59.94 system", 1201200), "tim_b": (313, 4600, 23, 1, 268, 5364, 149, 68, "50 system", 1440000)},
}
CONTRIB = "ogsq_fx3_pal25_mode0x820_contrib"


def check_row(h, v, p, e, units):
    """The rule every stock timing row with a fraction follows (build_og_s3_v4.check_row), for any frame length."""
    f = Fraction(units, v) - h
    assert 0 < e < p <= 255 and p % 2 == 1 and v % p == 0 and v % 4 == 0, (h, v, p, e)
    assert f == Fraction(e, p) and f.denominator == p, f"E/P is not the reduced fraction of the line length: {f} against {e}/{p}"
    assert v * h < units < v * (h + 1) and h * v + (v // p) * e == units
    assert v >= LINES, "the frame does not hold the full-height read-out"


def geo_row(img, mode):
    """The geometry table's row of a mode: 12-byte rows that start with the mode id, around v1's row of 0x8c0."""
    hits = [a for a in range(T["geo"] - 0x300, T["geo"] + 0x300, 12) if struct.unpack_from("<I", img, a - BASE)[0] == mode]
    assert len(hits) == 1, (hex(mode), [hex(a) for a in hits])
    return hits[0]


def cells(img, mode):
    """[(label, address, old, new, note)] for one drive mode: build_og_s3_v3.cells() with the row, the mode's stock values and the timing as parameters."""
    m = MODES[mode]
    idx = m["index"]
    at = lambda t, i=idx: T[t] + ROW[t] * i
    rd = lambda a, n: img[a - BASE:a - BASE + n]
    ids = struct.unpack_from("<40I", img, T["ids"] - BASE)
    assert ids[idx] == mode and ids[SRC] == 0xE011
    out = []

    def cell(label, addr, new, note, old=None):
        cur = rd(addr, len(new))
        assert old is None or cur == old, (label, cur.hex(), old.hex())
        if cur != new:
            out.append((label, addr, cur, new, note))

    def as_source(label, table, lo, hi, note):
        a, b = rd(at(table) + lo, hi - lo), rd(at(table, SRC) + lo, hi - lo)
        k = 0
        while k < len(a):
            if a[k] == b[k]:
                k += 1
                continue
            j = k
            while j < len(a) and (a[j] != b[j] or (j + 1 < len(a) and a[j + 1] != b[j + 1])):
                j += 1
            k0, j1 = k & ~1, (j + 1) & ~1
            cell(f"{label}+{lo + k0:#x}", at(table) + lo + k0, b[k0:j1], note)
            k = j1

    cell("C", at("colmap"), struct.pack("<I", 1), "column map: register matrix column 11 (sensor mode 0x21, the 16:9 band) -> 1 (sensor mode 0x01, full height), as 0xe011",
         struct.pack("<I", 11))
    assert rd(at("colmap", SRC), 8) == struct.pack("<2I", 1, 4) and rd(at("colmap") + 4, 4) == struct.pack("<I", 4)
    as_source("R1", "rx", 0, 12, "receiver type: 5, 3 -> 0, 2, as 0xe011 and the S35 movie modes")
    as_source("R2", "rx2", 0, 16, "receiver type, second table: 5, 3 -> 0, 2")
    as_source("D", "d", 4, 6, "0xc71a24 +4 (A7S III): 478 -> 484, the value of the modes on sensor mode 0x01 (meaning not known)")
    for t in ("tim", "tim_b"):
        h, v, p, e, h0, v0, p0, e0, system, units = m[t]
        check_row(h, v, p, e, units)
        assert h0 * v0 + (v0 // p0) * e0 == units, "the stock row is not this frame rate"
        cell(f"T.{t}", at(t), V3.trow(h, v, p, e), f"timing row, {system}: {h0}, {v0}, P {p0}, E {e0} -> {h}, {v}, P {p}, E {e} ({36e6 / units:.4f} fps)",
             V3.trow(h0, v0, p0, e0))
    as_source("W", "win", 0, 38, "stream-0 window row: 0xe011's (top margins 38, 6 -> 122, 22; height 2392 -> 2832)")
    as_source("A", "st1", 0, 38, "aux stream-1 row: 0xe011's")
    as_source("LC", "lc", 0, 14, "LC row: 0xe011's (V offset 220 -> 0, field 6 235 -> 37)")
    as_source("CR", "crop", 0, 20, "crop row: 0xe011's (V offset 220 -> 0, last field 2 -> 0)")
    g = geo_row(img, mode)
    cell("G", g + 10, struct.pack("<H", 0), f"geometry row of {mode:#x}: V offset 220 -> 0", struct.pack("<H", 220))
    va, vb = m["tim"][5], m["tim_b"][5]
    fa, fb = m["tim"][1] // 4 - K_FRAME, m["tim_b"][1] // 4 - K_FRAME
    assert struct.unpack_from("<9H", img, at("rl") - BASE)[4:] == (1000, va // 4 - K_FRAME, vb // 4 - K_FRAME, 618, 618)
    cell("L", at("rl") + 10, struct.pack("<4H", fa, fb, 2832 // 4 + 20, 2832 // 4 + 20),
         f"read-out table: frame-length fields {va // 4 - K_FRAME}, {vb // 4 - K_FRAME} -> {fa}, {fb} (VMAX / 4 - {K_FRAME}); row fields 618 -> 728 (rows / 4 + 20)")
    return out


def stored(fx, patches):
    """{system: {mode: (stock record, new record)}} from the FX3's own calculator, NTSC (60 Hz table) and PAL (the 50 Hz table in its place)."""
    f = emu_drvparam.CONSTS[BUILD]["fields"]
    img = bytearray(fx)
    for a, n in patches:
        img[a - BASE:a - BASE + len(n)] = n
    tb = lambda b: bytes(b[f[0x30] - BASE:f[0x30] - BASE + 24 * 40])
    # The read-out table holds a frame-length field per system (+10: 60 Hz, +12: 50 Hz) and the calculator reads +10 here; in PAL the camera's
    # records hold the +12 value (the tester's stock record, checked on his camera at all 62 offsets: 1318 at +0xda, where +10 would give 1104).
    # So the PAL run gets the 50 Hz timing table in place of the 60 Hz one AND each read-out row's +12 field in place of its +10 field.
    rl = emu_drvparam.CONSTS[BUILD]["fields"][0x44]
    rlp = lambda b: [(rl + 18 * i + 10, bytes(b[rl + 18 * i + 12 - BASE:rl + 18 * i + 14 - BASE])) for i in range(40)]
    out = {}
    for system, base_stock, base_new in (("ntsc", [], []), ("pal", [(f[0x2C], tb(fx))] + rlp(fx), [(f[0x2C], tb(img))] + rlp(img))):
        st, l1 = emu_drvparam.records(BUILD, base_stock)
        de, l2 = emu_drvparam.records(BUILD, list(patches) + base_new)          # the cells first, then (PAL) the patched 50 Hz table over the 60 Hz one
        assert not l1 and not l2 and all(st[m][2] is None and de[m][2] is None for m in st)
        changed = sorted(m for m in st if st[m][1] != de[m][1])
        assert changed == sorted(MODES), [hex(m) for m in changed]
        out[system] = {m: (st[m][1], de[m][1]) for m in MODES}
    return out


def main():
    des = ROOT / "modding" / "designs"
    v1 = json.loads((des / "ogsq_fx3_v1.json").read_text(encoding="utf8"))
    contrib = json.loads((des / f"{CONTRIB}.json").read_text(encoding="utf8"))
    fx = V1.image(BUILD)
    sha = hashlib.sha256(fx).hexdigest()
    assert sha == V1.SHA == v1["artifact_sha256"] == contrib["artifact_sha256"]
    ev = {"design": NAME, "build": BUILD}

    # ---- row 12: v1's cells, rebuilt
    c12_v1, _ = V1.fx_cells(fx)
    c12 = cells(fx, 0x8C0)
    v1_s = [(int(p["addr"], 16), p["old"], p["new"]) for p in v1["patches"] if p["kind"] == "S"]
    assert [(a, o.hex(), n.hex()) for _, a, o, n, _ in c12] == [(a, o.hex(), n.hex()) for _, a, o, n, _ in c12_v1] == v1_s, "row 12 is not v1's"
    # ---- row 10
    c10 = cells(fx, 0x820)
    mine = {a: (o.hex(), n.hex()) for _, a, o, n, _ in c10}
    theirs = {int(c["addr"], 16): (c["old"], c["new"]) for c in contrib["sensor_cells"]}
    ntsc_only = {a for lab, a, _, _, _ in c10 if lab == "T.tim"}
    assert len(c10) == len(c12) == 19 and len(theirs) == 18
    rl10 = next(a for lab, a, _, _, _ in c10 if lab == "L")
    for a, (o, n) in theirs.items():
        if a == rl10:                                    # theirs left the 59.94 frame-length field stock: the first two bytes
            assert o == mine[a][0] and n[4:] == mine[a][1][4:] and n[:4] == o[:4], (hex(a), o, n, mine[a])
        else:
            assert mine.get(a) == (o, n), (hex(a), (o, n), mine.get(a))
    assert set(mine) - set(theirs) == ntsc_only
    ev["row_10_against_the_tester"] = {"cells": len(c10), "equal_to_the_tester_s_design": len(theirs) - 1,
                                       "read_out_row": "equal but for the 59.94 frame-length field, which theirs left stock (PAL only)",
                                       "only_here": "the 59.94-system timing row (29.97p): " + ", ".join(hex(a) for a in ntsc_only)}
    # the two rows' cells side by side: the same tables and columns, the same new bytes but for the timing and the read-out frame-length fields
    for (l12, a12, o12, n12, _), (l10, a10, o10, n10, _) in zip(c12, c10):
        assert l12 == l10, (l12, l10)
        if l12 not in ("T.tim", "T.tim_b", "L", "G"):
            assert n12 == n10 and o12 == o10, l12
    # ---- the record pair: v1's, shared
    sel, _ = emu_record_selector.records(BUILD)
    assert sel[0x8C0] == sel[0x820] == sorted(V1.PAIR.values())
    recs = [p for p in v1["patches"] if p["kind"] == "R"]
    assert len(recs) == 2
    # ---- stored records
    cs = c12 + c10
    spans = sorted((a, len(n)) for _, a, _, n, _ in cs)
    assert all(a + n <= b for (a, n), (b, _) in zip(spans, spans[1:])), "cells overlap"
    st = stored(fx, [(a, n) for _, a, _, n, _ in cs])
    recs_out, offs = {}, set()
    var = {}
    for system in ("ntsc", "pal"):
        for m in MODES:
            s, n = st[system][m]
            d = bytearray(n)
            d[6], d[7] = 16, 19
            for o in V3.RUNTIME:
                d[o] = s[o]
            var[(system, m)] = (s, bytes(d))
            offs |= {o for o in range(emu_drvparam.REC) if s[o] != d[o]}
    offs = sorted(offs)
    sr1 = v1["stored_record"]
    assert var[("ntsc", 0x8C0)] == (bytes.fromhex(sr1["stock"]), bytes.fromhex(sr1["design"])), "NTSC 0x8c0 is not v1's record"
    tsr = contrib["stored_record"]
    t_offs = [int(o) for o in tsr["offsets_that_differ"]]
    s_pal, d_pal = var[("pal", 0x820)]
    t_stock, t_new = bytes.fromhex(tsr["stock_model_50_system"]), bytes.fromhex(tsr["design"])
    assert t_offs == [o for o in offs if s_pal[o] != d_pal[o]], "PAL 0x820: not the tester's offsets"
    assert all(s_pal[o] == t_stock[o] and d_pal[o] == t_new[o] for o in offs), "PAL 0x820: not the tester's stock and new bytes"
    pick = lambda b: bytes(b[o] for o in offs)
    for m in MODES:
        sets = [pick(var[(sy, m)][k]) for sy in ("ntsc", "pal") for k in (0, 1)]
        assert len(set(sets)) == 4, f"{m:#x}: the NTSC/PAL stock/new byte sets are not all different at the sites"
        recs_out[hex(m)] = {"index": MODES[m]["index"], "rates": MODES[m]["rates"],
                            **{sy: {"stock": var[(sy, m)][0].hex(), "design": var[(sy, m)][1].hex(),
                                    "bytes_that_change": sum(var[(sy, m)][0][o] != var[(sy, m)][1][o] for o in offs)} for sy in ("ntsc", "pal")}}
    assert offs[:2] == [6, 7] and not set(offs) & V3.RUNTIME and len(offs) <= 128
    ev["stored_records"] = {"offsets": len(offs), "ntsc_0x8c0_equals_v1": True, "pal_0x820_equals_the_tester_s": True,
                            "changed_modes_each_system": ["0x820", "0x8c0"], "variants_distinct": True,
                            "bytes_that_change": {k: {sy: v[sy]["bytes_that_change"] for sy in ("ntsc", "pal")} for k, v in recs_out.items()}}

    # ---- the design file
    patches = [{"kind": "S", "addr": hex(a), "old": o.hex(), "new": n.hex(), "where": "file", "note": f"{mode:#x} (index {MODES[mode]['index']}) {lab} {note}"}
               for mode, cc in ((0x8C0, c12), (0x820, c10)) for lab, a, o, n, note in cc]
    patches += recs
    timing = {f"{m:#x}": {t: {"hmax": MODES[m][t][0], "vmax": MODES[m][t][1], "p": MODES[m][t][2], "e": MODES[m][t][3], "units": MODES[m][t][9],
                              "fps": round(36e6 / MODES[m][t][9], 6), "system": MODES[m][t][8]} for t in ("tim", "tim_b")} for m in MODES}
    out = {"design": NAME, "build": BUILD, "camera": "ILME-FX3 (FX3), firmware 7.02",
           "title": "Open gate at 23.98p/24p (drive mode 0x8c0, ogsq_fx3_v1) and at 29.97p/25p (drive mode 0x820): both modes on the full-height sensor mode "
                    "of 0xe011, the shared picture records of v1, and the stored records of both modes in their NTSC and PAL forms",
           "status": "built from the firmware files and emulated; 0x8c0 at 23.98p is v1's, which works on FX3s; 0x820 at 25p is the tester's design (it ran "
                     "in PAL, 2026-11-25) plus the 29.97p row; the design as a whole has not run",
           "artifact": "cpapp-b.bin", "artifact_sha256": sha, "generated_by": "build/build_og_fx3_v2.py",
           "supersedes": {"design": "ogsq_fx3_v1", "what": "v1's 19 cells and two records unchanged; adds row 10 (0x820) and the PAL stored records"},
           "modes": {f"{m:#x}": {"index": v["index"], "rates": v["rates"]} for m, v in MODES.items()}, "mode_id": "0x8c0", "mode_ids": ["0x820", "0x8c0"],
           "timing": timing,
           "summary": {"sites": len(patches), "bytes": sum(len(p["new"]) // 2 for p in patches), "sensor_cells": len(cs), "records": 2,
                       "stored_records": "0x820 and 0x8c0, NTSC or PAL as the camera holds them, %d bytes each" % len(offs)},
           "lrc": v1["lrc"], "patches": patches, "record_size": emu_drvparam.REC,
           "stored_records": {k: {"index": v["index"], "offsets_that_differ": [hex(o) for o in offs], "ntsc": {"stock": v["ntsc"]["stock"], "design": v["ntsc"]["design"]},
                                  "pal": {"stock": v["pal"]["stock"], "design": v["pal"]["design"]}} for k, v in recs_out.items()},
           "stored_record_note": "RAM, computed by the camera at start-up from the 60 Hz or the 50 Hz timing table; run-time bytes (build_og_s3_v3.RUNTIME) "
                                 "are left alone; the write level finds each record through the pointer chain and takes the variant it holds",
           "guesses": v1["guesses"] + ["29.97p uses 0x820 as 25p does (the selector's 30p family; seen at 25p only)"],
           "not_shown": ["29.97p on a camera", "XAVC HS and S-I at 25p (the tester recorded XAVC S)", "whether movie standby runs 0x820 (the A7S III notes' "
                         "reading of its glitchy live view): with this design 0x820 is full height too"] + v1["not_shown"][1:],
           "frame_rates_not_served": "50p, 59.94p, 100p, 119.88p: no full-height read-out is fast enough (sensor mode 0x01 needs about 26 ms a frame); "
                                     "with the kit applied they are refused at encoder open"}
    (des / f"{NAME}.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf8", newline="\n")
    evd = ROOT / "evidence" / "fx3"
    ev["cells"] = [{"mode": f"{m:#x}", "label": lab, "addr": hex(a), "old": o.hex(), "new": n.hex()} for m, cc in ((0x8C0, c12), (0x820, c10)) for lab, a, o, n, _ in cc]
    (evd / f"{NAME}_checks.json").write_text(json.dumps(ev, indent=1) + "\n", encoding="utf8", newline="\n")
    print(f"{NAME}: {len(c12)} + {len(c10)} sensor cells + 2 records = {len(patches)} sites; stored records 0x820/0x8c0 x NTSC/PAL, {len(offs)} bytes each")
    for lab, a, o, n, note in c10:
        print(f"  0x820 {lab:8} {a:#x} {o.hex()} -> {n.hex()}")
    print("  row 10 = the tester's design (+ the 29.97p row); NTSC 0x8c0 record = v1's; PAL 0x820 record = the tester's;",
          json.dumps(ev["stored_records"]["bytes_that_change"]))
    print("wrote", des / f"{NAME}.json")


if __name__ == "__main__":
    main()
