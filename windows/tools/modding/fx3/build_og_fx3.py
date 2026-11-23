"""Build the FX3 7.02 coprocessor design `ogsq_fx3_v1`: the A7S III's working `ogsq_s3_v5` on the FX3's own tables.

  C:/Python313/python.exe -B build/build_og_fx3.py

Why this is a port and not a new design (modding/FX3_PORT.md): the FX3 7.02 coprocessor app is the A7S III 5.01 app
relinked. The same 40 drive modes (0x8c0 = index 12, 0xe011 = index 37), every sensor table byte-identical at a fixed
shift, the same calculator, record selector and scaler packers. `ogsq_s3_v5` ran on an A7S III (seventh write test,
2026-11-22): open gate, right colours, full sensor. It is the reference; nothing new is invented here.

How each part is made, and what is checked (every check must pass or nothing is written):
  identity   the FX3 image's sha256; each table the design touches is byte-identical to the A7S III's (whole table, 40 rows)
  S cells    build/build_og_s3_v3.py's `cells()` run on the FX3 image with the FX3 table addresses (from the table map
             0x857e5c) and v4's timing rows (313 x 4788 P57 E34; 313 x 4780 P239 E193), each row checked by v4's E < P rule;
             the result must be v5's 19 cells, each at the matching FX3 address with the same old and new bytes
  records    the selector 0x2514b8 (build/emu_record_selector.py) must give 0x8c0 and 0x820 the pair 0xbb31d8 / 0xbb3d90 and
             every mode the A7S III's record moved by -0x1ce20. The FX3's stock pair may differ from the A7S III's only in
             relocated pointers (A7S III value - 0x1ce20), none inside v5's changed bytes. New record = FX3 stock record with
             v5's changed bytes. Cross-check: build/build_og_s3.py's record model run on the FX3 image with the FX3's own
             packers (CamArc 0x24d6b8, CamNrs 0x6c70da, CamSig 0x6cd22e, CamLrc 0x6c7096, Dev 0x6c6618 / 0x6c64ba, fit
             0x6cce8c, log 0x9e6684), then v5's link-format words, must give the same two records byte for byte
  link rule  build/s3_linkfmt_words.py's rule on all FX3 stock records (FX3 receiver table, FX3 selector map)
  stored     build/emu_drvparam.py fx3_702: the 40 stock records equal the A7S III's; with the cells applied, index 12 plus the
             16/19 ratio and the run-time bytes left alone equals v5's stored record exactly
Design only: nothing is written to a firmware file, nothing is sent to a camera. Never run on an FX3.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import build_og_s3 as V2  # noqa: E402
import build_og_s3_v3 as V3  # noqa: E402
import build_og_s3_v4 as V4  # noqa: E402
import emu_drvparam  # noqa: E402
import emu_record_selector  # noqa: E402
import s3_linkfmt_words as LF  # noqa: E402

NAME, BUILD, REF = "ogsq_fx3_v1", "fx3_702", "a7s3_501"
BASE, SIZE = 0x108000, 0xBB8
SHA = "c90d00d807874a5309dc1b65b203287e83608ceee513cc57b53409333fb6bcba"
# FX3 table addresses, read from the table map 0x857e5c (the arguments of the constructor 0x859266) and the geometry table
T_FX3 = {"ids": 0xC53790, "colmap": 0xC53538, "rx": 0xC53FB0, "rx2": 0xC54910, "d": 0xC54B90, "tim": 0xC54190, "tim_b": 0xC54190 + 0x3C0,
         "win": 0xD46FAC, "st1": 0xD4759C, "lc": 0xD47B8C, "crop": 0xC53830, "rl": 0xD47DBC, "geo": 0xBFB188}
CLASS = {REF: 0xC709E4, BUILD: 0xC53B50}
RECORD_SHIFT = -0x1CE20
PAIR = {"L": 0xBB31D8, "R": 0xBB3D90}
STILL = {"L": 0xBC3F60, "R": 0xBC4B18}                 # 0xa000's full-height still pair (A7S III 0xbe0d80 / 0xbe1938)
PACKER = {"CamArc": 0x24D6B8, "CamNrs": 0x6C70DA, "CamSig": 0x6CD22E, "CamLrc": 0x6C7096, "Dev (first packer)": 0x6C6618,
          "Dev (second packer)": 0x6C64BA, V2.G.BEYOND: 0x6C6618}
LOG, FIT = 0x9E6684, 0x6CCE8C
STORED = 0x1FDD574 + 12 * 0x15C                       # index 12's stored record (records base from the table map)
TIMING = dict(V3.TIMING, tim=V4.TIM_A)                 # v4's rows: the ones v5 carries


def image(build):
    return emu_drvparam.image(build)


def table_lengths():
    """bytes of each table: rows x 40 (row sizes of build_og_s3_v3.ROW), the geometry row 48 bytes"""
    n = {k: V3.ROW[k] * 40 for k in V3.ROW}
    n.update(ids=160, geo=48)
    return n


def check_tables(fx, s3):
    lens = table_lengths()
    rows = []
    for k, a in T_FX3.items():
        b = V3.T[k]
        same = fx[a - BASE:a - BASE + lens[k]] == s3[b - BASE:b - BASE + lens[k]]
        rows.append({"table": k, "a7s3_501": hex(b), "fx3_702": hex(a), "bytes": lens[k], "identical": same})
        assert same, f"table {k} differs: {a:#x} against {b:#x}"
    a, b = CLASS[BUILD], CLASS[REF]
    assert fx[a - BASE:a - BASE + 40 * 8] == s3[b - BASE:b - BASE + 40 * 8], "class table differs"
    return rows


def fx_cells(fx):
    """build_og_s3_v3.cells() with the FX3 tables and v4's timing rows; returns the cells and the A7S III address each one matches"""
    saved = V3.T, V3.TIMING
    try:
        for t in TIMING.values():
            V4.check_row(t[0], t[1], t[2], t[3], t[8])
        V3.TIMING = TIMING
        V3.T = dict(T_FX3)
        cs = V3.cells(fx)
    finally:
        V3.T, V3.TIMING = saved
    to_ref = {}
    for lab, a, o, n, note in cs:
        k = min((k for k in T_FX3 if T_FX3[k] <= a), key=lambda k: a - T_FX3[k])
        to_ref[a] = V3.T[k] + (a - T_FX3[k])
    return cs, to_ref


def link_rule(fx, sel):
    """s3_linkfmt_words' rule on the FX3's own records: {record: True for a 10-bit link}"""
    ids = struct.unpack_from("<40I", fx, T_FX3["ids"] - BASE)
    cl = {}
    for i, m in enumerate(ids):
        b = struct.unpack_from("<I", fx, T_FX3["rx"] - BASE + 12 * i + 4)[0]
        assert b in (1, 2, 3)
        for r in sel[m]:
            assert cl.setdefault(r, b == 3) == (b == 3), f"record {r:#x} serves both link classes"
    for r, ten in cl.items():
        w = lambda off: struct.unpack_from("<I", fx, r + off - BASE)[0]
        for off, (v10, v12) in LF.LINK_WORDS.items():
            assert w(off) == (v10 if ten else v12), f"FX3 record {r:#x} +{off:#x}"
        assert w(0x274) - (w(0x278) & 0xFFFF) == LF.WIDTH_EXTRA[ten]
    return cl


def model_records(img, stock, still, packer, log, fit):
    """build_og_s3.Model on an image with that build's records and packers: (check report, v2-style records, + v5 link words)"""
    saved = V2.STOCK, V2.STILL, V2.PACKER, V2.LOG, V2.FIT
    try:
        V2.STOCK, V2.STILL, V2.PACKER, V2.LOG, V2.FIT = dict(stock), dict(still), dict(packer), log, fit
        m = V2.Model(img)
        rep = m.check()
        rec, _ = m.build(2848, 0)
    finally:
        V2.STOCK, V2.STILL, V2.PACKER, V2.LOG, V2.FIT = saved
    out = {}
    for h in "LR":
        r = bytearray(rec[h])
        for off, (v10, v12) in LF.LINK_WORDS.items():
            assert struct.unpack_from("<I", r, off)[0] == v10
            struct.pack_into("<I", r, off, v12)
        width = struct.unpack_from("<I", r, 0x278)[0] & 0xFFFF
        struct.pack_into("<I", r, 0x274, width + LF.WIDTH_EXTRA[False])
        out[h] = bytes(r)
    return rep, out


def main():
    des = ROOT / "modding" / "designs"
    v5 = json.loads((des / "ogsq_s3_v5.json").read_text(encoding="utf8"))
    fx, s3 = image(BUILD), image(REF)
    assert hashlib.sha256(fx).hexdigest() == SHA and v5["artifact_sha256"] == hashlib.sha256(s3).hexdigest()
    ev = {"design": NAME, "build": BUILD, "reference": "ogsq_s3_v5 (" + REF + ")"}
    ev["tables"] = check_tables(fx, s3)

    # ---- sensor cells, rebuilt on the FX3 image
    cs, to_ref = fx_cells(fx)
    ref_s = {int(p["addr"], 16): p for p in v5["patches"] if p["kind"] == "S"}
    assert len(cs) == len(ref_s) == 19
    for lab, a, o, n, note in cs:
        p = ref_s[to_ref[a]]
        assert (o.hex(), n.hex()) == (p["old"], p["new"]), (lab, hex(a))
    ev["cells"] = [{"label": lab, "fx3_702": hex(a), "a7s3_501": hex(to_ref[a]), "old": o.hex(), "new": n.hex()} for lab, a, o, n, note in cs]

    # ---- the record pair
    sel_fx, _ = emu_record_selector.records(BUILD)
    sel_s3, _ = emu_record_selector.records(REF)
    assert all([r + RECORD_SHIFT for r in sel_s3[m]] == sel_fx[m] for m in sel_s3), "the selector map is not the A7S III's moved"
    assert sel_fx[0x8C0] == sel_fx[0x820] == sorted(PAIR.values())
    ref_r = {int(p["addr"], 16): p for p in v5["patches"] if p["kind"] == "R"}
    recs, reloc = {}, {}
    for h in "LR":
        a = PAIR[h]
        p = ref_r[a - RECORD_SHIFT]
        s_old, s_new = bytes.fromhex(p["old"]), bytes.fromhex(p["new"])
        f_old = fx[a - BASE:a - BASE + SIZE]
        assert s_old == s3[a - RECORD_SHIFT - BASE:a - RECORD_SHIFT - BASE + SIZE]
        changed = [o for o in range(SIZE) if s_old[o] != s_new[o]]
        words = sorted({o & ~3 for o in range(SIZE) if s_old[o] != f_old[o]})
        for o in words:                                  # every stock difference is a relocated pointer
            x, y = struct.unpack_from("<I", s_old, o)[0], struct.unpack_from("<I", f_old, o)[0]
            assert y == x + RECORD_SHIFT and 0xB00000 < x < 0xD00000, (h, hex(o), hex(x), hex(y))
        assert not set(changed) & {o + k for o in words for k in range(4)}, "a relocated pointer inside v5's changed bytes"
        new = bytearray(f_old)
        for o in changed:
            new[o] = s_new[o]
        recs[h] = bytes(new)
        reloc[h] = [hex(o) for o in words]
    ev["records"] = {"selector_map": "every mode's records = the A7S III's - 0x1ce20 (build/emu_record_selector.py)",
                     "pair": {h: hex(a) for h, a in PAIR.items()}, "relocated_pointer_offsets": reloc}

    # ---- cross-check with the record model on the FX3's own packers, and the same run on the A7S III
    rep_fx, mod_fx = model_records(fx, PAIR, STILL, PACKER, LOG, FIT)
    rep_s3, mod_s3 = model_records(s3, V2.STOCK, V2.STILL, V2.PACKER, V2.LOG, V2.FIT)
    for rep in (rep_fx, rep_s3):
        assert all(not rep[h]["off_rule"] and not any(rep[h]["packer_words_not_reproduced_on_stock"].values()) for h in "LR"), rep
    for h in "LR":
        assert mod_s3[h] == bytes.fromhex(ref_r[V2.STOCK[h]]["new"]), f"the model does not reproduce v5's {h} record on the A7S III"
        assert mod_fx[h] == recs[h], f"the FX3 packers' {h} record differs from the ported one"
    g = lambda h, o: struct.unpack_from("<H", recs[h], o)[0]
    lrc = {h: {"input": [g(h, 0x160), g(h, 0xE)], "output": [g(h, 0x178), g(h, 0x17A)], "crop_rows": [g(h, 0x13A), g(h, 0x13E)], "final": [g(h, 0x194), g(h, 0x196)]}
           for h in "LR"}
    assert lrc == v5["lrc"], lrc
    ev["model_check"] = {"fx3_packers_reproduce_stock_words": True, "fx3_model_records_equal_port": True, "a7s3_model_reproduces_v5": True, "lrc": lrc}

    # ---- link-format rule on every FX3 stock record, and the two new records pass the 12-bit rule
    cl = link_rule(fx, sel_fx)
    assert cl[PAIR["L"]] and cl[PAIR["R"]]
    for h in "LR":
        w = lambda off: struct.unpack_from("<I", recs[h], off)[0]
        assert all(w(o) == v12 for o, (_, v12) in LF.LINK_WORDS.items()) and w(0x274) - (w(0x278) & 0xFFFF) == LF.WIDTH_EXTRA[False]
    ev["link_rule"] = {"records_10_bit": sum(cl.values()), "records_12_14_bit": len(cl) - sum(cl.values())}

    # ---- stored record
    st_fx, l0 = emu_drvparam.records(BUILD)
    st_s3, l1 = emu_drvparam.records(REF)
    assert not l0 and not l1 and all(st_fx[m][1] == st_s3[m][1] for m in st_s3), "stock stored records differ from the A7S III's"
    new_fx, l2 = emu_drvparam.records(BUILD, [(a, n) for _, a, _, n, _ in cs])
    assert not l2
    others = [hex(m) for m in st_fx if m != 0x8C0 and st_fx[m][1] != new_fx[m][1]]
    assert not others, others
    (i0, s_rec, e0), (i1, n_rec, e1) = st_fx[0x8C0], new_fx[0x8C0]
    assert i0 == i1 == 12 and not e0 and not e1
    d_rec = bytearray(n_rec)
    d_rec[6], d_rec[7] = 16, 19
    for o in V3.RUNTIME:
        d_rec[o] = s_rec[o]
    sr5 = v5["stored_record"]
    assert s_rec.hex() == sr5["stock"] and bytes(d_rec).hex() == sr5["design"], "the FX3 stored record differs from v5's"
    diff = [o for o in range(emu_drvparam.REC) if s_rec[o] != d_rec[o]]
    ev["stored_record"] = {"stock_40_records_equal_a7s3": True, "design_equals_v5": True, "bytes": len(diff)}

    # ---- the design file
    patches = []
    for lab, a, o, n, note in cs:
        p = ref_s[to_ref[a]]
        patches.append({"kind": "S", "addr": hex(a), "old": o.hex(), "new": n.hex(), "where": "file",
                        "note": p["note"] + f" | FX3: A7S III {to_ref[a]:#x}"})
    for h, nm in (("L", "left"), ("R", "right")):
        a = PAIR[h]
        p = ref_r[a - RECORD_SHIFT]
        patches.append({"kind": "R", "addr": hex(a), "old": fx[a - BASE:a - BASE + SIZE].hex(), "new": recs[h].hex(), "where": "file",
                        "note": f"0x8c0/0x820 {nm} record: v5's changed bytes on the FX3's stock record (A7S III {a - RECORD_SHIFT:#x}; relocated pointers kept)"})
    out = {"design": NAME, "build": BUILD, "camera": "ILME-FX3 (FX3), firmware 7.02",
           "title": "ogsq_s3_v5 (the A7S III's working open-gate sensor state) on the FX3's tables: drive mode 0x8c0 on the full-height sensor mode of 0xe011, "
                    "12-bit link, 2848-row first stage squeezed by Lrc into the stock picture; vertical sampling ratio 16/19",
           "status": "built from the firmware files and emulated (FX3 calculator, selector, packers); never run on an FX3. The same design (ogsq_s3_v5) works on an A7S III",
           "artifact": "cpapp-b.bin", "artifact_sha256": SHA, "generated_by": "build/build_og_fx3.py",
           "ported_from": "ogsq_s3_v5 (a7s3_501)", "mode_id": "0x8c0", "mode_index": 12, "sensor_mode_taken_from": "0xe011 (index 37)",
           "timing": v5["timing"], "summary": {"sites": len(patches), "bytes": sum(len(p["new"]) // 2 for p in patches), "sensor_cells": len(cs), "records": 2},
           "lrc": lrc, "patches": patches,
           "stored_record": {"address": hex(STORED), "stock": s_rec.hex(), "design": bytes(d_rec).hex(), "offsets_that_differ": [hex(o) for o in diff],
                             "run_time_offsets_left_alone": sr5["run_time_offsets_left_alone"]},
           "guesses": v5["guesses"],
           "not_shown": ["anything on an FX3", "that the FX3 runs the stills-to-movie switch like the A7S III (the A7S III shows a glitchy live view on each "
                         "entry into movie mode from stills until a recording starts)"] + [n for n in v5["not_shown"] if "camera" not in n]}
    (des / f"{NAME}.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf8", newline="\n")
    evd = ROOT / "evidence" / "fx3"
    evd.mkdir(parents=True, exist_ok=True)
    (evd / f"{NAME}_checks.json").write_text(json.dumps(ev, indent=1) + "\n", encoding="utf8", newline="\n")
    print(f"{NAME}: {len(cs)} sensor cells + 2 records = {len(patches)} sites, {out['summary']['bytes']} bytes; stored record {len(diff)} bytes")
    print(f"  tables identical to the A7S III's: {len(ev['tables'])}; cells = v5's at the FX3 addresses; records relocated pointers {reloc}")
    print(f"  FX3 packers rebuild both records byte for byte; link rule on {len(cl)} FX3 records; stored record = v5's; lrc {json.dumps(lrc)}")
    print("wrote", des / f"{NAME}.json", "and", evd / f"{NAME}_checks.json")


if __name__ == "__main__":
    main()
