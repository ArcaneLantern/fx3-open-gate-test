"""Build the A7S III 5.01 coprocessor design `ogh2816_s3_v1`: the sensor side of ogsq_s3_v5 (which records on the camera, F979) with a first
stage of 2,832 rows (2,816 active, from active row 8) that the first scaler (Lrc) passes ONE TO ONE, and the vertical sampling ratio 27/32.

  C:\\Python313\\python.exe -B build\\build_og_s3_native.py [--check]

Why (2026-11-28): the owner asked for the IMX510's whole picture, 4240 x 2832, in the file, as the A7 IV's real 5760 x 3840 (F906). Two facts
decide the shape:
  - The second scaler's division job takes a two-unit output only in widths that are multiples of 64, and refuses 4240 with one, two and four
    units (the A7S III's own job 0x444a74, build/division_sizes_s3.py). 4224 = 66 x 64 is the widest that fits the sensor.
  - The resize fit (the firmware's own calculation, build/emu_rc_fit.py; it returns both of the A7S III's camera-read blocks word for word)
    cuts a 16:9 shape, measured with the stored record's sampling ratio, out of the first stage's reference window. With a reference window of
    4240 x 2816 and the ratio 27/32 (the A7 IV's), that shape is 2816 x 27/32 x 16/9 = 4224 columns exactly, centred: the second scaler takes
    4224.0 x 2816.0 from (8, 0) and scales by exactly 1 into a 4224 x 2816 file. With 2,832 rows no ratio of two bytes gives a whole number.
So the file is the central 4224 x 2816 of the sensor's 4240 x 2832, pixel for pixel: 8 columns and 8 rows are left out at each edge.

What changes against ogsq_s3_v5 (modding/designs/ogsq_s3_v5.json):
  sensor cells   NONE. The sensor reads its full-height mode exactly as in v5 (matrix column 1, timing 313 x 4788, window 4240 x 2832).
  records        the two picture records of drive modes 0x820 / 0x8c0 (0xbcfff8, 0xbd0bb0):
                   stage    build_og_s3.Model.build(2832, 8): the row model that made v2..v5's records (v5 = build(2848, 0)), a first stage of
                            2,832 rows starting 8 active rows into the frame; the six link-format words of v5 (12-bit link)
                   Lrc on   build_fhnative.assemble (the firmware's split planner and packers; it rebuilds the A7S III's stock FF 4K pair byte
                            for byte): Lrc picture 4240 x 2816 at step 4096 both ways, where v5 squeezes the rows into 2,392
                 The header's third window (+0x10..+0x16), from which the reference window is made (0x6c5eba / 0x6c5f08 on the A7 IV), then
                 holds 4240 x 2816.
  stored record  v5's bytes with +6/+7 = 27/32 instead of 16/19.

Self-checks (each asserted):
  1. build(2848, 0) + the link-format words gives v5's two records byte for byte (so this path is the one that made the camera-proven records)
  2. assemble() rebuilds the stock pair from its own geometry byte for byte
  3. the new pair passes build/lint_split_record.py (rules that hold on every stock split pair of eight builds)
  4. every field before the first scaler's output that differs from v5 is one the row model moves with the stage (H, r0) or the header window
  5. the resize calculation: the two camera-read A7S III cases are reproduced, and the design gives 4224.0 x 2816.0 from (8, 0)
Design only: nothing is written to a firmware file, nothing is sent to a camera. Never run on a camera.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import locate_file  # noqa: E402
import build_og_s3 as V2  # noqa: E402
import build_fhstage as F  # noqa: E402
import build_fhnative as N  # noqa: E402
import build_fhpost as P  # noqa: E402
import lint_split_record as LINT  # noqa: E402
import s3_linkfmt_words as LF  # noqa: E402
import emu_rc_fit as RC  # noqa: E402

NAME, BASE, SIZE = "ogh2816_s3_v1", 0x108000, 0xBB8
H, R0 = 2832, 8                                       # stage rows (16 of them margin) and the stage's first active row
OUT_W, OUT_H = 4240, H - 16                            # the Lrc picture
FILE_W, FILE_H = 4224, 2816
PA = (27, 32)                                          # stored record +6 / +7
HALVES = (2144, 2096)                                  # final columns per half (stock)
u16 = N.u16


def link_words(rec):
    """v5's six link-format words (a 12-bit sensor link), on a record that holds the 10-bit values."""
    r = bytearray(rec)
    w = lambda off: struct.unpack_from("<I", r, off)[0]
    for off, (v10, v12) in sorted(LF.LINK_WORDS.items()):
        assert w(off) == v10, hex(off)
        struct.pack_into("<I", r, off, v12)
    width = w(0x278) & 0xFFFF
    assert w(0x274) == width + LF.WIDTH_EXTRA[True]
    struct.pack_into("<I", r, 0x274, width + LF.WIDTH_EXTRA[False])
    return bytes(r)


def rc(src, out, ref, pa):
    words = [2, 1, 1, 1, 1, src[0], src[1], out[0], out[1], HALVES[0], src[1], HALVES[1], src[1], ref[0], ref[1], 4240, 2832, 4240, 2832, 2]
    e = RC.run(ref[1], (1, 1, pa[0], pa[1]), input_words=words)
    assert not e["error"], e["error"]
    return e


def main():
    des = ROOT / "modding" / "designs"
    v5 = json.loads((des / "ogsq_s3_v5.json").read_text(encoding="utf8"))
    img = V2.image()
    sha = hashlib.sha256(img).hexdigest()
    assert v5["artifact_sha256"] == sha
    a7 = locate_file.locate("a7iv_602", "cpapp-b.bin").read_bytes()
    m = V2.Model(img)
    stock = {h: bytes(m.stock[h]) for h in "LR"}
    v5rec = {("L" if int(p["addr"], 16) == V2.STOCK["L"] else "R"): bytes.fromhex(p["new"]) for p in v5["patches"] if p["kind"] == "R"}
    assert all(bytes.fromhex(p["old"]) == stock["L" if int(p["addr"], 16) == V2.STOCK["L"] else "R"] for p in v5["patches"] if p["kind"] == "R")
    # 1. the path reproduces v5
    full, _ = m.build(2848, 0)
    again = {h: link_words(full[h]) for h in "LR"}
    assert again == v5rec, "build(2848, 0) + link-format words is not ogsq_s3_v5"
    # the stage of this design, squeezed form (as v5 at another height and start row)
    stage, _ = m.build(H, R0)
    sq = {h: link_words(stage[h]) for h in "LR"}
    hdr = lambda r: struct.unpack_from("<12H", r, 0)
    assert hdr(sq["L"])[4:] == (20, 28 + R0, 2408, H, 32, 36 + R0, 2396, H - 16) and hdr(sq["R"])[4:] == (1772, 28 + R0, 2512, H, 1772, 36 + R0, 2500, H - 16), (hdr(sq["L"]), hdr(sq["R"]))
    assert u16(sq["L"], 0x95E) == R0 and u16(sq["R"], 0x95E) == R0
    # 2. the planner path on stock
    M = F.Model(a7)
    frame, crop, target = N.pair_inputs(stock)
    assert (frame, crop, target) == ((4264, 2408), (12, 8, 4240, 2392), (4240, 2392))
    got, _ = N.assemble(M, stock, target, mirror_as=stock)
    assert all(bytes(got[h]) == stock[h] for h in "LR"), "the stock pair is not rebuilt"
    # the design: Lrc one to one
    assert N.pair_inputs(sq) == ((4264, H), (12, 8, 4240, H - 16), (4240, 2392))
    rec, facts = N.assemble(M, sq, (OUT_W, OUT_H), mirror_as=stock)
    rec = {h: bytes(rec[h]) for h in "LR"}
    assert N.pair_inputs(rec) == ((4264, H), (12, 8, 4240, H - 16), (OUT_W, OUT_H))
    # 3. lint
    lint, lf = LINT.lint_design_records(rec["L"], rec["R"])
    broken = {r: d for r, (ok, d) in lint.items() if not ok}
    assert not broken, broken
    lrc = {}
    for h in "LR":
        k = LINT.lrc(rec[h])
        lrc[h] = {"input": list(k["in"]), "output": list(k["out"]), "step_q12": list(k["step"]), "start": list(k["start"])}
        assert k["step"] == (4096, 4096) and k["in"][1] == H and k["out"][1] == H, k
    assert lf["seam"] == HALVES[0] and lf["row_pad"] == 8 and lf["pad"] == 12
    # 4. against v5: before the Lrc output only the stage's own fields move (the row model's), the header windows among them
    rule_fields = {h: {int(off, 16) for off, kind, *_ in m.rules[h]} for h in "LR"}
    pack_fields = {h: {po + k for blk in m.layout.values() for _, po, _ in blk for k in (0, 2)} for h in "LR"}
    for h in "LR":                                     # the second copy of the Dev words, which stock mirrors (build_fhpost.finish)
        pack_fields[h] |= {o + P.CLV for o in pack_fields[h] if 0x78C <= o < 0x78C + P.CLV}
    pre, post = {}, {}
    for h in "LR":
        ch = [o for o in range(0, SIZE, 2) if rec[h][o:o + 2] != v5rec[h][o:o + 2]]
        pre[h] = [o for o in ch if o < 0x174 or o >= 0x1D8]
        post[h] = [o for o in ch if 0x174 <= o < 0x1D8]
        odd = [hex(o) for o in pre[h] if o not in rule_fields[h] and o not in pack_fields[h] and not N.COLS[0] <= o < N.COLS[1] and o not in (0x590, 0x594)]
        assert not odd, (h, odd)
    # the same stage in the squeezed form differs from this design only after the first scaler and in the packed words
    for h in "LR":
        d = [o for o in range(0, SIZE, 2) if rec[h][o:o + 2] != sq[h][o:o + 2]]
        assert all(N.COLS[0] <= o < N.COLS[1] or o in pack_fields[h] or o in (0x64E, *N.DCV_COPIES, 0x768, 0x906, 0x914, 0x934) for o in d), (h, [hex(o) for o in d])
    # 5. the resize calculation
    cam2 = rc((4240, 2392), (3840, 2560), (4240, 2392), (16, 19))          # second write test (wrong records): columns 329..3910
    cam4 = rc((4240, 2392), (3840, 2560), (4240, 2832), (16, 19))          # v2..v5 on the camera: the whole picture
    assert cam2["words"] == [4240, 2392, 329, 0, 3580, 2392, 2596, 0, 3000, 0], cam2["words"]
    assert cam4["words"][:6] == [4240, 2392, 0, 0, 4240, 2391] and (cam4["pixel_aspect_q12"], cam4["scale_v_q12"]) == (3449, 3459), cam4
    ref = (4240, hdr(rec["R"])[11])
    assert ref == (4240, OUT_H)
    fit_file = rc((OUT_W, OUT_H), (FILE_W, FILE_H), ref, PA)
    fit_2560 = rc((OUT_W, OUT_H), (3840, 2560), ref, PA)
    want = [OUT_W, OUT_H, 8, 0, FILE_W, FILE_H, 0, 0, 0, 0]
    assert fit_file["words"] == want and fit_2560["words"] == want, (fit_file["words"], fit_2560["words"])
    assert (fit_file["pixel_aspect_q12"], fit_file["scale_h_q12"], fit_file["scale_v_q12"]) == (3456, 4096, 4096)
    if "--check" in sys.argv:
        print("all five self-checks pass")
        return
    # ---- the design file: v5's sensor cells, the two records, v5's stored record with 27/32
    patches = [p for p in v5["patches"] if p["kind"] == "S"]
    assert len(patches) == len(v5["patches"]) - 2
    for h, nm in (("L", "left"), ("R", "right")):
        n = sum(rec[h][o:o + 2] != stock[h][o:o + 2] for o in range(0, SIZE, 2))
        n5 = sum(rec[h][o:o + 2] != v5rec[h][o:o + 2] for o in range(0, SIZE, 2))
        patches.append({"kind": "R", "addr": hex(V2.STOCK[h]), "old": stock[h].hex(), "new": rec[h].hex(), "where": "file",
                        "note": f"0x8c0 {nm} record: first stage of {H} rows ({H - 16} active) from active row {R0} of the full-height frame, passed one to one by "
                                f"Lrc ({OUT_W} x {OUT_H} front end); link-format words for a 12-bit link; {n} fields differ from stock, {n5} from ogsq_s3_v5"})
    patches.sort(key=lambda p: int(p["addr"], 16))
    sr = v5["stored_record"]
    s_rec, d_rec = bytes.fromhex(sr["stock"]), bytearray.fromhex(sr["design"])
    assert (d_rec[6], d_rec[7]) == (16, 19) and s_rec[4:8] == b"\x01\x01\x01\x01"
    d_rec[6], d_rec[7] = PA
    diff = [o for o in range(len(s_rec)) if s_rec[o] != d_rec[o]]
    assert diff == [int(o, 16) for o in sr["offsets_that_differ"]], "the stored record's site is not v5's"
    out = {"design": NAME, "build": "a7s3_501", "camera": "ILCE-7SM3 (A7S III), firmware 5.01",
           "title": f"ogsq_s3_v5's sensor side with a first stage of {H} rows ({H - 16} active, from active row {R0}) that the first scaler passes one to one: "
                    f"front end {OUT_W} x {OUT_H}; vertical sampling ratio {PA[0]}/{PA[1]}, so that the second scaler takes the central {FILE_W} x {FILE_H} at scale 1",
           "status": "built from the firmware files and emulated in parts; never run on a camera. ogsq_s3_v5, whose sensor cells it keeps, records on the camera (F979)",
           "artifact": "cpapp-b.bin", "artifact_sha256": sha, "generated_by": "build/build_og_s3_native.py",
           "replaces": "ogsq_s3_v5 in the 4224x2816 state (the two records and two bytes of the stored record; every sensor cell is v5's)",
           "mode_id": v5["mode_id"], "mode_index": v5["mode_index"], "sensor_mode_taken_from": v5["sensor_mode_taken_from"], "timing": v5["timing"],
           "summary": {"sites": len(patches), "bytes": sum(len(p["new"]) // 2 for p in patches), "sensor_cells": len(patches) - 2, "records": 2,
                       "stage": {"rows": H, "active_rows": H - 16, "first_active_row": R0, "frame": [4264, H], "crop": [12, 8, 4240, H - 16]},
                       "front_end": [OUT_W, OUT_H], "final_columns": list(HALVES), "seam": lf["seam"], "column_pad": lf["pad"], "row_pad": lf["row_pad"],
                       "history_line": lf["history_line"], "source_windows": lf["source_windows"],
                       "reference_window": list(ref), "sampling_ratio": list(PA),
                       "expected_working_state": {"sensor": [4240, 2832], "stage": [4264, H], "front_end": [OUT_W, OUT_H],
                                                  "second_scaler_takes": {"size": fit_file["size"], "start": fit_file["start"], "block_words": fit_file["words"]},
                                                  "file": "4224x2816 with outsz4224_s3_v1 (scale 1), or 3840x2560 with outsz2560_s3_v1 (scale 1.1 both ways)"}},
           "lrc": lrc,
           "self_checks": ["build_og_s3.Model.build(2848, 0) + the link-format words = ogsq_s3_v5's records, byte for byte",
                           "build_fhnative.assemble rebuilds the stock FF 4K pair byte for byte",
                           "build/lint_split_record.py: no rule broken",
                           "against v5, outside the first scaler's output every changed field is a row-model field, a planner field or a packed word",
                           "build/emu_rc_fit.py returns the two camera-read A7S III blocks (second write test; v2..v5) and, for this design, "
                           f"{fit_file['words']}"],
           "resize_fit": {"camera_second_write_test": {"words": cam2["words"], "size": cam2["size"], "start": cam2["start"]},
                          "camera_v2_to_v5": {"words": cam4["words"], "size": cam4["size"], "start": cam4["start"], "pixel_aspect_q12": cam4["pixel_aspect_q12"],
                                              "scale_v_q12": cam4["scale_v_q12"]},
                          "this_design_into_4224x2816": {k: fit_file[k] for k in ("words", "size", "start", "pixel_aspect_q12", "scale_h_q12", "scale_v_q12")},
                          "this_design_into_3840x2560": {k: fit_2560[k] for k in ("words", "size", "start", "pixel_aspect_q12", "scale_h_q12", "scale_v_q12")}},
           "changed_fields_against_v5": {h: {"before_the_first_scaler_output_and_words": [hex(o) for o in pre[h]], "first_scaler_output_0x174_0x1d8": [hex(o) for o in post[h]]} for h in "LR"},
           "patches": patches,
           "stored_record": {"address": sr["address"], "stock": sr["stock"], "design": bytes(d_rec).hex(), "offsets_that_differ": sr["offsets_that_differ"],
                             "run_time_offsets_left_alone": sr.get("run_time_offsets_left_alone"),
                             "extra": [{"offset": "0x6", "old": "01", "new": "%02x" % PA[0], "note": "vertical sampling ratio, numerator (v5: 16)"},
                                       {"offset": "0x7", "old": "01", "new": "%02x" % PA[1], "note": "vertical sampling ratio, denominator (v5: 19)"}]},
           "not_shown": ["that the A7S III's stages after the first scaler take 2,816 rows at 24p (stock 4K: 2,392; the A7 IV went from 2,438 to 3,840, F906)",
                         "a first stage that starts 8 rows into the frame on this body (the A7 IV ran such stages: F658, F664; v5 starts at row 0)",
                         "that the reference window follows the header's third window on this body as it does on the A7 IV (it followed the records in the "
                         "second and fourth write tests)",
                         "anything on a camera"]}
    (des / f"{NAME}.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf8", newline="\n")
    print(f"{NAME}: {len(patches)} sites, {out['summary']['bytes']} bytes; records differ from v5 in "
          f"{ {h: len(pre[h]) + len(post[h]) for h in 'LR'} } fields; stored record site {len(diff)} bytes, ratio {PA[0]}/{PA[1]}")
    print("lrc", json.dumps(lrc))
    print("second scaler takes", fit_file["size"], "from", fit_file["start"], "words", fit_file["words"])
    print("wrote", des / f"{NAME}.json")


if __name__ == "__main__":
    main()
