"""A7S III 5.01: function-level emulation of the 4224x2816 encoder-side designs, stock against changed, in the A7S III's own av-cam.bin and
libmpr.so (2026-11-28). The changes are applied in emulated memory only. Nothing here is hardware; nothing was run on a camera.

  ogfile4224_s3_v1       build/build_og57.py --build a7s3_501 --raster 4224 2816 --name ogfile4224_v1 --meta      the state's encoder step
  ogfile4224nm_s3_v1     ... --name ogfile4224nm_v1 (no --meta)                                                 the MP4 headers keep 3840x2160
  ogfile4224r300_s3_v1   ... --name ogfile4224_v1 --meta --rate300                                              the 100M settings at 300 Mbps

The checks are build/run_og57_emu_fx30.py's (the FX30's 5.7K step) without its no-B-picture part, pointed at the A7S III's functions. The A7S III's
av-cam functions are the A7 IV's whole bodies (build/avcam_fnport.py, one place each), all 0x44ec higher:
  matcher 0x21fc6c (= A7 IV 0x21b780), memory function 0x217bb0 (0x2136c4), start-block builder 0x21b9ac (0x2174c0), allocator 0x2270bc
  (0x222bd0), log 0x276c78 (0x27278c) with its head 0x40 before and the memcpy / memset wrappers 0x51c / 0x534 after it, as on the A7 IV and A1;
  clip format: the A7 IV's 0x190128 but one log line number (found below by its body), the one-argument form
  tables: descriptors 0x38d968 (689), unit types 0x38d8c8, profiles 0x3a5cf8 / 0x3bd2f8, clip 0x38bbdc: the A7 IV's bytes (asserted), + 0xa02c
  codec firmware: vcd_firmware_imola2.bin is the A7 IV's file byte for byte (asserted): the memory need is build/emu_vcd_chmem.py's
  libmpr.so: g_videoParamComb 0x2d4408; MP4 writer = the A7 IV's moved by +0x1134 (build/emu_mp4_meta.py FUNCS)

Run with the Python that has Unicorn:  C:\\Python313\\python.exe -B build/run_og4224_emu_s3.py     writes evidence/a7s3/og4224_emu_s3.json

--build fx3_702 (2026-11-28): the FX3's three designs (ogfile4224_fx3_v1, ogfile4224nm_fx3_v1, ogfile4224r300_fx3_v1: 43 descriptors, 23.98p, 25p
and 29.97p) in the FX3 7.02's own av-cam.bin and libmpr.so, with the functions and tables build/emu_ogfilesi_fx3.py locates (matcher 0x225eb8,
memory function 0x21dd54, the FX3's own start-block builder 0x221b50, clip format 0x196b80); writes evidence/fx3/og4224_emu_fx3.json.
"""
import json
import re
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import avcam_fnport  # noqa: E402
import emu_mp4_meta  # noqa: E402
import emu_vcd_chmem as V  # noqa: E402
import locate_file  # noqa: E402
import parse_dmmcfg  # noqa: E402
import run_ogfile_emu as E  # noqa: E402

AVB = E.AVB
BUILD = sys.argv[sys.argv.index("--build") + 1] if "--build" in sys.argv else "a7s3_501"
SHIFT = 0xA02C
DESC, NDESC, UNIT, CLIPT = 0x38393C + SHIFT, 689, 0x38389C + SHIFT, 0x38BBDC
PROFILES = ((0x39BCCC + SHIFT, 373), (0x3B32CC + SHIFT, 316))
COMB = 0x2D32B8 + 0x1150
A7_FN = {"MATCH": 0x21B780, "UNITFN": 0x2136C4, "BUILDER": 0x2174C0, "DMM_OPEN": 0x222BD0, "LOGF": 0x27278C}
S3_FN = {"MATCH": 0x21FC6C, "UNITFN": 0x217BB0, "BUILDER": 0x21B9AC, "DMM_OPEN": 0x2270BC, "LOGF": 0x276C78}
D = ROOT / "modding" / "designs"
W0, H0 = 3840, 2160
DEST = ROOT / "evidence/a7s3/og4224_emu_s3.json"
NAMES = ("ogfile4224_s3_v1", "ogfile4224nm_s3_v1", "ogfile4224r300_s3_v1")
CAMERA, N_DESC_CHANGED = "A7S III", 29
if BUILD == "fx3_702":
    import emu_ogfilesi_fx3 as FX3  # noqa: E402
    DESC, NDESC, UNIT, PROFILES, COMB = FX3.DESC, FX3.NDESC, FX3.UNIT, FX3.PROFILES, FX3.COMB
    DEST = ROOT / "evidence/fx3/og4224_emu_fx3.json"
    NAMES = ("ogfile4224_fx3_v1", "ogfile4224nm_fx3_v1", "ogfile4224r300_fx3_v1")
    CAMERA, N_DESC_CHANGED = "FX3", 43


def find_functions(a7, s3):
    """The facts the docstring relies on, asserted. Returns the function table (absolute addresses) and the frame-rate table's offset."""
    if BUILD == "fx3_702":
        FX3.find_functions(a7, s3)
        fps = s3.find(a7[0x3220A0:0x3220A0 + 60])
        assert fps > 0 and s3.find(a7[0x3220A0:0x3220A0 + 60], fps + 1) < 0
        assert locate_file.locate(BUILD, "vcd_firmware_imola2.bin").read_bytes() == locate_file.locate("a7iv_602", "vcd_firmware_imola2.bin").read_bytes()
        return dict(FX3.FN), fps
    got = avcam_fnport.port(BUILD, list(A7_FN.values()), a7, s3)
    assert {k: v[0] for k, v in got.items()} == {A7_FN[k]: S3_FN[k] for k in A7_FN}, got
    fn = dict(S3_FN)
    fn["LOGH"], fn["MEMCPY"], fn["MEMSET"] = fn["LOGF"] - 0x40, fn["LOGF"] + 0x51C, fn["LOGF"] + 0x534
    # the clip-format function: the A7 IV's body but one `mov w7, #line`, at exactly one place
    n = avcam_fnport.a7iv_size(0x190128) // 4
    a = avcam_fnport.normalise(struct.unpack_from("<%dI" % n, a7, 0x190128))
    hits = []
    for at in range(0x180000, 0x1B0000, 4):
        b = avcam_fnport.normalise(struct.unpack_from("<%dI" % n, s3, at))
        diff = [k for k in range(n) if a[k] != b[k]]
        if len(diff) <= 1 and all(a[k] & 0xFFE0001F == b[k] & 0xFFE0001F == 0x52800007 for k in diff):
            hits.append(at)
    assert len(hits) == 1, [hex(h) for h in hits]
    fn["CLIPFN"] = hits[0]
    # log head and the memory wrappers: the A7 IV's instructions, pages and branch targets aside
    strip = lambda ws: [w & 0x9F00001F if w & 0x9F000000 == 0x90000000 else w & 0xFFC003FF if w & 0x7F800000 == 0x11000000 or w & 0xFFC00000 == 0x39400000
                        or w & 0xFFC00000 == 0x39000000 else w & 0xFC000000 if w & 0x7C000000 == 0x14000000 else w for w in ws]
    assert strip(struct.unpack_from("<16I", a7, 0x27274C)) == strip(struct.unpack_from("<16I", s3, fn["LOGH"]))
    for a7_at, at in ((0x272CA8, fn["MEMCPY"]), (0x272CC0, fn["MEMSET"])):
        wa, wb = struct.unpack_from("<6I", a7, a7_at), struct.unpack_from("<6I", s3, at)
        assert wa[:2] == wb[:2] and wa[3:] == wb[3:], (hex(a7_at), hex(at))
    # the tables are the A7 IV's bytes
    assert s3[UNIT:UNIT + 0xA0] == a7[0x38389C:0x38389C + 0xA0] and s3[DESC:DESC + NDESC * 0x90] == a7[0x38393C:0x38393C + NDESC * 0x90]
    for (base, cnt), a7base in zip(PROFILES, (0x39BCCC, 0x3B32CC)):
        assert s3[base:base + cnt * 0x100] == a7[a7base:a7base + cnt * 0x100]
    fps = s3.find(a7[0x3220A0:0x3220A0 + 60])
    assert fps > 0 and s3.find(a7[0x3220A0:0x3220A0 + 60], fps + 1) < 0
    assert locate_file.locate(BUILD, "vcd_firmware_imola2.bin").read_bytes() == locate_file.locate("a7iv_602", "vcd_firmware_imola2.bin").read_bytes()
    return dict({"DESC": AVB + DESC}, **{k: AVB + v for k, v in fn.items()}), fps


def apply(data, binary, name):
    out = bytearray(data)
    for off, nb in E.pokes(D / f"{name}_pokes_{binary}.txt"):
        out[off:off + len(nb)] = nb
    return bytes(out)


def runs_of(a, b):
    out = []
    for i in (i for i in range(len(a)) if a[i] != b[i]):
        if out and i == out[-1][1] + 1:
            out[-1][1] = i
        else:
            out.append([i, i])
    return [{"offset": hex(x), "bytes": y - x + 1, "first": a[x:y + 1].hex(), "second": b[x:y + 1].hex()} for x, y in out]


def check(name, av, lm, size_of, FN):
    dz = json.loads((D / f"{name}.json").read_text(encoding="utf8"))
    assert dz["build"] == BUILD
    W1, H1 = dz["raster"]
    big = f"{W1}x{H1}"
    res, checks = {"design": name, "format": dz["format"]}, {}
    # ---- libmpr: the encoder request's raster, and the MP4 track config / stsd / PROF of the four formats
    lmc = apply(lm, "libmpr", name)
    rows = sorted({int(re.search(r"row (\d+)", p["note"]).group(1)) for p in dz["patches"] if p["kind"] == "L1-comb"})
    others = [r for r in (4, 9, 12, 13) if r not in rows]
    comb = {r: {"stock": list(struct.unpack_from("<HH", lm, COMB + 0x18 * r + 4)), "changed": list(struct.unpack_from("<HH", lmc, COMB + 0x18 * r + 4))}
            for r in rows + others}
    checks["encoder request raster: rows %s 3840x2160 -> %s, rows %s unchanged" % (rows, big, others)] = (
        rows == [0, 2, 5, 7] and all(comb[r]["stock"] == [W0, H0] and comb[r]["changed"] == [W1, H1] for r in rows)
        and all(comb[r]["stock"] == comb[r]["changed"] for r in others))
    meta = any(p["kind"] == "L4-mp4size" for p in dz["patches"])
    want = [W1, H1] if meta else [W0, H0]
    libs = {"stock": emu_mp4_meta.Lib(lm, BUILD), "changed": emu_mp4_meta.Lib(lmc, BUILD)}
    mrows = []
    for cb in (0, 2, 5, 7):
        for rate_code in (0, 2):
            for rate_index in range(2, 0x36):
                row = {"comb": cb, "rate_code": rate_code, "rate_index": rate_index}
                for k, lib in libs.items():
                    r, cfg = lib.config(cb, rate_code, rate_index)
                    rs, sz = lib.stsd(cfg)
                    rp, pf = lib.prof(cfg)
                    row[k] = {"config": [struct.unpack_from("<H", cfg, 0x2A)[0], struct.unpack_from("<H", cfg, 0x28)[0]], "stsd": [rs, list(sz)], "prof": [rp, pf]}
                if row["stock"]["stsd"][0] == 0 and row["stock"]["prof"][0] == 0:
                    mrows.append(row)
    checks["MP4 track config, stsd and PROF of every request the stock writer accepts: %s with the stock profile id%s" % (
        "x".join(map(str, want)), "" if meta else " (no header sites: the headers keep 3840x2160)")] = bool(mrows) and all(
        r["stock"]["config"] == [W0, H0] and r["changed"]["config"] == want and r["changed"]["stsd"] == [0, want] and r["changed"]["prof"][0] == 0
        and r["changed"]["prof"][1]["profile_id"] == r["stock"]["prof"][1]["profile_id"] for r in mrows)
    res["libmpr"] = {"comb_rows": {str(k): v for k, v in comb.items()}, "mp4_requests_checked": len(mrows), "mp4_example": mrows[0] if mrows else None}
    # ---- av-cam: the matcher
    avc = apply(av, "avcam", name)
    s, c = E.AvCam(av, FN), E.AvCam(avc, FN)
    clip1 = lambda cam, w, h: cam.clip(w, h) & 0xFFFFFFFF
    sel, good = [], True
    for p in dz["descriptors"]:
        k = p["descriptor"]
        d = s.desc(k)
        row = {"descriptor": k, "format": p["format"], "rate": p["rate"], "quality_class": p["quality_class"], "key": d["key"],
               "stock_3840x2160": s.select(d, W0, H0), f"stock_{big}": s.select(d, W1, H1), f"changed_{big}": c.select(d, W1, H1), "changed_3840x2160": c.select(d, W0, H0)}
        row["as_designed"] = row["stock_3840x2160"] == k and row[f"stock_{big}"] is None and row[f"changed_{big}"] == k and row["changed_3840x2160"] is None
        good &= row["as_designed"]
        sel.append(row)
    checks["matcher: each of the %d changed descriptors is found for %s, no longer for 3840x2160" % (len(sel), big)] = good and len(sel) == N_DESC_CHANGED
    changed = {p["descriptor"] for p in dz["descriptors"]}
    untouched = []
    for k in range(NDESC):
        d = s.desc(k)
        if d["infr"] or k in changed or d["codec"] not in (4, 0xE, 0x18):
            continue
        if (d["w"], d["h"]) == (W0, H0) or d["w"] >= W1:
            untouched.append({"descriptor": k, "codec": hex(d["codec"]), "raster": [d["w"], d["h"]], "coding_rate_code": d["codfr"],
                              "stock": s.select(d, d["w"], d["h"]), "changed": c.select(d, d["w"], d["h"]), f"changed_{big}": c.select(d, W1, H1)})
    checks["matcher: every other 3840x2160 and wider AVC, HEVC, S-I request (the 50p / 60p / 120p settings among them): the same answer; none finds a descriptor at %s" % big] = (
        bool(untouched) and all(u["stock"] == u["changed"] for u in untouched) and all(u[f"changed_{big}"] is None for u in untouched))
    res["encoder_selection"] = {"changed": sel, "untouched_checked": len(untouched), "untouched_examples": untouched[:6]}
    # ---- clip-format code
    clips = [{"raster": [w, h], "stock": clip1(s, w, h), "changed": clip1(c, w, h)} for w, h in ((W1, H1), (W0, H0), (8192, 4320), (1920, 1080))]
    res["clip_code"] = clips
    checks["clip-format code: %s 0 -> 23 (the 4K code), 3840x2160 23 kept, 8192x4320 3 -> 0 (its row rewritten), 1920x1080 kept" % big] = (
        [x["stock"] for x in clips][:3] == [0, 23, 3] and [x["changed"] for x in clips][:3] == [23, 23, 0] and clips[3]["stock"] == clips[3]["changed"] != 0)
    # ---- memory: which ids the memory function asks for, and the codec's own calculation against row 3
    table = [struct.unpack_from("<4I", avc, UNIT + 0x10 * k) for k in range(5)]
    r3, r2 = table[3], table[2]
    firsts = {}
    for q in dz["descriptors"]:
        firsts.setdefault(s.desc(q["descriptor"])["codec"], q["descriptor"])
    mem_ids, ok_ids = {}, True
    for cd, k in sorted(firsts.items()):
        d = s.desc(k)
        mem_ids[hex(cd)] = {"descriptor": k, f"request_{big}": {"stock": s.unit_ids(d, W1, H1), "changed": c.unit_ids(d, W1, H1)},
                            "request_3840x2160": {"stock": s.unit_ids(d, W0, H0), "changed": c.unit_ids(d, W0, H0)}}
        ch = mem_ids[hex(cd)][f"request_{big}"]["changed"]
        ok_ids &= (ch["memory_ids_asked"][:4] == [hex(r3[0]), hex(r3[1]), hex(r3[3]), hex(r3[2])] and not ch["errors_logged"]
                   and mem_ids[hex(cd)]["request_3840x2160"]["changed"] == mem_ids[hex(cd)]["request_3840x2160"]["stock"])
    checks["memory function: a %s request asks row 3 (CD, LD, ES, multi = %s); 3840x2160 asks as stock" % (big, [hex(x) for x in (r3[0], r3[1], r3[3], r3[2])])] = ok_ids
    res["memory_ids_by_codec"] = mem_ids
    fw = V.Firmware()
    have, have2 = [size_of(i) for i in r3], [size_of(i) for i in r2]
    mem = []
    for dd in V.descriptors(avc):
        if dd["index"] not in changed:
            continue
        need = fw.need(dd)
        t, why = V.unit_type(dd)
        mem.append({"descriptor": dd["index"], "raster": [dd["w"], dd["h"]], "use_core": dd["use_core"], "unit_type": t, "pred_mode": dd["pred_mode"],
                    "need": {k: need[k] for k in ("cd", "ld", "multi")}, "firmware_asserts": need["asserts"],
                    "fits": need["cd"] <= have[0] and need["ld"] <= have[1] and need["multi"] <= have[2],
                    "would_fit_the_stock_order_of_row_2": need["cd"] <= have2[0] and need["ld"] <= have2[1] and need["multi"] <= have2[2]})
    checks["codec memory: every changed descriptor (two cores, unit type 3) fits the %s's blocks of row 3 %s, no firmware assert" % (CAMERA, have)] = bool(mem) and all(
        m["fits"] and m["unit_type"] == 3 and m["raster"] == [W1, H1] and m["use_core"] == 2 and not m["firmware_asserts"] for m in mem)
    res["codec_memory"] = {"row_3": {"ids": [hex(i) for i in r3], "bytes": have}, "row_2_stock_order": {"ids": [hex(i) for i in r2], "bytes": have2},
                           "largest_need": {k: max(m["need"][k] for m in mem) for k in ("cd", "ld", "multi")},
                           "in_the_stock_order_of_row_2_all_would_fit": all(m["would_fit_the_stock_order_of_row_2"] for m in mem), "rows": mem}
    # ---- B pictures are kept (the stock GOP): PredMode and MParam are the file's
    prof = {}
    for base, n in PROFILES:
        for k in range(n):
            prof[struct.unpack_from("<I", av, base + k * 0x100 + 0x20)[0]] = base + k * 0x100
    gop = []
    for p in dz["descriptors"]:
        d = s.desc(p["descriptor"])
        do, po = DESC + 0x90 * p["descriptor"], prof[d["key"]]
        mo = 0x97 if d["codec"] == 0xE else 0x9B
        gop.append({"descriptor": p["descriptor"], "pred_mode": [av[do + 0x85], avc[do + 0x85]], "m_param": [av[po + mo], avc[po + mo]]})
    checks["GOP unchanged: PredMode and MParam stay 3 in all %d descriptors and their profiles (B pictures kept)" % len(gop)] = bool(gop) and all(
        x["pred_mode"] == [3, 3] and x["m_param"] == [3, 3] for x in gop)
    # ---- the start-block builder
    starts, sgood = [], True
    for p in dz["descriptors"]:
        d = s.desc(p["descriptor"])
        o, ten = prof[d["key"]], d["bitl"] == 1
        a, seq_a = s.start_block(av[o:o + 0x100], d, W0, H0, ten)
        b, seq_b = c.start_block(avc[o:o + 0x100], d, W1, H1, ten)
        br = 32 if d["codec"] == 0xE else 16
        first = struct.unpack_from("<H", seq_b, 0xC)[0]
        sgood &= (a["returned"] == 1 and not a["errors_logged"] and b["returned"] == 1 and not b["errors_logged"] and b["crop_size"] == [W1, H1]
                  and first == (-(-H1 // br) // 2) * br == H1 // 2)
        starts.append({"descriptor": p["descriptor"], "key": d["key"], "stock_3840x2160": a, f"changed_{big}": b, "rows_for_first_core_in_the_block": first,
                       "sequence_block_differs_at": runs_of(seq_a, seq_b)})
    checks["start-block builder: every changed profile accepted at %s (crop, rows for the first core = %d, exactly half the picture)" % (big, H1 // 2)] = sgood
    res["start_block"] = starts
    # ---- the bit rate fields
    rate = []
    for p in dz["descriptors"]:
        d = s.desc(p["descriptor"])
        po, ro = prof[d["key"]], 0xAC if d["codec"] == 0xE else 0xB0
        fig = lambda img: [v << (6 + sh) for sh, v in zip(*[iter(struct.unpack_from("<4I", img, po + ro))] * 2)]
        rate.append({"descriptor": p["descriptor"], "key": d["key"], "stock_bit_rate_and_highest": fig(av), "design": fig(avc)})
    if "r300" in name:
        checks["bit rate: the 100M settings (97 million and above) hold 300 / 340 million; the lower settings keep theirs"] = all(
            (r["design"] == [300_000_000, 339_999_744] or r["design"][0] > 299_000_000) if r["stock_bit_rate_and_highest"][0] >= 96_000_000 else r["design"] == r["stock_bit_rate_and_highest"]
            for r in rate) and any(r["stock_bit_rate_and_highest"][0] >= 96_000_000 for r in rate)
    else:
        checks["bit rate: every profile keeps the menu setting's figures"] = all(r["design"] == r["stock_bit_rate_and_highest"] for r in rate)
    res["bit_rate"] = rate
    res["checks"] = checks
    return res


def main():
    av = locate_file.locate(BUILD, "av-cam.bin").read_bytes()
    lm = locate_file.locate(BUILD, "libmpr.so").read_bytes()
    a7 = locate_file.locate("a7iv_602", "av-cam.bin").read_bytes()
    FN, fps = find_functions(a7, av)
    V.DESC, V.NDESC, V.UNIT_TABLE, V.FPS_TABLE = AVB + DESC, NDESC, AVB + UNIT, AVB + fps
    cfg = parse_dmmcfg.Config(parse_dmmcfg.find_file(BUILD, "setting"), BUILD)

    def size_of(i):
        units = [u for kk in cfg.id_json(i).get("keys", []) for u in kk["units"]] if i else []
        return max(u["size_bytes"] for u in units) if units else None

    out = {"about": CAMERA + ": function-level emulation of the 4224x2816 encoder-side designs, stock against changed, in that camera's own av-cam.bin and "
                    "libmpr.so (build/run_og4224_emu_s3.py). The requests are built from the descriptors' own fields, not from a traced caller. Nothing "
                    "was run on a camera.",
           "functions": {k: hex(v - AVB) for k, v in FN.items()}, "frame_rate_table": hex(fps), "designs": []}
    bad = []
    for name in NAMES:
        r = check(name, av, lm, size_of, FN)
        out["designs"].append(r)
        print("==", name)
        for k, v in r["checks"].items():
            print("   %s  %s" % ("PASS" if v else "FAIL", k))
            if not v:
                bad.append(f"{name}: {k}")
        print("   codec memory: largest need", r["codec_memory"]["largest_need"], "| row 3", r["codec_memory"]["row_3"], "| stock order would fit:",
              r["codec_memory"]["in_the_stock_order_of_row_2_all_would_fit"])
    DEST.parent.mkdir(parents=True, exist_ok=True)
    DEST.write_text(json.dumps(out, indent=1) + "\n", encoding="utf8", newline="\n")
    print("wrote", DEST)
    print("ALL CHECKS PASS (%d)" % sum(len(r["checks"]) for r in out["designs"]) if not bad else "FAILED: " + "; ".join(bad))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
