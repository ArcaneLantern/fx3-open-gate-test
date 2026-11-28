"""Build the FX3 7.02 coprocessor design `ogh2816_fx3_v1`: the A7S III's `ogh2816_s3_v1` on the FX3 (the sensor side of the 4224 x 2816 state).

  C:\\Python313\\python.exe -B build\\build_og_fx3_native.py [--check]

What it is (modding/A7S3_PORT.md section 32, findings F1239-F1242): the sensor's own cells stay those of the open-gate state, the first stage
takes 2,832 rows from active row 8 (2,816 active) and the first scaler passes them ONE TO ONE; with the sampling ratio 27/32 in the stored
records the second scaler takes the central 4224.0 x 2816.0 of the 4240 x 2816 front end at scale 1.

On the FX3 the base is `ogsq_fx3_v2` (the kit's sensor step since 2026-11-26: drive modes 0x8c0 = 23.98p / 24p and 0x820 = 29.97p / 25p, which
share the picture-record pair 0xbb31d8 / 0xbb3d90, with the stored records of both modes in their NTSC and PAL forms):
  cells          v2's 38 cells, unchanged
  records        the FX3's stock pair with the bytes `ogh2816_s3_v1` changes on the A7S III (the way `ogsq_fx3_v1` was made from `ogsq_s3_v5`:
                 the FX3 app is the A7S III's relinked, and the two stock pairs differ only in relocated pointers outside those bytes)
  stored records v2's four (0x820 and 0x8c0, NTSC and PAL) with +6/+7 = 27/32 instead of 16/19

Checks (each asserted):
  1. the FX3's stock pair equals the A7S III's at every byte the A7S III design changes
  2. the same two records come out of the generator's own path on the FX3 image with the FX3's packers: build_og_s3.Model.build(2832, 8), the
     link-format words, then build_fhnative.assemble (Lrc 4240 x 2816 at step 4096), byte for byte
  3. build/lint_split_record.py: no rule broken
  4. v2's records are the FX3's stock pair with `ogsq_s3_v5`'s changed bytes (so the base is the state that records on FX3s)
  5. the resize calculation gives 4240, 2816, 8, 0, 4224, 2816, 0, 0, 0, 0 (build_og_s3_native.rc: the calculation that returns the A7S III's
     camera-read blocks; the FX3's closing dump of 2026-11-24 shows the same v5 block)
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
import build_og_fx3 as FX  # noqa: E402
import build_og_s3_native as S3N  # noqa: E402
import build_fhstage as F  # noqa: E402
import build_fhnative as N  # noqa: E402
import lint_split_record as LINT  # noqa: E402

NAME, BUILD, SIZE = "ogh2816_fx3_v1", "fx3_702", 0xBB8
H, R0, PA = S3N.H, S3N.R0, S3N.PA
OUT_W, OUT_H, FILE_W, FILE_H = S3N.OUT_W, S3N.OUT_H, S3N.FILE_W, S3N.FILE_H


def changed_bytes(old, new):
    return [o for o in range(SIZE) if old[o] != new[o]]


def main():
    des = ROOT / "modding" / "designs"
    v2 = json.loads((des / "ogsq_fx3_v2.json").read_text(encoding="utf8"))
    s3n = json.loads((des / "ogh2816_s3_v1.json").read_text(encoding="utf8"))
    s3v5 = json.loads((des / "ogsq_s3_v5.json").read_text(encoding="utf8"))
    fx = FX.image(BUILD)
    sha = hashlib.sha256(fx).hexdigest()
    assert sha == FX.SHA == v2["artifact_sha256"]
    a7 = locate_file.locate("a7iv_602", "cpapp-b.bin").read_bytes()
    rd = lambda a: fx[a - FX.BASE:a - FX.BASE + SIZE]
    stock = {h: rd(a) for h, a in FX.PAIR.items()}
    half = lambda d, h: next(p for p in d["patches"] if p["kind"] == "R" and int(p["addr"], 16) == V2.STOCK[h])
    # 1. transplant: the FX3's stock records with the A7S III design's changed bytes
    rec, n_changed = {}, {}
    for h in "LR":
        p = half(s3n, h)
        old, new = bytes.fromhex(p["old"]), bytes.fromhex(p["new"])
        ch = changed_bytes(old, new)
        assert all(stock[h][o] == old[o] for o in ch), f"the FX3's stock {h} record differs from the A7S III's inside the changed bytes"
        r = bytearray(stock[h])
        for o in ch:
            r[o] = new[o]
        rec[h], n_changed[h] = bytes(r), len(ch)
    # 4. the base: v2's records are stock + v5's changed bytes
    v2rec = {h: bytes.fromhex(next(p for p in v2["patches"] if p["kind"] == "R" and int(p["addr"], 16) == FX.PAIR[h])["new"]) for h in "LR"}
    for h in "LR":
        p = half(s3v5, h)
        old, new = bytes.fromhex(p["old"]), bytes.fromhex(p["new"])
        want = bytearray(stock[h])
        for o in changed_bytes(old, new):
            want[o] = new[o]
        assert bytes(want) == v2rec[h], f"ogsq_fx3_v2's {h} record is not the stock record with ogsq_s3_v5's bytes"
    # 2. the generator's own path on the FX3 image
    saved = V2.STOCK, V2.STILL, V2.PACKER, V2.LOG, V2.FIT
    try:
        V2.STOCK, V2.STILL, V2.PACKER, V2.LOG, V2.FIT = dict(FX.PAIR), dict(FX.STILL), dict(FX.PACKER), FX.LOG, FX.FIT
        m = V2.Model(fx)
        full, _ = m.build(2848, 0)
        assert {h: S3N.link_words(full[h]) for h in "LR"} == v2rec, "build(2848, 0) + link-format words is not ogsq_fx3_v2's pair"
        stage, _ = m.build(H, R0)
    finally:
        V2.STOCK, V2.STILL, V2.PACKER, V2.LOG, V2.FIT = saved
    sq = {h: S3N.link_words(stage[h]) for h in "LR"}
    M = F.Model(a7)
    got, _ = N.assemble(M, stock, N.pair_inputs(stock)[2], mirror_as=stock)
    assert all(bytes(got[h]) == stock[h] for h in "LR"), "the FX3's stock pair is not rebuilt"
    own, _ = N.assemble(M, sq, (OUT_W, OUT_H), mirror_as=stock)
    diff = {h: [hex(o) for o in range(0, SIZE, 2) if bytes(own[h][o:o + 2]) != rec[h][o:o + 2]] for h in "LR"}
    assert not any(diff.values()), ("the transplanted records are not what the generator makes on the FX3 image", diff)
    assert N.pair_inputs(rec) == ((4264, H), (12, 8, 4240, H - 16), (OUT_W, OUT_H))
    # 3. lint
    lint, lf = LINT.lint_design_records(rec["L"], rec["R"])
    broken = {r: d for r, (ok, d) in lint.items() if not ok}
    assert not broken, broken
    lrc = {}
    for h in "LR":
        k = LINT.lrc(rec[h])
        lrc[h] = {"input": list(k["in"]), "output": list(k["out"]), "step_q12": list(k["step"]), "start": list(k["start"])}
        assert k["step"] == (4096, 4096) and k["in"][1] == H and k["out"][1] == H
    # 5. the fit
    ref = (4240, struct.unpack_from("<12H", rec["R"], 0)[11])
    assert ref == (4240, OUT_H)
    fit_file, fit_2560 = S3N.rc((OUT_W, OUT_H), (FILE_W, FILE_H), ref, PA), S3N.rc((OUT_W, OUT_H), (3840, 2560), ref, PA)
    want = [OUT_W, OUT_H, 8, 0, FILE_W, FILE_H, 0, 0, 0, 0]
    assert fit_file["words"] == want == fit_2560["words"]
    if "--check" in sys.argv:
        print("all five checks pass")
        return
    # ---- the design file: v2's with the two records and the ratio bytes
    out = json.loads(json.dumps(v2))
    for p in out["patches"]:
        if p["kind"] != "R":
            continue
        h = "L" if int(p["addr"], 16) == FX.PAIR["L"] else "R"
        assert bytes.fromhex(p["old"]) == stock[h]
        p["new"] = rec[h].hex()
        p["note"] = (f"0x820 / 0x8c0 {'left' if h == 'L' else 'right'} record: first stage of {H} rows ({H - 16} active) from active row {R0}, passed one to one by Lrc "
                     f"({OUT_W} x {OUT_H} front end); link-format words for a 12-bit link; the bytes ogh2816_s3_v1 changes on the A7S III ({n_changed[h]})")
    assert [p for p in out["patches"] if p["kind"] == "S"] == [p for p in v2["patches"] if p["kind"] == "S"]
    for mode, sr in out["stored_records"].items():
        for system in ("ntsc", "pal"):
            d = bytearray.fromhex(sr[system]["design"])
            s = bytes.fromhex(sr[system]["stock"])
            assert (d[6], d[7]) == (16, 19) and s[4:8] == b"\x01\x01\x01\x01"
            d[6], d[7] = PA
            assert {hex(k) for k in range(len(s)) if s[k] != d[k]} <= set(sr["offsets_that_differ"])     # one list for both modes and systems
            sr[system]["design"] = bytes(d).hex()
    out.update({"design": NAME, "generated_by": "build/build_og_fx3_native.py",
                "title": f"ogsq_fx3_v2's sensor side (0x8c0 and 0x820) with a first stage of {H} rows ({H - 16} active, from active row {R0}) that the first scaler passes "
                         f"one to one: front end {OUT_W} x {OUT_H}; vertical sampling ratio {PA[0]}/{PA[1]}, so that the second scaler takes the central {FILE_W} x {FILE_H} at scale 1",
                "status": "built from the firmware files and emulated in parts; never run on a camera. ogsq_fx3_v2's cells are kept (0x8c0 at 23.98p records on FX3s; "
                          "0x820 at 25p ran as a tester's own design); the records are the A7S III's ogh2816_s3_v1, which has not run on a camera either",
                "ported_from": "ogh2816_s3_v1 (A7S III 5.01, modding/A7S3_PORT.md section 32)",
                "replaces": "ogsq_fx3_v2 in the 4224x2816 state (the two records and two bytes of each stored record; every sensor cell is v2's)",
                "lrc": lrc})
    out.pop("supersedes", None)
    out["summary"] = dict(v2["summary"], bytes=sum(len(p["new"]) // 2 for p in out["patches"]),
                          stage={"rows": H, "active_rows": H - 16, "first_active_row": R0, "frame": [4264, H], "crop": [12, 8, 4240, H - 16]},
                          front_end=[OUT_W, OUT_H], reference_window=list(ref), sampling_ratio=list(PA),
                          expected_working_state={"second_scaler_block_words": fit_file["words"],
                                                  "file": "4224x2816 with outsz4224_fx3_v1 (scale 1), or 3840x2560 with outsz2560_fx3_v1 (scale 1.1 both ways)"})
    out["self_checks"] = ["the FX3's stock pair equals the A7S III's at every byte ogh2816_s3_v1 changes",
                          "build_og_s3.Model.build(2832, 8) with the FX3's packers + link words + build_fhnative.assemble gives the same two records byte for byte",
                          "build/lint_split_record.py: no rule broken",
                          "ogsq_fx3_v2's records = the stock pair with ogsq_s3_v5's bytes; build(2848, 0) + link words reproduces them",
                          f"resize calculation: {fit_file['words']}"]
    out["stored_record_note"] = v2.get("stored_record_note", "") + " | this design: +6/+7 = 27/32 (v2: 16/19)"
    out["not_shown"] = ["that the stages after the first scaler take 2,816 rows at 24p / 25p / 29.97p on this body (stock 2,392)",
                        "a first stage that starts 8 rows into the frame on this body", "29.97p open gate on any camera (as ogsq_fx3_v2)", "anything on a camera"]
    (des / f"{NAME}.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf8", newline="\n")
    print(f"{NAME}: {len(out['patches'])} sites, {out['summary']['bytes']} bytes; records changed in {n_changed} bytes; stored records {sorted(out['stored_records'])} NTSC and PAL at {PA[0]}/{PA[1]}")
    print("lrc", json.dumps(lrc))
    print("second scaler takes", fit_file["size"], "from", fit_file["start"])


if __name__ == "__main__":
    main()
