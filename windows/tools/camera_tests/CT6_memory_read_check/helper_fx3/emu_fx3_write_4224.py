"""Run the eleven libraries of the FX3's 4224 x 2816 state in Unicorn against a model camera. Offline; no camera.

  C:/Python313/python.exe -B emu_fx3_write_4224.py

  H5 / H6    levels 5 / 6 with ogh2816_fx3_v1 (ogsq_fx3_v2's cells for 0x8c0 and 0x820, the two records with the first stage passed one to one, the
             stored records of both modes in NTSC and PAL form with the ratio 27/32)
  D16 / D17  levels 16 / 17 with dmm7slot_fx3_v1 (ten words of the run-time copy of DmmCfg.bin's unit records)
  K16 / K17  levels 16 / 17 with outsz4224_fx3_v1 (the output-size word)
  K19 / K20  levels 19 / 20 with ogfile4224_fx3_v1 (encoder side, MP4 header size);  J19 = ogfile4224nm_fx3_v1 (no header size; K20 puts it back)
  R19 / R20  levels 19 / 20 with ogfile4224r300_fx3_v1 (the 100M settings at 300 Mbps)

The harness and the coprocessor model are emu_fx3_write.py's. It is the FX3 form of helper_s3/emu_s3_write_4224.py: the same cases, on an NTSC and
on a PAL camera, and each library of this state on a camera that holds the 3840 x 2560 state's bytes (it must then write nothing) and the other
way round.
"""
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "helper"))
sys.path.insert(0, str(ROOT / "build"))
import emu_built as E  # noqa: E402
import emu_fx3_write as W  # noqa: E402

RESULT, RECS, REC, BASE = E.RESULT, W.RECS, W.REC, W.BASE
design, ex = W.design, W.ex
UNIT = 0x395068


def byte_pairs(sites):
    out = {}
    for a, old, new in sites:
        for k, (o, n) in enumerate(zip(old, new)):
            out[a + k] = (o, n)
    return out


def og_sites(og, system):
    s = [(int(p["addr"], 16), bytes.fromhex(p["old"]), bytes.fromhex(p["new"])) for p in og["patches"]]
    for idx, (st, nw) in W.records(og, system).items():
        s += [(RECS + idx * REC + k, bytes([st[k]]), bytes([nw[k]])) for k in range(REC) if st[k] != nw[k]]
    return s


def word_sites(d):
    return [(int(s["ram_address"], 16), bytes.fromhex(s["old"]), bytes.fromhex(s["new"])) for s in d["sites"]]


def main():
    fail, n_pass = [], [0]

    def ok(cond, text):
        print(("PASS  " if cond else "FAIL  ") + text)
        n_pass[0] += bool(cond)
        if not cond:
            fail.append(text)

    named = lambda n: (HERE / f"libJit_fx3_{n}.so").read_bytes()
    og, v2 = design("ogh2816_fx3_v1"), design("ogsq_fx3_v2")
    dm, oz, oz2560 = design("dmm7slot_fx3_v1"), design("outsz4224_fx3_v1"), design("outsz2560_fx3_v1")
    image = ex("nflasha8/cpapp-b.bin")
    files = E.tree()
    files["/dev/mem"] = b""
    dirs = {"/tmp_wbshd", "/sys/module/liro/parameters", "/proc/driver/pcie"}
    import build_dmm_s3 as DM
    import parse_dmmcfg as P
    DM.BUILD = "fx3_702"
    cfg = P.Config(P.find_file("fx3_702"), "fx3_702")
    dmm_base, dmm_table, _ = DM.ram_table(cfg)
    assert dmm_base == 0x1F7F90C

    def camera(system="ntsc"):
        m = W.camera(image, og, oz, system)
        m.write(dmm_base, dmm_table)
        return m

    def go(n, mem, pairs, **kw):
        r = W.Run(named(n), files, dirs, mem, pairs, **kw).go()
        return r, r.writes.get(RESULT, b"").decode("utf8", "replace")

    def state(mem, pairs):
        vals = [(mem.read(a, 1)[0], pr) for a, pr in pairs.items()]
        return "stock" if all(v == pr[0] for v, pr in vals) else "new" if all(v == pr[1] for v, pr in vals) else "mixed"

    def unchanged_but(mem, before, pairs):
        for a, p in mem.pages.items():
            b = before.get(a)
            if b is None:
                b = image[a - BASE:a - BASE + 4096].ljust(4096, b"\0") if BASE <= a < BASE + len(image) else bytes(4096)
            if any(p[k] != b[k] and (a + k) not in pairs for k in range(4096)):
                return False
        return True

    # ---- H5 / H6: the sensor side, on an NTSC and on a PAL camera
    for system in ("ntsc", "pal"):
        pairs = byte_pairs(og_sites(og, system))
        mem = camera(system)
        before = mem.snapshot()
        r, t = go("H5", mem, pairs)
        ok(not r.bad and "DONE: all " in t and "(apply)" in t and state(mem, pairs) == "new" and unchanged_but(mem, before, pairs),
           "H5 on a stock %s camera: every site and both modes' stored records are new, nothing else changed (%d line writes)" % (system.upper(), r.n_writes))
        ok(all(mem.read(RECS + idx * REC + 6, 2) == bytes([27, 32]) for idx in (10, 12)), "H5 (%s): the stored records of 0x820 and 0x8c0 hold the ratio 27/32" % system.upper())
        r, t = go("H5", mem, pairs)
        ok(not r.bad and "NOTHING TO DO" in t and r.n_writes == 0, "H5 again (%s): nothing to do, no write" % system.upper())
        r, t = go("H6", mem, pairs)
        ok(not r.bad and "(put back)" in t and "DONE" in t and state(mem, pairs) == "stock" and mem.snapshot() == {a: before.get(a, mem.snapshot()[a]) for a in mem.pages},
           "H6 (%s): everything is stock again, byte for byte" % system.upper())
        for lose in (1, 12, 30):
            mem = camera(system)
            before = mem.snapshot()
            r, t = go("H5", mem, pairs, lose=lose)
            ok(not r.bad and "NOT DONE: a step failed; every site this run touched was put back" in t and state(mem, pairs) == "stock" and unchanged_but(mem, before, ()),
               "H5 (%s) with line write %d lost: reported, and every site put back" % (system.upper(), lose))
        # the camera holds the 3840x2560 state's sensor step (ogsq_fx3_v2): the cells are this design's too, the records and ratios are not
        mem = camera(system)
        for a, old, new in og_sites(v2, system):
            mem.write(a, new)
        before = mem.snapshot()
        r, t = go("H5", mem, pairs)
        ok(not r.bad and r.n_writes == 0 and "nothing is written" in t and mem.snapshot() == before, "H5 on a %s camera holding ogsq_fx3_v2 (step L5): nothing is written" % system.upper())
        mem = camera(system)
        for a, old, new in og_sites(og, system):
            mem.write(a, new)
        before = mem.snapshot()
        r = W.Run(named("L5"), files, dirs, mem, byte_pairs(og_sites(v2, system))).go()
        ok(not r.bad and r.n_writes == 0 and mem.snapshot() == before, "L5 (the 3840x2560 state's sensor step) on a %s camera holding H5: nothing is written" % system.upper())
        r = W.Run(named("L6"), files, dirs, mem, byte_pairs(og_sites(v2, system))).go()
        ok(not r.bad and r.n_writes == 0 and mem.snapshot() == before, "L6 on a %s camera holding H5: nothing is written (H6 is its put back)" % system.upper())
    mem = W.camera(image, og, oz, "ntsc", stock_of={10: "pal"})
    mem.write(dmm_base, dmm_table)
    before = mem.snapshot()
    r, t = go("H5", mem, byte_pairs(og_sites(og, "ntsc")))
    ok(not r.bad and r.n_writes == 0 and "hold neither timing variant" in t and all(mem.snapshot()[a] == b for a, b in before.items()),
       "H5 with the two stored records of different systems: refused, nothing is written")

    # ---- D16 / D17: the output planes
    pairs = byte_pairs(word_sites(dm))
    mem = camera()
    before = mem.snapshot()
    r, t = go("D16", mem, pairs)
    ok(not r.bad and "DONE: every site holds the target bytes (apply)" in t and state(mem, pairs) == "new" and unchanged_but(mem, before, pairs),
       "D16 on a stock camera: the ten words are new, every other byte of the table and of the model unchanged (%d line writes)" % r.n_writes)
    sizes = [struct.unpack("<I", mem.read(int(s["ram_address"], 16), 4))[0] for s in dm["sites"]]
    ok(sorted(sizes) == sorted([0xE40000] * 8 + [0x7FD, 4096]), "D16: eight planes of 14,942,208 bytes, the ninth record key 0x7fd and 4,096 bytes")
    r, t = go("D16", mem, pairs)
    ok(not r.bad and "NOTHING TO DO" in t and r.n_writes == 0, "D16 again: nothing to do, no write")
    r, t = go("D17", mem, pairs)
    ok(not r.bad and "(put back)" in t and "DONE" in t and state(mem, pairs) == "stock" and mem.snapshot() == {a: before.get(a, mem.snapshot()[a]) for a in mem.pages},
       "D17: the table is the file's again, byte for byte")
    bad = 0
    for g in dm["guards"]:
        mem = camera()
        ga = int(g["ram_address"], 16)
        mem.write(ga, bytes([mem.read(ga, 1)[0] ^ 1]))
        r, t = go("D16", mem, pairs)
        bad += bool(r.bad or r.n_writes or "are not as expected; nothing is written" not in t)
    ok(not bad, "D16 with any one of the %d guards wrong: nothing is written" % len(dm["guards"]))
    mem = camera()
    mem.write(int(dm["sites"][3]["ram_address"], 16), struct.pack("<I", 14_745_600))
    r, t = go("D16", mem, pairs)
    ok(not r.bad and r.n_writes == 0 and "holds neither the earlier nor the new bytes; nothing is written" in t, "D16 with one plane holding another size: nothing is written")
    for lose in (1, 4, 10):
        mem = camera()
        r, t = go("D16", mem, pairs, lose=lose)
        ok(not r.bad and "NOT DONE: a step failed; every site this run touched was put back" in t and state(mem, pairs) == "stock",
           "D16 with line write %d lost: reported, and every word put back" % lose)

    # ---- K16 / K17: the output size
    pairs = byte_pairs(word_sites(oz))
    mem = camera()
    before = mem.snapshot()
    r, t = go("K16", mem, pairs)
    ok(not r.bad and state(mem, pairs) == "new" and unchanged_but(mem, before, pairs) and mem.read(int(oz["sites"][0]["ram_address"], 16), 4) == struct.pack("<HH", 4224, 2816),
       "K16 on a stock camera: the size word is 4224 x 2816, nothing else changed")
    r, t = go("K17", mem, pairs)
    ok(not r.bad and state(mem, pairs) == "stock", "K17: the size word is stock again")
    mem = camera()
    mem.write(int(oz2560["sites"][0]["ram_address"], 16), bytes.fromhex(oz2560["sites"][0]["new"]))
    before = mem.snapshot()
    r, t = go("K16", mem, pairs)
    ok(not r.bad and r.n_writes == 0 and mem.snapshot() == before, "K16 on a camera holding 3840 x 2560 (step L16): nothing is written")
    mem = camera()
    mem.write(int(oz["guards"][0]["ram_address"], 16), bytes(8))
    r, t = go("K16", mem, pairs)
    ok(not r.bad and r.n_writes == 0 and state(mem, pairs) == "stock", "K16 with the size table not filled (guard zero): nothing is written")

    # ---- main processor: the encoder side (K19 / K20, J19, R19 / R20)
    av, lm = ex("nflasha3/av-cam.bin"), ex("nflasha15/lib/libmpr.so")
    av = bytes([0x5A]) * 0x1000 + av[0x1000:]            # as on a camera: the first page is not the file's
    phoff, phentsize, phnum = struct.unpack_from("<Q", lm, 0x20)[0], *struct.unpack_from("<HH", lm, 0x36)
    span = next(struct.unpack_from("<IIQQQQQQ", lm, phoff + k * phentsize) for k in range(phnum) if struct.unpack_from("<I", lm, phoff + k * phentsize)[0] == 1)[5]
    lspan = (span + 0xFFF) & ~0xFFF
    lm0 = lm[:span].ljust(lspan, b"\0")
    LM_AT = W.LM_AT
    mfiles = dict(files)
    mfiles["/proc/self/mem"] = b""
    mfiles["/proc/self/maps"] = (b"00400000-00409000 r-xp 00000000 fc:8f 81970                              /usr/bin/im.elf\n"
                                 b"7f5c1e3000-7f6120c000 r-xp 00000000 fc:8f 55369                          /usr/lib/appFw.so\n"
                                 + b"%x-%x r-xp 00000000 fc:8f 55354                          /usr/lib/libmpr.so\n" % (LM_AT, LM_AT + lspan)
                                 + b"%x-%x ---p %08x fc:8f 55354                          /usr/lib/libmpr.so\n" % (LM_AT + lspan, LM_AT + lspan + 0x10000, lspan)
                                 + b"%x-%x r--p %08x fc:8f 55354                          /usr/lib/libmpr.so\n" % (LM_AT + lspan + 0x10000, LM_AT + lspan + 0x19000, lspan)
                                 + b"7f8b936000-7f8b991000 r-xp 00000000 fc:8f 55344                          /usr/lib/libsencore.so\n")

    def sites_of(name):
        s = {"av-cam.bin": [], "libmpr.so": []}
        for p in design(name)["patches"]:
            s[p["binary"]].append((int(p["file_off"], 16), bytes.fromhex(p["old"]), bytes.fromhex(p["new"])))
        return s

    def applied(blob, which, *names):
        b = bytearray(blob)
        for name in names:
            for o, old, new in sites_of(name)[which]:
                b[o:o + len(new)] = new
        return bytes(b)

    def mp(n, av_mem, lm_mem, **wrong):
        r = E.Run(named(n), int(n[1:]), mfiles, dirs, {E.AVCAM_PHYS: av_mem}, own={LM_AT: lm_mem})
        r.kview_fail = wrong.get("kview_fail", False)
        r.stale = {E.AVCAM_PHYS + o for o in wrong.get("stale", ())}
        r.pwrite_lost = {LM_AT + o for o in wrong.get("pwrite_lost", ())}
        r.go()
        return r, r.writes.get(RESULT, b"").decode("utf8", "replace"), bytes(r.phys[E.AVCAM_PHYS]), bytes(r.uc.mem_read(LM_AT, lspan))

    for step, back, name in (("K19", "K20", "ogfile4224_fx3_v1"), ("J19", "K20", "ogfile4224nm_fx3_v1"), ("R19", "R20", "ogfile4224r300_fx3_v1")):
        s = sites_of(name)
        av1, lm1 = applied(av, "av-cam.bin", name), applied(lm0, "libmpr.so", name)
        r, t, a, m = mp(step, av, lm0)
        ok(not r.bad and a == av1 and m == lm1 and "DONE" in t,
           "%s on a stock camera: %d + %d sites new, every other byte of both files' memory unchanged" % (step, len(s["av-cam.bin"]), len(s["libmpr.so"])))
        r, t, a, m = mp(step, av1, lm1)
        ok(not r.bad and a == av1 and m == lm1 and not r.pwrites and not r.map_writes, "%s again: no write" % step)
        r, t, a, m = mp(back, av1, lm1)
        ok(not r.bad and a == av and m == lm0 and "DONE" in t, "%s after %s: both are stock again, byte for byte" % (back, step))
        bad_av = bytearray(av)
        bad_av[UNIT + 0x20] ^= 1
        r, t, a, m = mp(step, bytes(bad_av), lm0)
        ok(not r.bad and a == bytes(bad_av) and m == lm0 and not r.pwrites and not r.map_writes, "%s with a guard of av-cam.bin wrong: nothing is written" % step)
        for off in sorted({s["libmpr.so"][0][0], s["libmpr.so"][-1][0]}):
            r, t, a, m = mp(step, av, lm0, pwrite_lost=[off])
            ok(not r.bad and a == av and m == lm0 and "NOT DONE: a step failed; every site this run touched was put back" in t,
               "%s with the libmpr.so write at %#x lost: everything put back" % (step, off))
        r, t, a, m = mp(step, av, lm0, stale=[s["av-cam.bin"][3][0]])
        ok(not r.bad and a == av and m == lm0 and "NOT DONE: a step failed; every site this run touched was put back" in t, "%s with the kernel's view not following a write: everything put back" % step)
    meta = [p for p in design("ogfile4224_fx3_v1")["patches"] if p["kind"] == "L4-mp4size"]
    first = min(int(p["file_off"], 16) for p in meta)
    bad_lm = bytearray(lm0)
    bad_lm[first - 4] ^= 1
    r, t, a, m = mp("K19", av, bytes(bad_lm))
    ok(len(meta) == 9 and not r.bad and a == av and m == bytes(bad_lm) and not r.pwrites and not r.map_writes, "K19 with the instruction before a header site wrong: nothing is written")
    # the 3840x2560 state's encoder steps applied (L19 = v3, N19 = v1, with or without the S-I step): this state's libraries write nothing
    for label, names in (("L19", ("ogfile2560_hs_s_fx3_v3",)), ("L19 and I19", ("ogfile2560_hs_s_fx3_v3", "ogfilesi2560_fx3_v2")), ("N19", ("ogfile2560_hs_s_fx3_v1",))):
        av2, lm2 = applied(av, "av-cam.bin", *names), applied(lm0, "libmpr.so", *names)
        for step in ("K19", "J19", "R19"):
            r, t, a, m = mp(step, av2, lm2)
            ok(not r.bad and a == av2 and m == lm2 and not r.pwrites and not r.map_writes, "%s on a camera holding the 3840x2560 state's %s: nothing is written" % (step, label))
    av1, lm1 = applied(av, "av-cam.bin", "ogfile4224_fx3_v1"), applied(lm0, "libmpr.so", "ogfile4224_fx3_v1")
    for other in ("L19", "N19", "L20"):
        r = E.Run(named(other), int(other[1:]), mfiles, dirs, {E.AVCAM_PHYS: av1}, own={LM_AT: lm1})
        r.go()
        ok(not r.bad and bytes(r.phys[E.AVCAM_PHYS]) == av1 and bytes(r.uc.mem_read(LM_AT, lspan)) == lm1 and not r.pwrites and not r.map_writes,
           "%s (the 3840x2560 state) on a camera holding K19: nothing is written" % other)
    # the S-I step shares no site with this state's encoder step: on a camera holding K19 it applies, and K20 then leaves its sites alone
    r = E.Run(named("I19"), 19, mfiles, dirs, {E.AVCAM_PHYS: av1}, own={LM_AT: lm1})
    r.go()
    a, m = bytes(r.phys[E.AVCAM_PHYS]), bytes(r.uc.mem_read(LM_AT, lspan))
    si = sites_of("ogfilesi2560_fx3_v2")
    k = sites_of("ogfile4224_fx3_v1")
    overlap = [hex(o) for b in ("av-cam.bin", "libmpr.so") for o, old, _ in si[b] for o2, old2, _ in k[b] if o < o2 + len(old2) and o2 < o + len(old)]
    ok(not r.bad, "I19 (XAVC S-I at 3840x2560) on a camera holding K19: it %s (sites shared with K19: %s). The 4224x2816 apply does not run it; do not record S-I in this state"
       % ("writes its own sites" if (a, m) != (av1, lm1) else "writes nothing", overlap or "none"))
    avr, lmr = applied(av, "av-cam.bin", "ogfile4224r300_fx3_v1"), applied(lm0, "libmpr.so", "ogfile4224r300_fx3_v1")
    r, t, a, m = mp("K20", avr, lmr)
    ok(not r.bad and a == avr and m == lmr and not r.pwrites and not r.map_writes, "K20 on a camera holding R19: nothing is written (R20 is its put back)")
    r, t, a, m = mp("R20", av1, lm1)
    ok(not r.bad and a == av1 and m == lm1 and not r.pwrites and not r.map_writes, "R20 on a camera holding K19: nothing is written (K20 is its put back)")
    print("ALL PASS (%d)" % n_pass[0] if not fail else "FAILED: %d of %d" % (len(fail), len(fail) + n_pass[0]))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
