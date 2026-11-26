"""Emulated check of the FX3's encoder steps for 29.97p (2026-11-26): `ogfile2560_hs_s_fx3_v3` (L19: XAVC HS 4K and XAVC S 4K at 23.98p, 25p and
29.97p, MP4 header heights) and `ogfilesi2560_fx3_v2` (I19: XAVC S-I 4K at the same three rates), both from build/build_ogfile.py /
build_ogfile_si.py --rate30, run on the FX3 7.02's own av-cam and libmpr code (the functions build/emu_ogfilesi_fx3.py locates).

  C:\\Python313\\python.exe -B build/emu_ogfile30_fx3.py        writes evidence/fx3/ogfile30_fx3_emu.json

Checks, stock against the state (v3 + S-I v2 applied in emulated memory):
  shape        v3 holds every site of v2 (the kit's L19 since 2026-11-25) and S-I v2 every site of S-I v1, with the same bytes: what the new steps
               add is the 29.97p descriptors and their profiles only; so the put back (L20 / I20 built from v3 / S-I v2) also puts back a camera
               that has v2 / v1 applied
  one core     every FX3 3840x2160 long-GOP descriptor at rate codes 0-5 (59.94p down to 23.98p) uses one encoder core: the 29.97p ones keep it
  matcher      the FX3's matcher (0x225eb8) finds each changed descriptor for a 3840x2560 request of its own kind (every rate, every class); every other
               AVC / HEVC / S-I request from 1920 wide up gives the same answer as stock; a 3840x2560 request of a rate the steps do not serve
               (50p, 59.94p, high frame rates) finds nothing, so the camera refuses it at encoder open (as at 24p today)
  memory       the memory function (0x21dd54) asks the same blocks for a 29.97p request at 3840x2560 as for 23.98p (long GOP: unit row 3, which L19
               makes the 4K row; S-I: row 4); the codec firmware's need for each changed descriptor fits the FX3's DmmCfg blocks
  start block  the FX3's start-block builder (0x221b50) takes each changed profile at 3840x2560 (crop 3840x2560, no error)
  MP4          the FX3's track config gives 3840x2560 for combs 0, 2, 5, 7, 9 at every rate code the stock code accepts, with the stock profile id
  clip code    3840x2560 gets 23, the 4K code
  overlap      no site is one of the sensor or playback steps' (those are other files), and none of S-I v2's is one of v3's
"""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import emu_mp4_meta  # noqa: E402
import emu_ogfilesi_fx3 as SI  # noqa: E402
import emu_vcd_chmem  # noqa: E402
import locate_file  # noqa: E402
import parse_dmmcfg  # noqa: E402
from run_ogfile_emu import AvCam, D  # noqa: E402

BUILD = "fx3_702"
V3, V2, SIV2, SIV1 = "ogfile2560_hs_s_fx3_v3", "ogfile2560_hs_s_fx3_v2", "ogfilesi2560_fx3_v2", "ogfilesi2560_fx3_v1"
W0, H0, W1, H1 = 3840, 2160, 3840, 2560
RATE = {5: "23.98p", 3: "25p", 2: "29.97p", 1: "50p", 0: "59.94p"}


def sites(name):
    return {(p["binary"], p["file_off"], p["old"], p["new"]) for p in json.loads((D / f"{name}.json").read_text(encoding="utf8"))["patches"]}


def main():
    a7 = locate_file.locate("a7iv_602", "av-cam.bin").read_bytes()
    av = locate_file.locate(BUILD, "av-cam.bin").read_bytes()
    lm = locate_file.locate(BUILD, "libmpr.so").read_bytes()
    v3 = json.loads((D / f"{V3}.json").read_text(encoding="utf8"))
    si = json.loads((D / f"{SIV2}.json").read_text(encoding="utf8"))
    res, checks = {"designs": [V3, SIV2], "functions": SI.find_functions(a7, av)}, {}

    # ---- shape
    checks["v3 holds every site of v2 with the same bytes, and S-I v2 every site of S-I v1: only 29.97p descriptors and profiles are added"] = (
        sites(V2) <= sites(V3) and sites(SIV1) <= sites(SIV2)
        and all(int(p["file_off"], 16) for p in v3["patches"]) and {x["rate"] for x in v3["descriptors"] if x["descriptor"] not in
                                                                    {y["descriptor"] for y in json.loads((D / f"{V2}.json").read_text(encoding="utf8"))["descriptors"]}} == {"29.97p"})
    res["added_sites"] = {V3: len(sites(V3) - sites(V2)), SIV2: len(sites(SIV2) - sites(SIV1))}

    # ---- one core
    s = AvCam(av, SI.FN)
    wide = [s.desc(k) for k in range(SI.NDESC)]
    long_gop = [(k, d) for k, d in enumerate(wide) if d["codec"] in (4, 0xE) and (d["w"], d["h"]) == (W0, H0)
                and struct.unpack_from("<I", av, SI.DESC + k * 0x90 + 8)[0] <= 5 and not struct.unpack_from("<I", av, SI.DESC + k * 0x90 + 4)[0]]
    cores = {k: av[SI.DESC + k * 0x90 + 0x78] for k, _ in long_gop}
    checks["every FX3 3840x2160 long-GOP descriptor at 59.94p..23.98p (rate codes 0-5) uses one encoder core, so 29.97p at 3840x2560 keeps one"] = (
        bool(cores) and set(cores.values()) == {0})
    res["one_core_descriptors_up_to_59_94p"] = len(cores)

    # ---- matcher
    state = SI.apply(av, V3, SIV2)
    c = AvCam(state, SI.FN)
    changed = {x["descriptor"]: x for x in v3["descriptors"] + si["descriptors"]}
    found, good = [], True
    for k, x in sorted(changed.items()):
        d = s.desc(k)
        a, b, b0 = s.select(d, W0, H0), c.select(d, W1, H1), s.select(d, W1, H1)
        ok = a == k and b == k and b0 is None
        good &= ok
        found.append({"descriptor": k, "rate": x["rate"], "class": x["quality_class"], "stock_2160": a, "state_2560": b, "stock_2560": b0, "ok": ok})
    checks["the FX3's matcher finds each changed descriptor (%d, every rate and class) for 3840x2560 with the steps, and none without" % len(changed)] = good
    same, n, moved, refused = True, 0, [], {}
    for k, d in enumerate(wide):
        if k in changed or d["codec"] not in (4, 0xE, 0x18) or d["w"] < 1920:
            continue
        a, b = s.select(d, d["w"], d["h"]), c.select(d, d["w"], d["h"])
        n += 1
        if a != b:
            moved.append({"built_from": k, "stock": a, "state": b})
            same &= a in changed                                       # only a request whose stock answer is a changed row (its twin's own fields)
        if (d["w"], d["h"]) == (W0, H0) and a not in changed:
            rc = struct.unpack_from("<I", av, SI.DESC + k * 0x90 + 8)[0]
            r = c.select(d, W1, H1)
            refused.setdefault(RATE.get(rc, "code %d" % rc), set()).add(r)
            same &= r is None or r in changed
    checks["every other AVC/HEVC/S-I request from 1920 wide up gives the stock answer (but a changed row's own match fields)"] = same
    checks["3840x2560 requests of rates the steps do not serve (50p, 59.94p, high frame rates) find nothing: refused at encoder open"] = all(
        v == {None} for r, v in refused.items() if r not in ("23.98p", "25p", "29.97p"))
    res["matcher"] = {"changed": found, "requests_compared": n, "answers_that_moved": moved,
                      "other_3840_requests_at_2560": {r: sorted(str(x) for x in v) for r, v in refused.items()}}

    # ---- memory
    def pick(rate, codec):
        return next(k for k, x in changed.items() if x["rate"] == rate and s.desc(k)["codec"] == codec)
    mem_ids = {}
    for codec, name in ((0xE, "HEVC"), (4, "AVC"), (0x18, "S-I")):
        for rate in ("23.98p", "29.97p"):
            k = pick(rate, codec)
            mem_ids[f"{name} {rate}"] = c.unit_ids(s.desc(k), W1, H1)
    checks["the memory function asks the same blocks at 29.97p as at 23.98p (HEVC, AVC, S-I), no error"] = all(
        mem_ids[f"{nm} 29.97p"]["memory_ids_asked"] == mem_ids[f"{nm} 23.98p"]["memory_ids_asked"] and not mem_ids[f"{nm} 29.97p"]["errors_logged"]
        and mem_ids[f"{nm} 29.97p"]["returned"] == mem_ids[f"{nm} 23.98p"]["returned"] for nm in ("HEVC", "AVC", "S-I"))
    res["memory_ids"] = mem_ids
    cfg = parse_dmmcfg.Config(parse_dmmcfg.find_file(BUILD, "setting"), BUILD)
    size = lambda i: max(u["size"] for k in cfg.id_rows.get(i, {}).get("keys", []) for u in cfg.units_by_key.get(k, []))
    table = [struct.unpack_from("<4I", state, SI.UNIT + 0x10 * k) for k in range(10)]
    fw = emu_vcd_chmem.Firmware()
    mem, fit = [], True
    for k in sorted(changed):
        dd = SI.descriptor(state, k)
        row = table[4] if dd["codec"] == 0x18 else table[3]                         # intra above 8,847,360 pixels: row 4; long GOP: row 3 (= the 4K row with L19)
        have = {"cd": size(row[0]), "ld": size(row[1]), "multi": size(row[2])}
        need = fw.need(dd)
        f = (dd["w"], dd["h"]) == (W1, H1) and all(need[x] <= have[x] for x in have) and not need["asserts"]
        fit &= f
        mem.append({"descriptor": k, "rate": changed[k]["rate"], "use_core": dd["use_core"], "need": {x: need[x] for x in have}, "have": have, "fits": f})
    checks["the codec firmware's need for every changed descriptor at 3840x2560 fits the FX3's blocks (row 3 = the 4K row for long GOP, row 4 for S-I)"] = fit
    res["codec_memory"] = mem
    res["unit_rows_3_4"] = [[hex(i) for i in table[3]], [hex(i) for i in table[4]]]

    # ---- start block
    prof = {}
    for base, cnt in SI.PROFILES:
        for k in range(cnt):
            prof[struct.unpack_from("<I", av, base + k * 0x100 + 0x20)[0]] = base + k * 0x100
    starts, sgood = [], True
    for k in sorted(changed):
        d = s.desc(k)
        o = prof[d["key"]]
        a, _ = s.start_block(av[o:o + 0x100], d, W0, H0, True)
        b, _ = c.start_block(state[o:o + 0x100], d, W1, H1, True)
        ok = a["returned"] == 1 and not a["errors_logged"] and a["crop_size"] == [W0, H0] and b["returned"] == 1 and not b["errors_logged"] and b["crop_size"] == [W1, H1]
        sgood &= ok
        if changed[k]["rate"] == "29.97p":
            starts.append({"descriptor": k, "stock_3840x2160": a, "state_3840x2560": b, "ok": ok})
    checks["the FX3's start-block builder takes every changed profile at 3840x2560 (and at 3840x2160 in stock), no error"] = sgood
    res["start_block_29_97p"] = starts

    # ---- MP4 headers, the clip code
    lib_s, lib_t = emu_mp4_meta.Lib(lm, BUILD), emu_mp4_meta.Lib(SI.apply(lm, V3, SIV2, kind="libmpr"), BUILD)
    mp4, mgood = [], True
    for comb in (0, 2, 5, 7, 9):
        for rate_code in range(0, 6):
            for rate_index in range(2, 0x36):
                r0, cfg0 = lib_s.config(comb, rate_code, rate_index)
                if r0 != 0:
                    continue
                r1, cfg1 = lib_t.config(comb, rate_code, rate_index)
                rs, sz = lib_t.stsd(cfg1)
                rp, pf = lib_t.prof(cfg1)
                rp0, pf0 = lib_s.prof(cfg0)
                ok = r1 == 0 and struct.unpack_from("<HH", cfg1, 0x28) == (H1, W1) and rs == 0 and list(sz) == [W1, H1] and rp == rp0 and pf["profile_id"] == pf0["profile_id"]
                mgood &= ok
                mp4.append((comb, rate_code, rate_index, ok))
    checks["the FX3's track config: 3840x2560 in tkhd/stsd for combs 0, 2, 5, 7, 9 at every rate code and bit-rate index the stock code accepts, stock profile ids"] = (
        mgood and len({(x[0], x[1]) for x in mp4}) >= 10)
    res["mp4"] = {"requests": len(mp4), "comb_rate_pairs": sorted({(x[0], x[1]) for x in mp4})}
    res["clip_code"] = c.clip(W1, H1)
    checks["clip-format code of 3840x2560 is 23 (the 4K code)"] = res["clip_code"] == SI.CLIP_4K

    # ---- overlap
    a_sites = {(b, int(o, 16), len(nw) // 2) for b, o, _, nw in sites(V3)}
    b_sites = {(b, int(o, 16), len(nw) // 2) for b, o, _, nw in sites(SIV2)}
    other = json.loads((D / "avdec8k_fx3_v1.json").read_text(encoding="utf8"))
    o_sites = {("av-cam.bin", int(p["file_off"], 16), len(p["new"]) // 2) for key in ("code_sites", "data_sites") for p in other.get(key, [])}
    clash = lambda X, Y: any(a == b and x < y + m and y < x + nn for a, x, nn in X for b, y, m in Y)
    checks["no site of S-I v2 is one of v3's, and neither touches the playback step's sites"] = not clash(a_sites, b_sites) and not clash(a_sites | b_sites, o_sites) and o_sites

    res["checks"] = checks
    out = ROOT / "evidence/fx3/ogfile30_fx3_emu.json"
    out.write_text(json.dumps(res, indent=1, default=str) + "\n", encoding="utf8", newline="\n")
    bad = 0
    for text, ok in checks.items():
        print("   %s  %s" % ("PASS" if ok else "FAIL", text))
        bad += not ok
    print("   added sites:", res["added_sites"], "| one-core descriptors up to 59.94p:", res["one_core_descriptors_up_to_59_94p"],
          "| requests compared:", n, "| MP4 requests:", len(mp4))
    print("   memory e.g.:", mem[0] if mem else None)
    if bad:
        raise SystemExit("%d check(s) failed" % bad)
    print("all checks passed; wrote", out)


if __name__ == "__main__":
    main()
