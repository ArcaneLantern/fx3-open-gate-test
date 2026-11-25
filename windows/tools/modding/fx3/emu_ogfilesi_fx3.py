"""Emulated check of the FX3's XAVC S-I 4K open-gate step `ogfilesi2560_fx3_v1` (build/build_ogfile_si.py --build fx3_702), on the FX3 7.02's
own code, in the state it is applied on (the kit's L19, ogfile2560_hs_s_fx3_v2, applied first in emulated memory). 2026-11-25.

The FX3 counterpart of build/run_ogfile_si_emu.py (the A7 IV's ogfilesi2560_v1). The FX3's av-cam functions are found first, by code:
  matcher        0x225eb8  = A7 IV 0x21b780, the whole body equal (build/avcam_fnport.py: branch targets and page offsets aside)
  memory ids     0x21dd54  = A7 IV 0x2136c4, equal
  allocator      0x22d394  = A7 IV 0x222bd0, equal;   log 0x27d568 = A7 IV 0x27278c, equal
  clip format    0x196b80  = A7 IV 0x190128 but for one log line number
  start block    0x221b50  (the A7 IV's 0x2174c0 compiled differently: other stack layout, one block fewer); it is reached from the
                 FX3's command fill at 0x21f87c with the A7 IV's six instructions before the call. It is run as the FX3's own.
  memcpy / memset wrappers 0x27da84 / 0x27da9c (call 0xd80 / 0x2f67c as the A7 IV's 0x272ca8 / 0x272cc0)
Then, stock against the state (L19) against the state plus the S-I step:
  libmpr      the encoder request's raster of comb row 9 (g_videoParamComb, what SetEncOpenParam copies: F132; the FX3's L19 rows work this way
              on the camera); the MP4 writer's sizes for comb 9 (build/emu_mp4_meta.py's Lib with the FX3's own writer)
  av-cam      the matcher for each changed descriptor and for every other AVC/HEVC/S-I request; the memory ids the memory function asks for
              an S-I request of the new size; the codec firmware's memory need (the same vcd_firmware_imola2.bin on the A7 IV and the FX3)
              against the FX3's DmmCfg sizes; the start-block builder with each changed profile; the clip-format code of 3840x2560
  DmmCfg      the ids the S-I request asks for have the A7 IV's units on the FX3
  overlap     no site of the step is a site or guard of the kit's other main-processor designs

Nothing here is hardware. Run:  C:\\Python313\\python.exe -B build/emu_ogfilesi_fx3.py      writes evidence/fx3/ogfilesi_fx3_emu.json
"""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import avcam_fnport  # noqa: E402
import emu_mp4_meta  # noqa: E402
import emu_vcd_chmem  # noqa: E402
import locate_file  # noqa: E402
import parse_dmmcfg  # noqa: E402
from run_ogfile_emu import AVB, AvCam, D, pokes  # noqa: E402

BUILD, SI, STEP4, STEP4_V1 = "fx3_702", "ogfilesi2560_fx3_v1", "ogfile2560_hs_s_fx3_v2", "ogfile2560_hs_s_fx3_v1"
W0, H0, W1, H1 = 3840, 2160, 3840, 2560
COMB, DESC, NDESC, UNIT = 0x2CB108, 0x395108, 689, 0x395068
PROFILES = ((0x3AD498, 373), (0x3C4A98, 316))
CLIP_4K = 23                                      # the FX3's clip-format code of 3840x2160 (build_ogfile.OTHER_BUILDS["fx3_702"])
FN = {"DESC": AVB + DESC, "MATCH": AVB + 0x225EB8, "CLIPFN": AVB + 0x196B80, "UNITFN": AVB + 0x21DD54, "BUILDER": AVB + 0x221B50,
      "DMM_OPEN": AVB + 0x22D394, "LOGF": AVB + 0x27D568, "LOGH": AVB + 0x27D528, "MEMSET": AVB + 0x27DA9C, "MEMCPY": AVB + 0x27DA84}


def apply(img, *names, kind="avcam"):
    b = bytearray(img)
    for n in names:
        for off, nb in pokes(D / f"{n}_pokes_{kind}.txt"):
            b[off:off + len(nb)] = nb
    return bytes(b)


def find_functions(a7, fx):
    """Assert where the FX3's functions are (see the docstring). Returns a dict for the report."""
    exact = avcam_fnport.port(BUILD, [0x21B780, 0x2136C4, 0x222BD0, 0x27278C], a7, fx)
    want = {0x21B780: 0x225EB8, 0x2136C4: 0x21DD54, 0x222BD0: 0x22D394, 0x27278C: 0x27D568}
    assert {k: v[0] for k, v in exact.items()} == want, exact
    # the clip-format function: equal but for one `mov w7, #line`
    n = avcam_fnport.a7iv_size(0x190128) // 4
    a = avcam_fnport.normalise(struct.unpack_from("<%dI" % n, a7, 0x190128))
    b = avcam_fnport.normalise(struct.unpack_from("<%dI" % n, fx, 0x196B80))
    diff = [k for k in range(n) if a[k] != b[k]]
    assert len(diff) == 1 and a[diff[0]] & 0xFFE0001F == b[diff[0]] & 0xFFE0001F == 0x52800007, diff
    # the start-block builder: the call in the command fill, after the A7 IV's six instructions
    seq = struct.unpack_from("<6I", a7, 0x2151D4)
    sites = [x for x in range(0x210000, 0x230000, 4) if struct.unpack_from("<6I", fx, x) == seq]
    assert sites == [0x21F864], sites
    w = struct.unpack_from("<I", fx, 0x21F87C)[0]
    assert w & 0xFC000000 == 0x94000000 and 0x21F87C + 4 * ((w & 0x3FFFFFF) - ((w & 0x2000000) << 1)) == 0x221B50
    # memcpy / memset wrappers: the same shape, calling the same two routines as the A7 IV's
    for a7_at, fx_at in ((0x272CA8, 0x27DA84), (0x272CC0, 0x27DA9C)):
        wa, wf = struct.unpack_from("<6I", a7, a7_at), struct.unpack_from("<6I", fx, fx_at)
        tgt = lambda at, ws: at + 8 + 4 * ((ws[2] & 0x3FFFFFF) - ((ws[2] & 0x2000000) << 1))
        assert wa[:2] == wf[:2] and wa[3:] == wf[3:] and tgt(a7_at, wa) == tgt(fx_at, wf), (hex(a7_at), hex(fx_at))
    return {"matcher": "0x225eb8 (= A7 IV 0x21b780)", "memory_ids": "0x21dd54 (= A7 IV 0x2136c4)", "allocator": "0x22d394 (= A7 IV 0x222bd0)",
            "clip_format": "0x196b80 (A7 IV 0x190128 but one log line number)", "start_block": "0x221b50 (called at 0x21f87c; the FX3's own compile)",
            "memcpy_memset": "0x27da84 / 0x27da9c"}


def descriptor(av, k):
    o = DESC + k * 0x90
    b = av[o:o + 0x90]
    codec, infr, codfr, f0c, f10, chroma, bitl = struct.unpack_from("<7I", b, 0)
    w, h = struct.unpack_from("<HH", b, 0x7E)
    return {"index": k, "codec": codec, "w": w, "h": h, "key": struct.unpack_from("<I", b, 0x28)[0], "use_core": b[0x78], "enc_cd_mode": b[0x7A],
            "bit_depth": b[0x82], "chroma": b[0x83], "codec_type": b[0x84], "pred_mode": b[0x85], "ebc_ld": b[0x86], "ebc_cd": b[0x87],
            "scan_mode": b[0x89], "roi": b[0x8A]}


def main():
    a7 = locate_file.locate("a7iv_602", "av-cam.bin").read_bytes()
    av = locate_file.locate(BUILD, "av-cam.bin").read_bytes()
    lm = locate_file.locate(BUILD, "libmpr.so").read_bytes()
    design = json.loads((D / f"{SI}.json").read_text(encoding="utf8"))
    s4 = json.loads((D / f"{STEP4}.json").read_text(encoding="utf8"))
    assert design["build"] == BUILD and design["artifact_sha256"]["av-cam.bin"] == s4["artifact_sha256"]["av-cam.bin"]
    res, checks = {"design": SI, "on_top_of": STEP4, "functions": find_functions(a7, av)}, {}

    # ---- libmpr: the encoder request (comb rows) and the MP4 writer for comb 9
    lms = {"stock": lm, "state": apply(lm, STEP4, kind="libmpr"), "state + S-I step": apply(lm, STEP4, SI, kind="libmpr"),
           "first kit's state (v1) + S-I step": apply(lm, STEP4_V1, SI, kind="libmpr")}
    raster = lambda img, r: list(struct.unpack_from("<HH", img, COMB + 0x18 * r + 4))
    res["encoder_request"] = {k: {str(r): raster(v, r) for r in (0, 2, 5, 7, 9, 12)} for k, v in lms.items()}
    e = res["encoder_request"]
    checks["encoder request: comb 9 (XAVC S-I 4K) 3840x2160 -> 3840x2560 with the step; comb 0/2/5/7 as the state makes them; S-I DCI (12) untouched"] = (
        e["stock"]["9"] == [W0, H0] and e["state"]["9"] == [W0, H0] and e["state + S-I step"]["9"] == [W1, H1]
        and all(e["state + S-I step"][r] == e["state"][r] for r in ("0", "2", "5", "7", "12")) and e["state"]["12"] == [4096, 2160])
    libs = {k: emu_mp4_meta.Lib(v, BUILD) for k, v in lms.items()}
    mp4 = []
    for rate_code in (0, 2):
        for rate_index in range(2, 0x36):
            row = {"rate_code": rate_code, "rate_index": rate_index}
            for k, lib in libs.items():
                r, cfg = lib.config(9, rate_code, rate_index)
                rs, sz = lib.stsd(cfg)
                rp, pf = lib.prof(cfg)
                row[k] = {"config": [struct.unpack_from("<H", cfg, 0x2A)[0], struct.unpack_from("<H", cfg, 0x28)[0]], "stsd": [rs, list(sz)], "prof": [rp, pf]}
            if row["stock"]["stsd"][0] == 0 and row["stock"]["prof"][0] == 0:
                mp4.append(row)
    ok_mp4 = bool(mp4) and all(r["stock"]["config"] == [W0, H0] and r["state"] == r["state + S-I step"] and r["state"]["config"] == [W1, H1]
                               and r["state"]["stsd"] == [0, [W1, H1]] and r["state"]["prof"][0] == 0
                               and r["state"]["prof"][1]["profile_id"] == r["stock"]["prof"][1]["profile_id"]
                               and r["first kit's state (v1) + S-I step"]["config"] == [W0, H0] for r in mp4)
    res["mp4_headers_comb_9"] = {"requests_the_stock_code_accepts": len(mp4), "example": mp4[0] if mp4 else None}
    checks["MP4 headers of an S-I file: the kit's L19 (v2) makes them say 3840x2560, stock profile id; with the first kit's v1 (--no-meta) 3840x2160"] = ok_mp4

    # ---- av-cam: the matcher
    stock, state, both = av, apply(av, STEP4), apply(av, STEP4, SI)
    s, t, c = AvCam(stock, FN), AvCam(state, FN), AvCam(both, FN)
    sel, good = [], True
    for p in design["descriptors"]:
        k = p["descriptor"]
        d = s.desc(k)
        row = {"descriptor": k, "rate": p["rate"], "class": p["quality_class"], "key": d["key"], "twin": p["twin_never_reached"],
               "stock_3840x2160": s.select(d, W0, H0), "state_3840x2560": t.select(d, W1, H1), "state_and_step_3840x2560": c.select(d, W1, H1),
               "state_and_step_3840x2160": c.select(d, W0, H0)}
        row["as_designed"] = (row["stock_3840x2160"] == k and row["state_3840x2560"] is None and row["state_and_step_3840x2560"] == k
                              and row["state_and_step_3840x2160"] == p["twin_never_reached"])
        good &= row["as_designed"]
        sel.append(row)
    checks["the FX3's matcher finds each changed S-I descriptor for 3840x2560 (its 205xxx twin keeps 2160, never asked)"] = good
    changed = {p["descriptor"] for p in design["descriptors"]}
    twins = {p["twin_never_reached"] for p in design["descriptors"]}
    W4, H4 = s4["raster"]
    same, n, moved = True, 0, []
    for k in range(NDESC):
        d = s.desc(k)
        if k in changed or d["codec"] not in (4, 0xE, 0x18) or d["w"] < 1920:
            continue
        for w, h in ((d["w"], d["h"]), (W4, H4)):
            a, b = t.select(d, w, h), c.select(d, w, h)
            n += 1
            if a != b:
                moved.append({"built_from": k, "raster": [w, h], "state": a, "state_and_step": b})
                same &= (k in twins and (w, h) == (W0, H0) and a in changed and b == k) or ((w, h) == (W4, H4) and d["codec"] == 0x18 and a is None and b in changed)
    checks["every other AVC/HEVC/S-I request gives the same answer with and without the step (but a changed row's own match fields)"] = same
    checks["the L19 design's own descriptors are still found at 3840x2560"] = all(c.select(s.desc(q["descriptor"]), W4, H4) == q["descriptor"] for q in s4["descriptors"])
    res["encoder_selection"] = {"changed": sel, "requests_compared": n, "answers_that_moved": moved}

    # ---- memory: the ids asked, the codec's need, the FX3's DmmCfg
    table = [struct.unpack_from("<4I", both, UNIT + 0x10 * k) for k in range(10)]
    d0 = s.desc(design["descriptors"][0]["descriptor"])
    ids0, ids1 = s.unit_ids(d0, W0, H0), c.unit_ids(d0, W1, H1)
    res["memory_ids"] = {"stock_3840x2160": ids0, "state_and_step_3840x2560": ids1}
    r4, r9 = table[4], table[9]
    checks["the FX3's memory function asks unit type 4's row (0x486, 0x474, 0x47a, 0x477) where stock asks type 9's, the rest the same"] = (
        r4 == (0x486, 0x474, 0x477, 0x47A) and r9 == (0x664, 0x474, 0x477, 0x690)
        and ids0["memory_ids_asked"][:4] == [hex(r9[0]), hex(r9[1]), hex(r9[3]), hex(r9[2])]
        and ids1["memory_ids_asked"][:4] == [hex(r4[0]), hex(r4[1]), hex(r4[3]), hex(r4[2])]
        and ids1["memory_ids_asked"][4:] == ids0["memory_ids_asked"][4:] and not ids1["errors_logged"] and ids1["returned"] == ids0["returned"])
    cfgs = {b: parse_dmmcfg.Config(parse_dmmcfg.find_file(b, "setting"), b) for b in (BUILD, "a7iv_602")}

    def units(b, i):
        return sorted((u["group"]["parent"], u["size"]) for k in cfgs[b].id_rows.get(i, {}).get("keys", []) for u in cfgs[b].units_by_key.get(k, []))
    ids = sorted({int(x, 16) for x in ids0["memory_ids_asked"] + ids1["memory_ids_asked"]})
    # for the record: each id's units on both bodies (same sizes; the ES parent block is key 0x76a on the FX3, 0x7d6 on the A7 IV, both 138.7 MB,
    # holding 0x47a or 0x690/0x691; the FX3's 304.7 MB region 0x668 has one more alternative group, {0x479}, its stock long-GOP ES block)
    res["dmm"] = {hex(i): {"fx3": units(BUILD, i), "a7iv": units("a7iv_602", i)} for i in ids}
    # what decides: the S-I request at 3840x2560 asks the very blocks a stock XAVC S 4K 24p recording asks on the FX3 (its 4K unit row), and the
    # same further id as stock S-I. Those blocks are open together in every 4K recording, open gate included (the kit's L19 gives row 3 these ids)
    s_4k = next(q["descriptor"] for q in s4["descriptors"] if s.desc(q["descriptor"])["codec"] == 4 and q["rate"] == "23.98p")    # XAVC S 4K (AVC)
    ids_s = s.unit_ids(s.desc(s_4k), W0, H0)
    res["memory_ids"]["stock_xavc_s_4k_24p_3840x2160"] = ids_s
    checks["on the FX3, the S-I request at 3840x2560 asks the blocks a stock XAVC S 4K 24p recording asks (and stock S-I's further id)"] = (
        ids1["memory_ids_asked"][:4] == ids_s["memory_ids_asked"][:4] and ids1["memory_ids_asked"][4:] == ids0["memory_ids_asked"][4:]
        and all(units(BUILD, i) for i in ids))
    fw = emu_vcd_chmem.Firmware()
    size = {i: max(sz for _, sz in units(BUILD, i)) for i in r4}
    mem, fit = [], True
    for k in sorted(changed):
        dd = descriptor(both, k)
        need = fw.need(dd)
        f = (dd["w"], dd["h"]) == (W1, H1) and dd["use_core"] == 2 and need["cd"] <= size[r4[0]] and need["ld"] <= size[r4[1]] and need["multi"] <= size[r4[2]] and not need["asserts"]
        fit &= f
        mem.append({"descriptor": k, "raster": [dd["w"], dd["h"]], "need": {x: need[x] for x in ("cd", "ld", "multi")},
                    "have": {"cd": size[r4[0]], "ld": size[r4[1]], "multi": size[r4[2]]}, "fits": f})
    checks["the codec firmware's memory need for each changed descriptor fits unit type 4's blocks on the FX3, no firmware assert"] = fit
    res["codec_memory"] = mem

    # ---- the start-block builder and the clip-format code
    prof = {}
    for base, cnt in PROFILES:
        for k in range(cnt):
            prof[struct.unpack_from("<I", av, base + k * 0x100 + 0x20)[0]] = base + k * 0x100
    starts, sgood = [], True
    for p in design["descriptors"]:
        d = s.desc(p["descriptor"])
        o = prof[d["key"]]
        a, seq_a = s.start_block(stock[o:o + 0x100], d, W0, H0, True)
        b, seq_b = c.start_block(both[o:o + 0x100], d, W1, H1, True)
        first0, first1 = struct.unpack_from("<H", seq_a, 0xC)[0], struct.unpack_from("<H", seq_b, 0xC)[0]
        ok = (a["returned"] == 1 and not a["errors_logged"] and a["crop_size"] == [W0, H0] and first0 == 1072
              and b["returned"] == 1 and not b["errors_logged"] and b["crop_size"] == [W1, H1] and first1 == 1280)
        sgood &= ok
        starts.append({"descriptor": p["descriptor"], "stock_3840x2160": a, "changed_3840x2560": b, "rows_for_first_core": [first0, first1], "ok": ok})
    checks["the FX3's start-block builder takes each profile: stock at 3840x2160 (1072 rows first core), changed at 3840x2560 (1280)"] = sgood
    res["start_block"] = starts
    res["clip_code"] = {"stock_3840x2160": s.clip(W0, H0), "stock_3840x2560": s.clip(W1, H1), "state_and_step_3840x2560": c.clip(W1, H1)}
    checks["clip-format code of 3840x2560 is the FX3's 4K code 23 (from L19)"] = res["clip_code"]["state_and_step_3840x2560"] == CLIP_4K == res["clip_code"]["stock_3840x2160"]

    # ---- no overlap with the kit's other main-processor designs
    mine = [(p["binary"], int(p["file_off"], 16), len(p["new"]) // 2) for p in design["patches"]]
    theirs = []
    for nm in (STEP4, STEP4_V1, "avdec8k_fx3_v1"):
        dj = json.loads((D / f"{nm}.json").read_text(encoding="utf8"))
        for p in dj.get("patches", []):
            theirs.append((p["binary"], int(p["file_off"], 16), len(p["new"]) // 2))
        for key in ("code_sites", "data_sites"):
            for p in dj.get(key, []):
                theirs.append(("av-cam.bin", int(p["file_off"], 16), len(p["new"]) // 2))
    checks["no site of the step is a site of L19 (v1, v2) or of the playback step"] = not any(
        a == b and x < y + m and y < x + n for a, x, n in mine for b, y, m in theirs)

    res["checks"] = checks
    out = ROOT / "evidence/fx3/ogfilesi_fx3_emu.json"
    out.write_text(json.dumps(res, indent=1) + "\n", encoding="utf8", newline="\n")
    bad = 0
    for text, ok in checks.items():
        print("   %s  %s" % ("PASS" if ok else "FAIL", text))
        bad += not ok
    print("   memory ids asked: stock %s / 3840x2560 %s" % (ids0["memory_ids_asked"], ids1["memory_ids_asked"]))
    print("   codec need e.g. #%d: %s of %s" % (mem[0]["descriptor"], mem[0]["need"], mem[0]["have"]))
    print("   start block e.g. #%d: %s" % (starts[0]["descriptor"], starts[0]["changed_3840x2560"]))
    print("   clip codes:", res["clip_code"], "| MP4 requests checked:", len(mp4))
    if bad:
        raise SystemExit("%d check(s) failed" % bad)
    print("all checks passed; wrote", out)


if __name__ == "__main__":
    main()
