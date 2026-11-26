"""Build the encoder and container side of an open-gate file in XAVC S-I 4K (A7 IV 6.02): designs `ogfilesi2560_v1` (3840x2560) and
`ogfilesi57_v1` (5760x3840). Design only: nothing is written to a firmware file and nothing is sent to a camera.

2026-11-25, at the owner's request ("for our A7iv open gate patches (both 4K and 5.7K) can we make a new test script that applies the same open
gate to XAVC S-I 4K mode?"). Each design is ONE MORE STEP on top of an open-gate state that already records XAVC HS 4K and XAVC S 4K:

  ogfilesi2560_v1  after ogfile2560_hs_s_v2 in the 3840x2560 state (open_gate_apply.cmd: dmmwb4688_v1, ogsq_v3, outsz2560_v1, ...)
  ogfilesi57_v1    after ogfile57r300m1_v4 in the real 5760x3840 state (open_gate_apply_57.cmd: dmmwb4688_v1, og57n_v1, og57cp_v3, ...)

The coprocessor steps of those states are not changed: they make the full-height picture, the output size and its buffers, whatever the
recording format. What the main processor holds for XAVC S-I 4K is what this adds.

XAVC S-I 4K in the tables (read here; the asserts below check every statement against the files):
  libmpr.so   g_videoParamComb row 9 (0x2d3390): codec 0 (AVC), 3840x2160, 4:2:2 10-bit, intra flag 1; m_vpcSt row 9 (0x2e917c) intra flag 1.
              Row 12 is XAVC S-I DCI 4096x2160 and is not touched.
  av-cam.bin  codec id 0x18 (AVC intra, CodecType 1, PredMode 0, EncCdMode 0 = not a landing channel). Every S-I descriptor is there twice: keys
              105xxx with UseCore 2 (both encoder cores) and keys 205xxx with UseCore 0, the two identical in every field the matcher
              0xffffffc00121b780 compares (codec, rate codes, quality class, chroma, depth, raster, input rate, the mode list). The matcher returns
              the FIRST match, so a recording reaches the 105xxx row and never its 205xxx twin. Only 105xxx rows are changed.
              At 23.98p (rate code 5) and 25p (rate code 3), normal speed, there are two quality classes each: 19 / 18 hold 10,080,256 at profile
              +0x5c (x 23.976 = 241.7 Mbps, x 25 = 252 Mbps: the menu's 240M / 250M; read as the bits of one picture) and 14 / 13 hold 16,076,800
              (385 / 402 Mbps; no setting of this camera's menu that we know of). Both classes are changed, so either request finds the new raster.
  memory      av-cam's memory function 0xffffffc0012136c4 (build/emu_vcd_chmem.py unit_type): an intra picture up to 8,847,360 pixels and
              530,841,600 pixels a second takes unit type 9 (block 0x664 50.4 MB as CD); above that, type 4, whose row is the 4K class's in
              stock ({CD 0x486 100.8 MB, LD 0x474, multi 0x477, ES 0x47a}). Row 3, which the long-GOP designs rewrite, is not used by intra.
              The codec firmware's own calculation (build/run_ogfile_si_emu.py) asks CD 44,269,568 at 3840x2560 and 99,549,184 at 5760x3840 of
              the 100,794,368 of 0x486; LD 0. So no memory-class site is needed (OG4K_FILE_SIDE.md said so for 2,560 rows).
              5760x3840 at 50p/60p is refused by that function (above 995,328,000 pixels a second); 23.98p/25p/29.97p pass.

Sites:
  ogfilesi2560_v1   (the shape of ogfile2560_s_v1, which records XAVC S 4K at 3840x2560: F700)
    L1  libmpr comb row 9: height 2160 -> 2560 (the encoder request)
    A1  the four descriptors (24p classes 19 and 14, 25p classes 18 and 13): height +0x80 -> 2560
    A2  their profiles: +0x06 and +0x38 height -> 2560; rows for the first core +0x56: 1072 -> 1280 (half the picture in whole 16-row
        macroblock rows, as Sony's own two-core S-I profiles split 2160 and 1080)
  ogfilesi57_v1     (the shape of ogfile57_v1, which records XAVC S 4K at 5760x3840: F906; no core change: S-I already uses both)
    L1  libmpr comb row 9: 3840x2160 -> 5760x3840
    A1  the four descriptors: raster +0x7e -> 5760x3840
    A2  their profiles: raster +0x04, +0x34, +0x8e -> 5760x3840; +0x4c: 5760 -> 8640 (1.5 x the width, as every S-I profile) and +0x56:
        1072 -> 1920 (the eight bytes between written as they are); level +0xa7: 51 -> 60 (Level 6, the lowest whose picture size limit holds
        5760x3840; Sony's 7680-wide AVC profiles carry it)

Left alone on purpose:
  - the picture bit budget (profile +0x5c): the menu's 240M (24p) / 250M (25p) gives the same bits to a bigger picture: 0.84 x the bits per
    pixel of stock S-I 4K at 3840x2560, 0.375 x at 5760x3840. A higher budget is a later, separate test.
  - the unit-type table (not needed, above), the clip-format row (the state's step 4 already writes row 1 with the state's size and code 16),
    the MP4 headers (the state's step 4: the AVC size immediates 0x222b90/0x222b94 are shared by combs 0, 2 and 9, so with ogfile2560_hs_s_v2
    or ogfile57r300m1_v4 applied an S-I file's headers say the state's size; checked in build/run_ogfile_si_emu.py).
  - the 205xxx twins (never reached), the other frame rates (their request now says the new size and finds no descriptor: refused at encoder
    open, as in the HS/S designs), S-I HD and S-I DCI 4K.

Run:  work\\venv\\Scripts\\python.exe -I -B build\\build_ogfile_si.py [--list] [--register [--only <design>]]
Writes modding/designs/<design>.json and poke lists (file offset, hex) for the emulators.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import locate_file  # noqa: E402
import build_ogfile as B  # noqa: E402  (the table addresses: B.use_build(<build>) points them at another body)
from build_ogfile import AVB, RATES, Design  # noqa: E402

BUILD = "a7iv_602"
W0, H0 = 3840, 2160
SI_CODEC, SI_COMB = 0x18, 9                      # AVC intra; g_videoParamComb row of XAVC S-I 4K
# mpr::pconv::m_vpcSt (7 words a row), per build. FX3 7.02 (2026-11-25): found by content (the A7 IV's rows 0-11 at 0x2e0b80, once).
VPCS = {"a7iv_602": 0x2E9080, "fx3_702": 0x2E0B80}
BLOCK_ROWS, LEVEL_OFF, RASTER3, BUDGET = 16, 0xA7, 0x8E, 0x5C
LEVEL6 = 60
SIZES = {
    "ogfilesi2560_v1": {"raster": (3840, 2560), "shape": "ogfile2560_s_v1",
                        "goes_with": "the 3840x2560 open-gate state (dmmwb4688_v1 + ogsq_v3 or ogsq880_v1, outsz2560_v1 in coprocessor RAM; ogfile2560_hs_s_v2 "
                                     "on the main processor), applied as one more level 19 step after ogfile2560_hs_s_v2",
                        "after": "ogfile2560_hs_s_v2"},
    "ogfilesi57_v1": {"raster": (5760, 3840), "shape": "ogfile57_v1",
                      "goes_with": "the real 5760x3840 open-gate state (dmmwb4688_v1 + og57n_v1 or og57n880_v1, og57cp_v3 in coprocessor RAM; "
                                   "ogfile57r300m1_v4 on the main processor), applied as one more level 19 step after ogfile57r300m1_v4",
                      "after": "ogfile57r300m1_v4"},
}
# FX3 7.02 (2026-11-25, owner: "port that for the FX3 and build it into the repo"): the 3840x2560 design only (the FX3 kit has no 5.7K state).
# Its av-cam tables are the A7S III's moved as one (build_ogfile.OTHER_BUILDS["fx3_702"]); every assert below runs on the FX3's own files.
SIZES_BY_BUILD = {
    "a7iv_602": SIZES,
    "fx3_702": {"ogfilesi2560_fx3_v1": {"raster": (3840, 2560), "shape": "ogfile2560_hs_s_fx3_v1",
                                        "goes_with": "the FX3 kit's 3840x2560 open-gate state (ogsq_fx3_v1, outsz2560_fx3_v1 in coprocessor RAM; "
                                                     "ogfile2560_hs_s_fx3_v2 or _v1 on the main processor), applied as one more level 19 step (I19) of "
                                                     "fx3_apply.py apply",
                                        "after": "ogfile2560_hs_s_fx3_v2"}},
}
# A1 II 4.00 (2026-11-26, modding/A1M2_PORT_ENCODER.md): the 3840x2560 design only. Tables as build_ogfile.OTHER_BUILDS["a1m2_400"]; m_vpcSt found by
# content (the A7 IV's 14 rows at 0x2e8a50, once). The A1 II's matcher 0x234acc scans from index 0 (the A7 IV's from 3 when request +0x74 is 0);
# the S-I descriptors sit at 110+, so first_match() answers the same.
VPCS["a1m2_400"] = 0x2E8A50
SIZES_BY_BUILD["a1m2_400"] = {"ogfilesi2560_a1m2_v1": {"raster": (3840, 2560), "shape": "ogfile2560_hs_s_a1m2_v1",
                                                       "goes_with": "the A1 II kit's 3840x2560 open-gate state (its sensor, output size and raw-buffer steps "
                                                                    "in coprocessor RAM; ogfile2560_hs_s_a1m2_v2 or _v1 on the main processor), applied as "
                                                                    "one more level 19 step after it",
                                                       "after": "ogfile2560_hs_s_a1m2_v2"}}
WHY = ("the owner asked for a test script that applies the same open gate (3840x2560 and 5760x3840) to XAVC S-I 4K (2026-11-25); this is its "
       "encoder side")


def rows_first(h):
    """Rows for the first encoder core: half the picture in whole 16-row macroblock rows, rounded down (Sony's S-I profiles: 2160 -> 1072, 1080 -> 544)."""
    return (-(-h // BLOCK_ROWS) // 2) * BLOCK_ROWS


def descriptor_table(av):
    out = []
    for k in range(B.NDESC):
        o = B.DESC + k * 0x90
        f = struct.unpack_from("<7I", av, o)
        out.append({"k": k, "o": o, "codec": f[0], "infr": f[1], "codfr": f[2], "f0c": f[3], "cls": f[4], "chroma": f[5], "bitl": f[6],
                    "key": struct.unpack_from("<I", av, o + 0x28)[0], "wh": struct.unpack_from("<HH", av, o + 0x7E), "core": av[o + 0x78],
                    "w38": struct.unpack_from("<II", av, o + 0x38), "modes": struct.unpack_from("<7I", av, o + 0x40), "enc_cd_mode": av[o + 0x7A],
                    "codec_type": av[o + 0x84], "pred_mode": av[o + 0x85], "chroma_code": av[o + 0x83], "depth_code": av[o + 0x82]})
    return out


MATCH_FIELDS = ("codec", "infr", "codfr", "f0c", "cls", "chroma", "bitl", "wh", "modes")


def first_match(rows, r):
    """The index the matcher returns for a request built from row r's own fields (it scans from index 3 and returns the first that matches)."""
    return next(x["k"] for x in rows if x["k"] >= 3 and all(x[f] == r[f] for f in MATCH_FIELDS))


def check_rule(rows, prof_off, av):
    """What the design relies on, read from Sony's tables: every S-I profile has +0x4c = 1.5 x the width and +0x56 = rows_first(height), and the
    105xxx/205xxx twins differ only in key, +0x38/+0x3c and UseCore."""
    si = [r for r in rows if r["codec"] == SI_CODEC and r["key"] in prof_off]
    rule = []
    for r in si:
        po = prof_off[r["key"]]
        w, h = struct.unpack_from("<HH", av, po + 4)
        assert (w, h) == r["wh"], r["k"]
        assert struct.unpack_from("<H", av, po + 0x4C)[0] == w * 3 // 2 and struct.unpack_from("<H", av, po + 0x56)[0] == rows_first(h), (r["k"], w, h)
        rule.append((w, h))
    twins = []
    for r in si:
        if r["key"] // 100000 != 1:
            continue
        t = [x for x in si if x["key"] == r["key"] + 100000]
        if t:
            a, b = av[r["o"]:r["o"] + 0x90], av[t[0]["o"]:t[0]["o"] + 0x90]
            # fields the matcher does not read: the key, +0x34 (1 in the 50p/60p UseCore-2 rows), +0x38/+0x3c and UseCore +0x78
            assert {i for i in range(0x90) if a[i] != b[i]} <= set(range(0x28, 0x2C)) | {0x34, 0x38, 0x3C, 0x78}, (r["k"], t[0]["k"])
            assert first_match(rows, t[0]) == r["k"], (r["k"], t[0]["k"])
            twins.append((r["k"], t[0]["k"]))
    return {"si_profiles_checked": len(rule), "rasters": sorted(set(rule)),
            "rule": "+0x4c = 1.5 x width and +0x56 = half the height in whole 16-row macroblock rows (rounded down), in every XAVC S-I profile",
            "twins": "%d pairs (105xxx UseCore 2, 205xxx UseCore 0) that differ only in key, +0x34, +0x38/+0x3c and UseCore (none of them read by the "
                     "matcher); the matcher reaches the 105xxx row first in every pair" % len(twins)}, dict(twins)


def build(name, lm, av):
    cfg = SIZES_BY_BUILD[BUILD][name]
    W1, H1 = cfg["raster"]
    full = (W1 != W0)
    d = Design(name, f"A {W1} by {H1} file in XAVC S-I 4K (AVC intra 4:2:2 10-bit) at 23.98p and 25p: encoder request, descriptors and profiles; "
                     f"one step on top of the {W1}x{H1} open-gate state")
    # ---- libmpr: the comb row and the intra flag
    o = B.COMB + 0x18 * SI_COMB
    codec, w, h, aspect, chroma, depth, intra = struct.unpack_from("<IHH4I", lm, o)
    assert (codec, w, h, chroma, depth, intra) == (0, W0, H0, 1, 1, 1), (codec, w, h, chroma, depth, intra)
    assert struct.unpack_from("<7I", lm, VPCS[BUILD] + 0x1C * SI_COMB)[6] == 1, "m_vpcSt row 9 is not the intra row"
    if full:
        d.add("libmpr.so", lm, "L1-comb", o + 4, struct.pack("<HH", W1, H1),
              f"g_videoParamComb row {SI_COMB} (XAVC S-I 4K, AVC intra 4:2:2 10-bit): {W0}x{H0} -> {W1}x{H1} (the encoder request's raster)", struct.pack("<HH", W0, H0))
    else:
        d.add("libmpr.so", lm, "L1-comb", o + 6, struct.pack("<H", H1),
              f"g_videoParamComb row {SI_COMB} (XAVC S-I 4K, AVC intra 4:2:2 10-bit): height {H0} -> {H1} (the encoder request's height)", struct.pack("<H", H0))
    # ---- av-cam: descriptors and profiles
    rows = descriptor_table(av)
    prof_off = {}
    for base, n in B.PROFILE_TABLES:
        for k in range(n):
            prof_off.setdefault(struct.unpack_from("<I", av, base + k * 0x100 + 0x20)[0], []).append(base + k * 0x100)
    assert all(len(v) == 1 for k, v in prof_off.items() if any(r["key"] == k and r["codec"] == SI_CODEC for r in rows))
    prof_off = {k: v[0] for k, v in prof_off.items()}
    rule, twins = check_rule(rows, prof_off, av)
    urows = [struct.unpack_from("<4I", av, B.UNIT_TABLE + 0x10 * k) for k in range(10)]
    assert urows[4] == urows[2] == (0x486, 0x474, 0x477, 0x47A) and urows[9] == (0x664, 0x474, 0x477, 0x690), urows
    mine = [r for r in rows if r["codec"] == SI_CODEC and r["wh"] == (W0, H0) and not r["infr"] and r["codfr"] in RATES and r["key"] // 100000 == 1]
    assert sorted((r["codfr"], r["cls"]) for r in mine) == [(3, 13), (3, 18), (5, 14), (5, 19)], [(r["k"], r["codfr"], r["cls"]) for r in mine]
    key_users = {}
    for r in rows:
        key_users.setdefault(r["key"], []).append(r["k"])
    picked = []
    rf = rows_first(H1)
    assert rf % BLOCK_ROWS == 0 and abs(2 * rf - H1) < 2 * BLOCK_ROWS and rf == {2560: 1280, 3840: 1920}[H1]
    for r in mine:
        assert first_match(rows, r) == r["k"], f"descriptor #{r['k']} is not the one the matcher reaches"
        assert (r["core"], r["w38"][0], r["enc_cd_mode"], r["codec_type"], r["pred_mode"], r["chroma_code"], r["depth_code"]) == (2, 2, 0, 1, 0, 2, 1), r
        assert key_users[r["key"]] == [r["k"]], f"profile key {r['key']} is used by other descriptors: {key_users[r['key']]}"
        po = prof_off[r["key"]]
        p = av[po:po + 0x100]
        assert struct.unpack_from("<HH", p, 4) == (W0, H0) and struct.unpack_from("<II", p, 0x34) == (W0, H0) and struct.unpack_from("<HH", p, RASTER3) == (W0, H0)
        assert struct.unpack_from("<HH", p, 0x8A) == (0, 0) and struct.unpack_from("<H", p, 0x4C)[0] == W0 * 3 // 2 and struct.unpack_from("<H", p, 0x56)[0] == 1072
        assert p[LEVEL_OFF] == 51 and p[0xA6] == 122 and p[0xA8] == 2 and p[0x9B] == 0 and struct.unpack_from("<HH", p, 0x9C) == (1, 1), r["key"]
        budget = struct.unpack_from("<I", p, BUDGET)[0]
        assert budget in (10080256, 16076800), (r["key"], budget)
        rate = RATES[r["codfr"]]
        what = f"descriptor #{r['k']} (XAVC S-I 4K, 4:2:2 10-bit, {rate}, quality class {r['cls']}, key {r['key']}, UseCore 2)"
        if full:
            d.add("av-cam.bin", av, "A1-desc", r["o"] + 0x7E, struct.pack("<HH", W1, H1), what + f": raster +0x7e: {W0}x{H0} -> {W1}x{H1}", struct.pack("<HH", W0, H0))
        else:
            d.add("av-cam.bin", av, "A1-desc", r["o"] + 0x80, struct.pack("<H", H1), what + f": height +0x80 -> {H1}", struct.pack("<H", H0))
        pk = f"profile key {r['key']}"
        if full:
            d.add("av-cam.bin", av, "A2-profile", po + 4, struct.pack("<HH", W1, H1), pk + f": raster +0x04 -> {W1}x{H1}", struct.pack("<HH", W0, H0))
            d.add("av-cam.bin", av, "A2-profile", po + 0x34, struct.pack("<II", W1, H1), pk + f": raster +0x34 -> {W1}x{H1}", struct.pack("<II", W0, H0))
            d.add("av-cam.bin", av, "A2-profile", po + RASTER3, struct.pack("<HH", W1, H1), pk + f": raster +{RASTER3:#x} -> {W1}x{H1}", struct.pack("<HH", W0, H0))
            old = p[0x4C:0x58]
            d.add("av-cam.bin", av, "A2-profile", po + 0x4C, struct.pack("<H", W1 * 3 // 2) + old[2:10] + struct.pack("<H", rf),
                  pk + f": +0x4c: {W0 * 3 // 2} -> {W1 * 3 // 2} (1.5 x the width, as every S-I profile); rows for the first core +0x56: 1072 -> {rf} "
                       "(half the picture in whole macroblock rows; the eight bytes between are written as they are)", old)
            d.add("av-cam.bin", av, "A2-level", po + LEVEL_OFF, bytes([LEVEL6]),
                  pk + f": level {p[LEVEL_OFF]} -> {LEVEL6} (Level 6: the lowest level whose picture size limit holds {W1} by {H1}; Sony's 7680-wide AVC "
                       "profiles carry it)", bytes([p[LEVEL_OFF]]))
        else:
            d.add("av-cam.bin", av, "A2-profile", po + 6, struct.pack("<H", H1), pk + f": raster height +0x06 -> {H1}", struct.pack("<H", H0))
            d.add("av-cam.bin", av, "A2-profile", po + 0x38, struct.pack("<I", H1), pk + f": raster height +0x38 -> {H1}", struct.pack("<I", H0))
            d.add("av-cam.bin", av, "A2-profile", po + 0x56, struct.pack("<H", rf),
                  pk + f": rows for the first core +0x56: 1072 -> {rf} (half the picture in whole 16-row macroblock rows)", struct.pack("<H", 1072))
        twin_k = [t["k"] for t in rows if t["codec"] == SI_CODEC and t["key"] == r["key"] + 100000]
        picked.append({"descriptor": r["k"], "family": "si", "format": "4:2:2 10-bit intra", "rate": rate, "coding_rate_code": r["codfr"], "input_rate": 0,
                       "quality_class": r["cls"], "f0c": r["f0c"], "profile_key": r["key"], "pred_mode": r["pred_mode"], "use_core": r["core"],
                       "plus_38_3c": list(r["w38"]), "level_byte": p[LEVEL_OFF], "picture_bits": budget,
                       "bit_rate_millions": round(budget * (24000 / 1001 if r["codfr"] == 5 else 25) / 1e6, 1),
                       "twin_never_reached": twin_k[0] if twin_k else None})
    spans = sorted((p["binary"], int(p["file_off"], 16), len(p["new"]) // 2) for p in d.patches)
    assert all(a[0] != b[0] or a[1] + a[2] <= b[1] for a, b in zip(spans, spans[1:])), "sites overlap"
    assert all(len(p["new"]) // 2 <= 16 for p in d.patches)
    # the shared rows the state's step 4 changes: none of them is a site here (level 19 would refuse a site that is not stock)
    shared = [(B.UNIT_TABLE + 0x30, 16), (B.CLIP + 0x10, 16)]
    assert not any(b == "av-cam.bin" and s < a + n and a < s + ln for a, n in shared for b, s, ln in spans)
    return d, picked, rule


def main():
    global BUILD
    if "--build" in sys.argv:                             # 2026-11-25: fx3_702 (the FX3 kit's I19 step); the default stays the A7 IV
        BUILD = sys.argv[sys.argv.index("--build") + 1]
        B.use_build(BUILD)
    lm = locate_file.locate(BUILD, "libmpr.so").read_bytes()
    av = locate_file.locate(BUILD, "av-cam.bin").read_bytes()
    sha = {"libmpr.so": hashlib.sha256(lm).hexdigest(), "av-cam.bin": hashlib.sha256(av).hexdigest()}
    only = sys.argv[sys.argv.index("--only") + 1] if "--only" in sys.argv else None
    out_dir = ROOT / "modding" / "designs"
    designs = []
    for name, cfg in SIZES_BY_BUILD[BUILD].items():
        d, picked, rule = build(name, lm, av)
        W1, H1 = cfg["raster"]
        by, kinds = {}, {}
        for p in d.patches:
            by.setdefault(p["binary"], []).append(p)
            kinds[p["kind"]] = kinds.get(p["kind"], 0) + 1
        out = {"design": d.name, "title": d.title, "generated_by": "build/build_ogfile_si.py", "family": "si", "format": "XAVC S-I 4K (AVC intra)",
               "raster": [W1, H1], "rates": sorted(RATES.values()), "goes_with": cfg["goes_with"], "apply_after": cfg["after"], "shape_of": cfg["shape"],
               "artifact_sha256": sha,
               "summary": {b: {"sites": len(ps), "bytes": sum(len(p["new"]) // 2 for p in ps), "code_sites": sum(p["code"] for p in ps)} for b, ps in by.items()},
               "sites_by_kind": kinds,
               "level": ("Level 6 (60)" if W1 != W0 else "the stock level bytes are kept (51, Level 5.1), as ogfile2560_s_v1 did"),
               "encoder_cores": "both (UseCore 2), as every reachable stock XAVC S-I 4K descriptor",
               "memory": {"unit_type": "4 (intra above 8,847,360 pixels; build/emu_vcd_chmem.py unit_type)", "row_4_ids": [hex(i) for i in (0x486, 0x474, 0x477, 0x47A)],
                          "row_4_is_stock": True, "note": "no memory-class site: row 4 is the 4K class's in stock; row 3 (long GOP) is not used by intra"},
               "rule_checked_against_sonys_s_i_profiles": rule,
               "while_applied": ["XAVC S-I 4K at 23.98p and 25p records %dx%d; at 29.97p/50p/59.94p the request says %dx%d and finds no descriptor: refused at "
                                 "encoder open (do not use them)" % (W1, H1, W1, H1),
                                 "XAVC S-I HD and every other format are not touched by this step",
                                 "the picture bit budget is the menu's (240M at 24p, 250M at 25p): the same bits for a bigger picture",
                                 "the MP4 headers say what the state's step 4 makes them say for AVC 3840-wide formats (%dx%d with ogfile2560_hs_s_v2 / "
                                 "ogfile57r300m1_v4; 3840x2160 with their --no-meta variants); Sony's XML says 3840x2160" % (W1, H1)],
               "descriptors": picked, "patches": d.patches, "optional_sites": []}
        if BUILD == "fx3_702":                            # the FX3's words (the A7 IV designs' text is unchanged)
            out = {**{"build": BUILD, "camera": "ILME-FX3 (FX3), firmware 7.02"}, **out}
            out["level"] = "the stock level bytes are kept (51, Level 5.1), as the FX3's ogfile2560_hs_s_fx3_v1 / v2 keep XAVC S 4K's"
            out["memory"]["unit_type"] = "4 (intra above 8,847,360 pixels; the FX3's memory function 0x21dd54 is the A7 IV's 0x2136c4, emulated in build/emu_ogfilesi_fx3.py)"
            out["while_applied"][3] = ("the MP4 headers say what the kit's step L19 makes them say for AVC 3840-wide formats (%dx%d with ogfile2560_hs_s_fx3_v2; "
                                       "3840x2160 with --no-meta, the first kit's v1); Sony's XML says 3840x2160" % (W1, H1))
            out["status"] = "built from the FX3 7.02 files and emulated on its own code (build/emu_ogfilesi_fx3.py); never run on an FX3 or on an A7 IV"
        elif BUILD == "a1m2_400":                         # the A1 II's words (2026-11-26)
            out = {**{"build": BUILD, "camera": "ILCE-1M2 (A1 II), firmware 4.00"}, **out}
            out["level"] = "the stock level bytes are kept (51, Level 5.1), as the A1 II's ogfile2560_hs_s_a1m2_v1 / v2 keep XAVC S 4K's"
            out["memory"]["unit_type"] = ("4 (intra above 8,847,360 pixels; the A1 II's memory function 0x22c9e8, the A7 IV's logic recompiled, emulated in "
                                          "build/run_ogfile_emu_a1m2.py)")
            out["while_applied"][3] = ("the MP4 headers say what the kit's encoder step makes them say for AVC 3840-wide formats (%dx%d with "
                                       "ogfile2560_hs_s_a1m2_v2; 3840x2160 with its v1); Sony's XML says 3840x2160" % (W1, H1))
            out["status"] = "built from the A1 II 4.00 files and emulated on its own code (build/run_ogfile_emu_a1m2.py); never run on an A1 II"
        out_dir.mkdir(exist_ok=True)
        (out_dir / f"{d.name}.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf8", newline="\n")
        for b, ps in by.items():
            (out_dir / f"{d.name}_pokes_{b.split('.')[0].replace('-', '')}.txt").write_text("".join(f"{p['file_off']} {p['new']}\n" for p in ps), encoding="utf8",
                                                                                           newline="\n")
        print(d.name, out["summary"], kinds, "descriptors:", len(picked))
        if "--list" in sys.argv:
            for p in picked:
                print("    #%d %s %s class %d key %d core %d level %d picture bits %d (%.1f Mbps) twin #%s" % (
                    p["descriptor"], p["format"], p["rate"], p["quality_class"], p["profile_key"], p["use_core"], p["level_byte"], p["picture_bits"],
                    p["bit_rate_millions"], p["twin_never_reached"]))
            for p in d.patches:
                print("      %s %s %s -> %s  %s" % (p["binary"], p["file_off"], p["old"], p["new"], p["kind"]))
        designs.append(d)
    if "--register" in sys.argv:
        import records
        st = records.Store()
        names = [d.name for d in designs if only in (None, d.name)]
        st.begin("designs %s: the encoder side of an open-gate file in XAVC S-I 4K, as patch sites" % ", ".join(names), WHY,
                 evidence="modding/designs/<name>.json from build/build_ogfile_si.py", author="build_ogfile_si.py")
        for d in designs:
            if only not in (None, d.name):
                continue
            for i, p in enumerate(d.patches, 1):
                data = {"design": d.name, "design_title": d.title, "artifact": p["binary"], "artifact_sha256": sha[p["binary"]], "addr": p["va"],
                        "file_off": p["file_off"], "length": len(p["new"]) // 2, "old_hex": p["old"], "old_source": "stock file", "new_hex": p["new"],
                        "patch_kind": p["kind"], "risk_class": "R2", "old_verified": True, "note": p["note"], "source": f"modding/designs/{d.name}.json"}
                rid, ttl = f"PS-{d.name}-{i}", f"{d.name} {p['kind']}: {p['note']}"
                if rid in st.records:
                    st.amend(rid, data, title=ttl)
                else:
                    st.add("patch_site", ttl, data, id=rid, level="static", certainty="inferred", build=BUILD, subsystem="patch-design")
        print("registered:", st.commit(), "changes")


if __name__ == "__main__":
    main()
