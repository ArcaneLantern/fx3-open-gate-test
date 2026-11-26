"""Run the eight built FX3 write libraries in Unicorn against a model camera. Offline; no camera.

  C:/Python313/python.exe -B emu_fx3_write.py

The FX3 7.02 counterpart of helper_s3/emu_s3_write.py (made from it by fixed replacements, 2026-11-24). The libraries are
helper/readcheck.c's levels 5/6, 16/17 and 19/20 built with this camera's tables (build_fx3_write.sh). The harness is the A7 IV one (helper/emu_built.py); the coprocessor model is this file's:
a transfer must be whole 64-byte lines to or from the allocated buffer, and a transfer TOWARDS the coprocessor
may change only bytes of a listed site, and only to that site's stock or new bytes. Anything else fails the run.

Cases, coprocessor (sensor sites + stored record; output-size word):
  apply on stock -> every site new, nothing else changed;  apply again -> nothing to do;  put back -> all stock
  a site holding foreign bytes -> nothing written;  a write that is lost -> everything this run wrote is put back
  the stored record not where the pointers lead -> nothing written;  a guard byte wrong -> nothing written
Cases, main processor (encoder sites): apply, apply again, put back; a guard wrong; a lost write in libmpr.so;
the kernel's view not following a write.

The two rear-screen libraries (S16/S17 = levels 16/17 with lcd32dsq_fx3_v1's 30 words: the 3:2 ratio, the frame tables, the
de-squeeze ratios and the 2.0x crop) run in the same harness, on the words of the loaded coprocessor image. There is no C19/C20.
Safety cases: the A7S III kit's own write libraries (helper_s3, levels 5, 16 with its screen words, and 19) run on an FX3 write nothing.
The playback decoder's two libraries (P29 / P30, readcheck.c levels 29 / 30 with avdec8k_fx3_v1) are run by emu_fx3_playback.py's cases, at the end.
XAVC S-I 4K (I19 / I20: levels 19 / 20 with ogfilesi2560_fx3_v1): after L19, again, put back, L20 leaving it, on stock, after N19, a lost write,
a stale view, each guard.
Since 2026-11-26 (open gate at 25p and 29.97p as well): L5 / L6 carry ogsq_fx3_v2 (v1's cells, drive mode 0x820's, and the stored records of 0x820
and 0x8c0 in NTSC or PAL form, MULTI_REC), L19 / L20 ogfile2560_hs_s_fx3_v3 and I19 / I20 ogfilesi2560_fx3_v2 (both + 29.97p); O5 is the earlier L5
(v1). The cases above run with the new libraries on an NTSC camera; added: the same on a PAL camera, records of mixed systems, O5 (NTSC applies,
PAL refused) and the new L5 / L6 over it, and the new encoder libraries over the previous kit's state (v2 / S-I v1 applied) and back.
"""
import json
import struct
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE.parent / "helper"))
sys.path.insert(0, str(HERE))
import emu_built as E  # noqa: E402
from unicorn import arm64_const as R  # noqa: E402

BASE, CP_HI = 0x108000, 0x10000000
DES = ROOT / "modding/designs"
IMAGER, CTRL, OBJ, CTRL_DRVPARAM = 0x127AB68, 0x1500000, 0x1500800, 0x698
IDS, RECS, REC, INDEX, COUNT = 0xC53790, 0x1FDD574, 0x15C, 12, 40
LM_AT = 0x7F82D15000
RESULT = E.RESULT


def ex(rel):
    return (ROOT / "work/extracted/fx3_702/0700_part_image/dev" / rel).read_bytes()


def design(name):
    return json.loads((DES / f"{name}.json").read_text(encoding="utf8"))


class Mem:
    """Coprocessor memory: the image at 0x108000, zeros elsewhere, with what the model camera adds."""

    def __init__(self, image):
        self.pages, self.image = {}, image

    def page(self, a):
        a &= ~0xFFF
        if a not in self.pages:
            p = bytearray(4096)
            if BASE <= a < BASE + len(self.image):
                chunk = self.image[a - BASE:a - BASE + 4096]
                p[:len(chunk)] = chunk
            self.pages[a] = p
        return self.pages[a]

    def read(self, a, n):
        return bytes(self.page(a + k)[(a + k) & 0xFFF] for k in range(n))

    def write(self, a, data):
        for k, v in enumerate(data):
            self.page(a + k)[(a + k) & 0xFFF] = v

    def snapshot(self):
        return {a: bytes(p) for a, p in self.pages.items()}


def records(og, system="ntsc"):
    """{index: (stock record, design record)}: v1's one record of 0x8c0 (NTSC), or v2's records of each mode in the given system."""
    if "stored_record" in og:
        return {INDEX: (bytes.fromhex(og["stored_record"]["stock"]), bytes.fromhex(og["stored_record"]["design"]))}
    return {v["index"]: (bytes.fromhex(v[system]["stock"]), bytes.fromhex(v[system]["design"])) for v in og["stored_records"].values()}


def camera(image, og, oz, system="ntsc", stock_of=None):
    """stock_of: {index: system} to give a record another system's stock bytes (a case of mixed records)."""
    m = Mem(image)
    m.write(IMAGER, struct.pack("<I", CTRL))
    m.write(CTRL + CTRL_DRVPARAM, struct.pack("<I", OBJ))
    m.write(OBJ, struct.pack("<6I", 0xC5501C, COUNT, IDS, 0, RECS, 0xC53830))
    for i in range(COUNT):
        m.write(RECS + i * REC, bytes([i]) * REC)
    v2 = design("ogsq_fx3_v2")
    for idx, (st, _) in records(v2, system).items():           # every mode the designs know, in the camera's system: as the camera computes them
        m.write(RECS + idx * REC, records(v2, (stock_of or {}).get(idx, system))[idx][0])
    for g in oz["guards"]:
        m.write(int(g["ram_address"], 16), bytes.fromhex(g["bytes"]))
    for s in oz["sites"]:
        m.write(int(s["ram_address"], 16), bytes.fromhex(s["old"]))
    return m


def allowed_sites(og, oz, system="ntsc"):
    """{address: (stock byte, new byte)} for every byte a write may change."""
    out = {}
    for p in og["patches"]:
        a = int(p["addr"], 16)
        for k, (o, n) in enumerate(zip(bytes.fromhex(p["old"]), bytes.fromhex(p["new"]))):
            out[a + k] = (o, n)
    for idx, (st, nw) in records(og, system).items():
        for k in range(REC):
            if st[k] != nw[k]:
                out[RECS + idx * REC + k] = (st[k], nw[k])
    for s in oz["sites"]:
        a = int(s["ram_address"], 16)
        for k, (o, n) in enumerate(zip(bytes.fromhex(s["old"]), bytes.fromhex(s["new"]))):
            out[a + k] = (o, n)
    return out


class Run(E.Run):
    def __init__(self, lib, files, dirs, mem, allowed, lose=None):
        super().__init__(lib, 5, files, dirs, cp=b"")           # level 5: the harness's system-call rules for a coprocessor write level
        self.mem, self.allowed, self.lose, self.n_writes = mem, allowed, lose, 0

    def go(self):
        self.uc.reg_write(R.UC_ARM64_REG_SP, E.STACK - 0x1000)
        self.uc.reg_write(R.UC_ARM64_REG_X30, E.RET)
        self.uc.emu_start(self.ctor, E.RET, count=2_000_000_000)
        if not self.bad and self.uc.reg_read(R.UC_ARM64_REG_PC) != E.RET:
            self.bad = "the constructor did not return"
        return self

    def on_import(self, uc, address, size, _):
        x = lambda n: uc.reg_read(getattr(R, "UC_ARM64_REG_X%d" % n))
        name, ret = self.imports.get(address), 0
        if name == "_Z9dmm_allocjPj":
            uc.mem_write(x(1), struct.pack("<I", E.BUF_HANDLE))
            ret = self.buf
        elif name == "_Z8dmm_freej":
            pass
        elif name == "sen_dma_transfer":
            d, src, dst, n = x(0) & 0xFFFFFFFF, x(1), x(2), x(3) & 0xFFFFFFFF
            cp = src if d == 0 else dst
            self.lib_calls.append(("transfer", d, src, dst, n))
            if d not in (0, 1) or (dst if d == 0 else src) != self.buf or cp & 63 or n & 63 or not 0 < n <= 4096 or cp < BASE or cp + n > CP_HI:
                self.bad = "a transfer that is not whole lines to or from the buffer: dir %d src %#x dst %#x size %d" % (d, src, dst, n)
                uc.emu_stop()
                return
            va = next(v for v, off in self.map_phys.items() if v in self.maps and off <= self.buf < off + self.maps[v]) + self.buf % 4096
            if d == 0:
                uc.mem_write(va, self.mem.read(cp, n))
            else:
                data, now = bytes(uc.mem_read(va, n)), self.mem.read(cp, n)
                for k in range(n):
                    if data[k] != now[k] and data[k] not in self.allowed.get(cp + k, ()):
                        self.bad = "a write that changes %#x to %#x, which is not a listed site's stock or new byte" % (cp + k, data[k])
                        uc.emu_stop()
                        return
                self.n_writes += 1
                if self.lose != self.n_writes:               # lose: this write reports success and nothing arrives
                    self.mem.write(cp, data)
        else:
            self.bad = "call of an unexpected import %r" % name
            uc.emu_stop()
            return
        uc.reg_write(R.UC_ARM64_REG_X0, ret)
        uc.reg_write(R.UC_ARM64_REG_PC, uc.reg_read(R.UC_ARM64_REG_X30))


def main():
    fail = []
    ok = lambda cond, text: (print(("PASS  " if cond else "FAIL  ") + text), fail.append(text) if not cond else None)
    lib = lambda L: (HERE / f"libJit_fx3_L{L}.so").read_bytes()
    og, oz, fl = design("ogsq_fx3_v2"), design("outsz2560_fx3_v1"), design("ogfile2560_hs_s_fx3_v3")
    fl1 = design("ogfile2560_hs_s_fx3_v1")                  # the first kit's encoder side (N19 / N20)
    fl2 = design("ogfile2560_hs_s_fx3_v2")                  # the previous kit's L19 (2026-11-25): 23.98p and 25p
    og1 = design("ogsq_fx3_v1")                             # the previous kit's L5 (now O5): 0x8c0, NTSC record
    image = ex("nflasha8/cpapp-b.bin")
    allowed = allowed_sites(og, oz)
    files = E.tree()
    files["/dev/mem"] = b""
    dirs = {"/tmp_wbshd", "/sys/module/liro/parameters", "/proc/driver/pcie"}

    def state(mem):
        """'stock', 'new', or 'mixed' over the bytes of the two coprocessor designs' sites, by design."""
        out = {}
        for nm, keys in (("og", [a for a in allowed if a < 0x13C0000 or a >= RECS]), ("oz", [a for a in allowed if 0x13C0000 <= a < RECS])):
            vals = [mem.read(a, 1)[0] for a in keys]
            out[nm] = "stock" if all(v == allowed[a][0] for v, a in zip(vals, keys)) else "new" if all(v == allowed[a][1] for v, a in zip(vals, keys)) else "mixed"
        return out

    def others_unchanged(mem, before):
        for a, p in mem.pages.items():
            b = before.get(a, bytes(4096) if not BASE <= a < BASE + len(image) else image[a - BASE:a - BASE + 4096].ljust(4096, b"\0"))
            if any(p[k] != b[k] and (a + k) not in allowed for k in range(4096)):
                return False
        return True

    def go(L, mem, **kw):
        r = Run(lib(L), files, dirs, mem, allowed, **kw).go()
        return r, r.writes.get(RESULT, b"").decode("utf8", "replace")

    # ---- coprocessor: sensor sites and stored record (levels 5, 6)
    mem = camera(image, og, oz)
    before = mem.snapshot()
    r, t = go(5, mem)
    ok(not r.bad and "DONE: all " in t and "sites hold the target bytes (apply)" in t and state(mem)["og"] == "new" and state(mem)["oz"] == "stock" and others_unchanged(mem, before),
       "level 5 on a stock camera: every site and the stored record's design bytes are new, nothing else changed (%d line writes)" % r.n_writes)
    r, t = go(5, mem)
    ok(not r.bad and "NOTHING TO DO" in t and r.n_writes == 0, "level 5 again: nothing to do, no write")
    r, t = go(6, mem)
    ok(not r.bad and "(put back)" in t and "DONE" in t and state(mem) == {"og": "stock", "oz": "stock"} and mem.snapshot() == {a: before.get(a, mem.snapshot()[a]) for a in mem.pages},
       "level 6: everything is stock again, byte for byte")
    mem = camera(image, og, oz)
    a0 = int(og["patches"][0]["addr"], 16)
    mem.write(a0, b"\x55")
    r, t = go(5, mem)
    ok(not r.bad and r.n_writes == 0 and "holds neither the stock nor the new bytes; nothing is written" in t, "level 5 with one site holding other bytes: nothing is written")
    for lose in (1, 9, 21):
        mem = camera(image, og, oz)
        before = mem.snapshot()
        r, t = go(5, mem, lose=lose)
        ok(not r.bad and "NOT DONE: a step failed; every site this run touched was put back" in t and state(mem)["og"] == "stock" and others_unchanged(mem, before),
           "level 5 with line write %d lost: reported, and every site put back" % lose)
    mem = camera(image, og, oz)
    mem.write(OBJ + 0x10, struct.pack("<I", 0))
    r, t = go(5, mem)
    ok(not r.bad and r.n_writes == 0 and "stored record was not found" in t, "level 5 with a null records pointer: nothing is written")
    mem = camera(image, og, oz)
    mem.write(RECS + INDEX * REC + 6, b"\x07")
    r, t = go(5, mem)
    ok(not r.bad and r.n_writes == 0 and "nothing is written" in t, "level 5 with the stored record's ratio byte not stock: nothing is written")

    # ---- 2026-11-26: the new L5 / L6 (ogsq_fx3_v2) in PAL, with mixed records, and the earlier L5 (O5, ogsq_fx3_v1)
    def go_with(name, mem, allow, **kw):
        r = Run((HERE / f"libJit_fx3_{name}.so").read_bytes(), files, dirs, mem, allow, **kw).go()
        return r, r.writes.get(RESULT, b"").decode("utf8", "replace")

    def holds(mem, og_, system, which):
        """every site byte of the design (cells, records, stored records of that system) holds its stock (0) or new (1) byte"""
        al = allowed_sites(og_, {"sites": []}, system)
        return all(mem.read(a, 1)[0] == v[which] for a, v in al.items())
    ok(set((int(p["addr"], 16), p["old"], p["new"]) for p in og1["patches"]) <= set((int(p["addr"], 16), p["old"], p["new"]) for p in og["patches"])
       and len(og["patches"]) == len(og1["patches"]) + 19, "v2's sites are v1's 21 and 19 more on drive mode 0x820")
    mem = camera(image, og, oz)
    r, t = go(5, mem)
    ok("the stored records are the NTSC (60 Hz) variant" in t and holds(mem, og, "ntsc", 1), "L5 on an NTSC camera: it reports the NTSC records and both modes' records are new")
    pal_allowed = allowed_sites(og, oz, "pal")
    mem = camera(image, og, oz, "pal")
    before = mem.snapshot()
    r, t = go_with("L5", mem, pal_allowed)
    ok(not r.bad and "DONE: all " in t and "the stored records are the PAL (50 Hz) variant" in t and holds(mem, og, "pal", 1),
       "L5 on a PAL camera: every site and both modes' PAL records are new (%d line writes)" % r.n_writes)
    r, t = go_with("L5", mem, pal_allowed)
    ok(not r.bad and "NOTHING TO DO" in t and r.n_writes == 0, "L5 again on the PAL camera: nothing to do")
    r, t = go_with("L6", mem, pal_allowed)
    ok(not r.bad and "DONE" in t and holds(mem, og, "pal", 0) and all(mem.read(a, 4096) == p for a, p in before.items()), "L6 on the PAL camera: stock again, byte for byte")
    for stock_of, what in (({10: "pal"}, "0x820's PAL and 0x8c0's NTSC"), ({12: "pal"}, "0x820's NTSC and 0x8c0's PAL")):
        mem = camera(image, og, oz, "ntsc", stock_of)
        r, t = go_with("L5", mem, allowed_sites(og, oz, "ntsc"))
        ok(not r.bad and r.n_writes == 0 and "hold neither timing variant" in t, "L5 with %s stock records (no one system fits both): nothing is written" % what)
    mem = camera(image, og, oz)
    mem.write(RECS + 10 * REC + 6, b"\x07")
    r, t = go(5, mem)
    ok(not r.bad and r.n_writes == 0 and "nothing is written" in t, "L5 with 0x820's record not stock (ratio byte): nothing is written")
    for lose in (2, 25, 41):
        mem = camera(image, og, oz, "pal")
        before = mem.snapshot()
        r, t = go_with("L5", mem, pal_allowed, lose=lose)
        ok(not r.bad and "NOT DONE: a step failed; every site this run touched was put back" in t and holds(mem, og, "pal", 0)
           and all(mem.read(a, 4096) == p for a, p in before.items()), "L5 on the PAL camera with line write %d lost: every site put back" % lose)
    # O5 = the previous kit's L5 (v1): NTSC applies v1's sites; on PAL its record holds neither (the reason v2 carries both systems)
    o5_allowed = allowed_sites(og1, oz, "ntsc")
    mem = camera(image, og, oz)
    before = mem.snapshot()
    r, t = go_with("O5", mem, o5_allowed)
    ok(not r.bad and "DONE: all " in t and holds(mem, og1, "ntsc", 1) and not holds(mem, og, "ntsc", 1), "O5 (--only-24p) on an NTSC camera: v1's sites and 0x8c0's record, not 0x820's")
    r, t = go(5, mem)
    ok(not r.bad and "DONE: all " in t and holds(mem, og, "ntsc", 1), "the new L5 over O5: adds 0x820's cells and record, the rest already in place")
    r, t = go(6, mem)
    ok(not r.bad and "DONE" in t and holds(mem, og, "ntsc", 0) and all(mem.read(a, 4096) == p for a, p in before.items()), "L6 after both: stock again, byte for byte")
    r, t = go_with("O5", mem, o5_allowed)
    r2, t2 = go(6, mem)
    ok(not r.bad and not r2.bad and "DONE" in t2 and holds(mem, og, "ntsc", 0), "L6 after O5 alone: stock again (the put back of either sensor step is L6)")
    mem = camera(image, og, oz, "pal")
    r, t = go_with("O5", mem, o5_allowed)
    ok(not r.bad and r.n_writes == 0 and "nothing is written" in t, "O5 on a PAL camera: 0x8c0's record holds neither of its NTSC bytes, nothing is written")

    # ---- the stored record as the tester's A7S III held it (2026-11-21): run-time bytes differ from the emulated record, the design bytes do not.
    # The FX3's stock record of 0x8c0 is byte-identical to the A7S III's (build/build_og_fx3.py), so that camera's record stands in for an FX3's.
    ev = ROOT / "evidence/a7s3/tester_2026-11-21"
    seen = []
    for run in ("CT6_20261121T132137Z_s3_check", "CT6_20261121T132551Z_s3_dump", "CT6_20261121T134754Z_s3_dump"):      # stills, stills, after a 4K 24p recording
        p = ev / run / "readcheck_result.txt"
        if p.is_file():
            line = next((ln for ln in p.read_text(encoding="utf8", errors="replace").split("\n") if ln.startswith("other stored_record ")), None)
            if line:
                seen.append((run, bytes.fromhex(line.split(" ")[2])))
    for run, record in seen:
        mem = camera(image, og, oz)
        mem.write(RECS + INDEX * REC, record)
        before = mem.snapshot()
        r, t = go(5, mem)
        got = mem.read(RECS + INDEX * REC, REC)
        want = bytearray(record)
        for a, (o, n) in allowed.items():
            if RECS + INDEX * REC <= a < RECS + (INDEX + 1) * REC:
                want[a - RECS - INDEX * REC] = n
        ok(not r.bad and "DONE: all " in t and got == bytes(want) and others_unchanged(mem, before),
           "level 5 with the stored record the camera held in %s: applied, and its run-time bytes are left as they were" % run.split("_")[-1])
        r, t = go(6, mem)
        ok(not r.bad and mem.read(RECS + INDEX * REC, REC) == record, "level 6 after it: the camera's record is back, byte for byte")
    if not seen:
        print("NOTE  the tester's results are not here (evidence/a7s3/tester_2026-11-21): the camera-record cases were skipped")

    # ---- coprocessor: the output-size word (levels 16, 17)
    mem = camera(image, og, oz)
    before = mem.snapshot()
    r, t = go(16, mem)
    ok(not r.bad and state(mem) == {"og": "stock", "oz": "new"} and others_unchanged(mem, before) and "!!" not in t.split("== level")[-1], "level 16 on a stock camera: the size word is new, nothing else changed")
    r, t = go(17, mem)
    ok(not r.bad and state(mem) == {"og": "stock", "oz": "stock"}, "level 17: the size word is stock again")
    mem = camera(image, og, oz)
    mem.write(int(oz["guards"][0]["ram_address"], 16), bytes(8))
    r, t = go(16, mem)
    ok(not r.bad and r.n_writes == 0 and state(mem)["oz"] == "stock", "level 16 with the size table not filled (guard zero): nothing is written")

    # ---- main processor: encoder sites (levels 19, 20), with the harness's own model of /dev/mem and /proc/self/mem
    av, lm = ex("nflasha3/av-cam.bin"), ex("nflasha15/lib/libmpr.so")
    av = bytes([0x5A]) * 0x1000 + av[0x1000:]            # as on a camera: the first page is not the file's (2026-11-21); no level may depend on it
    phoff, phentsize, phnum = struct.unpack_from("<Q", lm, 0x20)[0], *struct.unpack_from("<HH", lm, 0x36)
    span = next(struct.unpack_from("<IIQQQQQQ", lm, phoff + k * phentsize) for k in range(phnum) if struct.unpack_from("<I", lm, phoff + k * phentsize)[0] == 1)[5]
    lspan = (span + 0xFFF) & ~0xFFF
    lm0 = lm[:span].ljust(lspan, b"\0")
    mfiles = dict(files)
    mfiles["/proc/self/mem"] = b""
    # the list of mappings in the shape the tester's A7S III gave (2026-11-21): im.elf first, libmpr.so as r-xp from offset 0, then its gap and data
    mfiles["/proc/self/maps"] = (b"00400000-00409000 r-xp 00000000 fc:8f 81970                              /usr/bin/im.elf\n"
                                 b"7f5c1e3000-7f6120c000 r-xp 00000000 fc:8f 55369                          /usr/lib/appFw.so\n"
                                 + b"%x-%x r-xp 00000000 fc:8f 55354                          /usr/lib/libmpr.so\n" % (LM_AT, LM_AT + lspan)
                                 + b"%x-%x ---p %08x fc:8f 55354                          /usr/lib/libmpr.so\n" % (LM_AT + lspan, LM_AT + lspan + 0x10000, lspan)
                                 + b"%x-%x r--p %08x fc:8f 55354                          /usr/lib/libmpr.so\n" % (LM_AT + lspan + 0x10000, LM_AT + lspan + 0x19000, lspan)
                                 + b"7f8b936000-7f8b991000 r-xp 00000000 fc:8f 55344                          /usr/lib/libsencore.so\n")
    sites = {"av-cam.bin": [], "libmpr.so": []}
    for p in fl["patches"]:
        sites[p["binary"]].append((int(p["file_off"], 16), bytes.fromhex(p["old"]), bytes.fromhex(p["new"])))

    def applied(blob, which):
        b = bytearray(blob)
        for o, old, new in sites[which]:
            b[o:o + len(new)] = new
        return bytes(b)

    def mp(L, av_mem, lm_mem, **wrong):
        r = (E.Run(lib(L), L, mfiles, dirs, {E.AVCAM_PHYS: av_mem}, own={LM_AT: lm_mem}) if isinstance(L, int) else
             E.Run((HERE / f"libJit_fx3_{L}.so").read_bytes(), int(L[1:]), mfiles, dirs, {E.AVCAM_PHYS: av_mem}, own={LM_AT: lm_mem}))
        r.kview_fail = wrong.get("kview_fail", False)
        r.stale = {E.AVCAM_PHYS + o for o in wrong.get("stale", ())}
        r.pwrite_lost = {LM_AT + o for o in wrong.get("pwrite_lost", ())}
        r.go()
        return r, r.writes.get(RESULT, b"").decode("utf8", "replace"), bytes(r.phys[E.AVCAM_PHYS]), bytes(r.uc.mem_read(LM_AT, lspan))

    av1, lm1 = applied(av, "av-cam.bin"), applied(lm0, "libmpr.so")
    r, t, a, m = mp(19, av, lm0)
    ok(not r.bad and a == av1 and m == lm1 and "DONE" in t, "level 19 on a stock camera: %d + %d sites new, every other byte of both files' memory unchanged"
       % (len(sites["av-cam.bin"]), len(sites["libmpr.so"])))
    r, t, a, m = mp(19, av1, lm1)
    ok(not r.bad and a == av1 and m == lm1 and not r.pwrites and not r.map_writes, "level 19 again: no write")
    r, t, a, m = mp(20, av1, lm1)
    ok(not r.bad and a == av and m == lm0 and "DONE" in t, "level 20: both are stock again, byte for byte")
    bad_av = bytearray(av)
    bad_av[0x395068 + 0x20] ^= 1
    r, t, a, m = mp(19, bytes(bad_av), lm0)
    ok(not r.bad and a == bytes(bad_av) and m == lm0 and not r.pwrites and not r.map_writes, "level 19 with a guard of av-cam.bin wrong: nothing is written")
    r, t, a, m = mp(19, av, lm0, pwrite_lost=[sites["libmpr.so"][0][0]])
    ok(not r.bad and a == av and m == lm0 and "NOT DONE: a step failed; every site this run touched was put back" in t, "level 19 with a libmpr.so write lost: everything put back")
    r, t, a, m = mp(19, av, lm0, stale=[sites["av-cam.bin"][3][0]])
    ok(not r.bad and a == av and m == lm0 and "NOT DONE: a step failed; every site this run touched was put back" in t, "level 19 with the kernel's view not following a write: everything put back")
    # ---- the MP4 header heights (2026-11-25): L19 = ogfile2560_hs_s_fx3_v2 holds two code words more than the first kit's N19 (v1)
    code = [(int(q["file_off"], 16), bytes.fromhex(q["old"]), bytes.fromhex(q["new"])) for q in fl["patches"] if q["code"]]
    ok(len(code) == 2 and all(o[2] == 0x81 and n[2] == 0x81 for _, o, n in code), "v2's two code sites are the two movz w6 heights (2160 -> 2560)")
    sites1 = {"av-cam.bin": [], "libmpr.so": []}
    for q in fl1["patches"]:
        sites1[q["binary"]].append((int(q["file_off"], 16), bytes.fromhex(q["old"]), bytes.fromhex(q["new"])))

    def applied1(blob, which):
        b = bytearray(blob)
        for o, old, new in sites1[which]:
            b[o:o + len(new)] = new
        return bytes(b)
    av1n, lm1n = applied1(av, "av-cam.bin"), applied1(lm0, "libmpr.so")
    s2 = {(q["binary"], q["file_off"], q["old"], q["new"]) for q in fl2["patches"]}
    s3 = {(q["binary"], q["file_off"], q["old"], q["new"]) for q in fl["patches"]}
    added = s3 - s2
    ok(s2 <= s3 and added and all(b == "av-cam.bin" for b, *_ in added), "v3 = v2 + %d av-cam.bin sites (the 29.97p descriptors and profiles); libmpr.so as v2" % len(added))
    av_v2 = bytearray(av)
    for b, o, _, n in s2:
        if b == "av-cam.bin":
            av_v2[int(o, 16):int(o, 16) + len(n) // 2] = bytes.fromhex(n)
    av_v2 = bytes(av_v2)
    ok(applied1(av, "av-cam.bin") == av_v2, "v1 and v2 hold the same av-cam.bin sites (they differ only in libmpr.so's two height words)")
    r, t, a, m = mp(19, av_v2, lm1)
    ok(not r.bad and a == av1 and m == lm1 and "DONE" in t and not r.pwrites,
       "L19 on a camera holding the previous kit's L19 (v2): only the 29.97p sites are written, no libmpr.so write")
    r, t, a, m = mp(20, av_v2, lm1)
    ok(not r.bad and a == av and m == lm0 and "DONE" in t, "L20 on a camera holding the previous kit's L19 (v2): stock again")
    r, t, a, m = mp("N19", av, lm0)
    ok(not r.bad and a == av1n and m == lm1n and "DONE" in t, "N19 (the first kit's encoder side) on a stock camera: v1's sites, the heights stay stock")
    r, t, a, m = mp("N20", av1n, lm1n)
    ok(not r.bad and a == av and m == lm0 and "DONE" in t, "N20: stock again, byte for byte")
    r, t, a, m = mp(19, av1n, lm1n)
    ok(not r.bad and a == av1 and m == lm1 and "DONE" in t and len(r.pwrites) <= 2,
       "L19 on a camera holding the first kit's encoder side: the 29.97p sites and the two height words are written (%d libmpr.so writes)" % len(r.pwrites))
    r, t, a, m = mp(20, av1n, lm1n)
    ok(not r.bad and a == av and m == lm0 and "DONE" in t, "L20 on a camera holding the first kit's encoder side: stock again")
    # Why the kit's put back is always L20 and N20 is not shipped: v1's put back does not know the two height words, so on a camera holding v2 it
    # puts back everything else and leaves the headers saying 2560 for stock 2160 recordings
    r, t, a, m = mp("N20", av1, lm1)
    left = bytearray(lm0)
    for o, _, new in code:
        left[o:o + 4] = new
    left_av = bytearray(av)
    for b, o, _, n in added:
        left_av[int(o, 16):int(o, 16) + len(n) // 2] = bytes.fromhex(n)
    ok(not r.bad and a == bytes(left_av) and m == bytes(left) and "DONE" in t,
       "N20 (not shipped) on a camera holding v3: leaves the two heights and the 29.97p sites, so the kit's put back is always L20")
    for g in [int(x["file_off"], 16) for x in fl["libmpr_code_guards"][0]["guards"]]:
        bad_lm = bytearray(lm0)
        bad_lm[g] ^= 1
        r, t, a, m = mp(19, av, bytes(bad_lm))
        if r.bad or a != av or m != bytes(bad_lm) or r.pwrites or r.map_writes:
            ok(False, "L19 with the code guard at %#x wrong: nothing is written" % g)
            break
    else:
        ok(True, "L19 with any one of the %d instructions around the heights wrong: nothing is written" % len(fl["libmpr_code_guards"][0]["guards"]))
    # ---- XAVC S-I 4K (2026-11-25): I19 / I20 = levels 19 / 20 with ogfilesi2560_fx3_v1, one more step after L19 in the same apply
    fs, fs1 = design("ogfilesi2560_fx3_v2"), design("ogfilesi2560_fx3_v1")
    si = {"av-cam.bin": [], "libmpr.so": []}
    for q in fs["patches"]:
        si[q["binary"]].append((int(q["file_off"], 16), bytes.fromhex(q["old"]), bytes.fromhex(q["new"])))

    def with_si(blob, which):
        b = bytearray(blob)
        for o, old, new in si[which]:
            b[o:o + len(new)] = new
        return bytes(b)
    ok(not ({o for o, _, _ in si["av-cam.bin"]} & {o for o, _, _ in sites["av-cam.bin"]}) and not ({o for o, _, _ in si["libmpr.so"]} & {o for o, _, _ in sites["libmpr.so"]}),
       "the S-I step's %d sites are none of L19's" % (len(si["av-cam.bin"]) + len(si["libmpr.so"])))
    av2, lm2 = with_si(av1, "av-cam.bin"), with_si(lm1, "libmpr.so")
    r, t, a, m = mp("I19", av1, lm1)
    ok(not r.bad and a == av2 and m == lm2 and "DONE" in t, "I19 after L19 (the apply's order): the %d + %d S-I sites new, L19's and every other byte as they were"
       % (len(si["av-cam.bin"]), len(si["libmpr.so"])))
    # the previous kit's I19 (S-I v1, 23.98p / 25p) applied over the previous kit's L19 (v2): the new I19 adds the two 29.97p descriptors
    av_old, lm_old = bytearray(av_v2), bytearray(lm1)
    for q in fs1["patches"]:
        tgt = av_old if q["binary"] == "av-cam.bin" else lm_old
        tgt[int(q["file_off"], 16):int(q["file_off"], 16) + len(q["new"]) // 2] = bytes.fromhex(q["new"])
    av_old, lm_old = bytes(av_old), bytes(lm_old)
    r, t, a, m = mp(19, av_old, lm_old)
    r2, t2, a2, m2 = mp("I19", a, m)
    ok(not r.bad and not r2.bad and a2 == av2 and m2 == lm2 and "DONE" in t and "DONE" in t2 and not r2.pwrites,
       "L19 then I19 on a camera holding the whole previous kit (L19 v2 + I19 v1): the 29.97p sites only; the result is the new kit's state")
    r, t, a, m = mp("I20", av_old, lm_old)
    ok(not r.bad and a == av_v2 and m == lm1 and "DONE" in t, "I20 on a camera holding the previous kit's I19: back to its L19 state")
    r, t, a, m = mp("I19", av2, lm2)
    ok(not r.bad and a == av2 and m == lm2 and not r.pwrites and not r.map_writes and "NOTHING TO DO" in t, "I19 again: nothing to do, no write")
    r, t, a, m = mp(19, av2, lm2)
    ok(not r.bad and a == av2 and m == lm2 and not r.pwrites and not r.map_writes, "L19 on a camera holding L19 and I19 (an apply run again): no write")
    r, t, a, m = mp("I20", av2, lm2)
    ok(not r.bad and a == av1 and m == lm1 and "DONE" in t, "I20 (the put back's first step): the camera holds exactly L19's state again")
    r, t, a, m = mp(20, av2, lm2)
    ok(not r.bad and a == with_si(av, "av-cam.bin") and m == with_si(lm0, "libmpr.so") and "DONE" in t,
       "L20 on a camera holding both: puts back L19's sites only, the S-I sites stay (I20 is their put back)")
    r, t, a, m = mp("I19", av, lm0)
    ok(not r.bad and a == with_si(av, "av-cam.bin") and m == with_si(lm0, "libmpr.so") and "DONE" in t, "I19 on a stock camera (without L19): its own sites only")
    r, t, a, m = mp("I19", av1n, lm1n)
    ok(not r.bad and a == with_si(av1n, "av-cam.bin") and m == with_si(lm1n, "libmpr.so") and "DONE" in t, "I19 after the first kit's encoder step (N19, --no-meta)")
    r, t, a, m = mp("I19", av1, lm1, pwrite_lost=[si["libmpr.so"][0][0]])
    ok(not r.bad and a == av1 and m == lm1 and "NOT DONE: a step failed; every site this run touched was put back" in t, "I19 with its libmpr.so write lost: everything it wrote put back")
    r, t, a, m = mp("I19", av1, lm1, stale=[si["av-cam.bin"][5][0]])
    ok(not r.bad and a == av1 and m == lm1 and "NOT DONE" in t, "I19 with the kernel's view not following a write: everything it wrote put back")
    fsg = [(int(x["descriptor"]) * 0x90 + 0x395108 + 0x28) for x in fs["descriptors"]]
    for g in fsg + [0x395088, 0x3933AC]:
        bad_av = bytearray(av1)
        bad_av[g] ^= 1
        r, t, a, m = mp("I19", bytes(bad_av), lm1)
        if r.bad or a != bytes(bad_av) or m != lm1 or r.pwrites or r.map_writes:
            ok(False, "I19 with the guard at %#x wrong: nothing is written" % g)
            break
    else:
        ok(True, "I19 with any one of its %d av-cam.bin guards wrong (the %d profile keys, the 4K unit row, clip row 5): nothing is written" % (len(fsg) + 2, len(fsg)))
    bad_lm = bytearray(lm1)
    bad_lm[si["libmpr.so"][0][0] - 4] ^= 1
    r, t, a, m = mp("I19", av1, bytes(bad_lm))
    ok(not r.bad and a == av1 and m == bytes(bad_lm) and not r.pwrites and not r.map_writes, "I19 with comb row 9's width not 3840: nothing is written")

    # ---- rear screen and de-squeeze, coprocessor words inside the loaded image (S16, S17: lcd32dsq_fx3_v1)
    named = lambda n: (HERE / f"libJit_fx3_{n}.so").read_bytes()
    lf = design("lcd32dsq_fx3_v1")
    lf_allowed = {}
    for st in lf["sites"]:
        a0 = int(st["ram_address"], 16)
        for k, (o, n) in enumerate(zip(bytes.fromhex(st["old"]), bytes.fromhex(st["new"]))):
            lf_allowed[a0 + k] = (o, n)

    def go_s(n, mem, **kw):
        r = Run(named(n), files, dirs, mem, lf_allowed, **kw).go()
        return r, r.writes.get(RESULT, b"").decode("utf8", "replace")

    def lf_state(mem):
        vals = [(mem.read(a, 1)[0], pair) for a, pair in lf_allowed.items()]
        return "stock" if all(v == pr[0] for v, pr in vals) else "new" if all(v == pr[1] for v, pr in vals) else "mixed"

    def image_but(mem, addrs):
        """Every byte the model holds equals the image's, except at the given addresses."""
        for a, pg in mem.pages.items():
            b = image[a - BASE:a - BASE + 4096].ljust(4096, b"\0") if BASE <= a < BASE + len(image) else bytes(4096)
            if any(pg[k] != b[k] and (a + k) not in addrs for k in range(4096)):
                return False
        return True

    mem = Mem(image)
    r, t = go_s("S16", mem)
    ok(not r.bad and "DONE: every site holds the target bytes (apply)" in t and lf_state(mem) == "new" and image_but(mem, lf_allowed) and r.n_writes == len(lf["sites"]),
       "S16 on the stock image: the %d words are new, every other byte is the image's (%d line writes)" % (len(lf["sites"]), r.n_writes))
    r, t = go_s("S16", mem)
    ok(not r.bad and "NOTHING TO DO" in t and r.n_writes == 0, "S16 again: nothing to do, no write")
    r, t = go_s("S17", mem)
    ok(not r.bad and "(put back)" in t and "DONE" in t and lf_state(mem) == "stock" and image_but(mem, ()), "S17: the image again, byte for byte")
    for g in lf["guards"]:
        mem = Mem(image)
        ga = int(g["ram_address"], 16)
        mem.write(ga, bytes([mem.read(ga, 1)[0] ^ 1]))
        r, t = go_s("S16", mem)
        if r.bad or r.n_writes or "are not as expected; nothing is written" not in t:
            ok(False, "S16 with the guard at %#x wrong: nothing is written" % ga)
            break
    else:
        ok(True, "S16 with any one of the %d guards wrong: nothing is written" % len(lf["guards"]))
    mem = Mem(image)
    mem.write(int(lf["sites"][3]["ram_address"], 16), b"\x02\x00\x00\x00")
    r, t = go_s("S16", mem)
    ok(not r.bad and r.n_writes == 0 and "holds neither the earlier nor the new bytes; nothing is written" in t, "S16 with one word holding other bytes: nothing is written")
    for lose in (1, 2, 8, 14, 30):
        mem = Mem(image)
        r, t = go_s("S16", mem, lose=lose)
        ok(not r.bad and "NOT DONE: a step failed; every site this run touched was put back" in t and lf_state(mem) == "stock" and image_but(mem, ()),
           "S16 with line write %d lost: reported, and every word put back" % lose)

    # ---- safety: the A7S III kit's write libraries on an FX3 write nothing (an FX3 owner might run that kit; its apply also needs a READY
    # A7S III check, which an FX3 never gives: helper_fx3/emu_fx3.py). Any write the model sees fails the case (no byte is allowed).
    s3lib = lambda n: (HERE.parent / "helper_s3" / f"libJit_s3_{n}.so").read_bytes()
    if (HERE.parent / "helper_s3" / "libJit_s3_L5.so").is_file():
        mem = camera(image, og, oz)
        mem.write(0x12A41F0, struct.pack("<I", CTRL))     # the worst case: the A7S III's sensor-object address leads to the FX3's real object
        before = mem.snapshot()
        r = Run(s3lib("L5"), files, dirs, mem, {}).go()
        t = r.writes.get(RESULT, b"").decode("utf8", "replace")
        fresh = lambda a: before.get(a, image[a - BASE:a - BASE + 4096].ljust(4096, b"\0") if BASE <= a < BASE + len(image) else bytes(4096))
        same = all(bytes(p) == fresh(a) for a, p in mem.pages.items())          # pages a read brought into the model hold what they held
        ok(not r.bad and r.n_writes == 0 and "holds neither the stock nor the new bytes; nothing is written" in t and same,
           "the A7S III kit's L5 on an FX3 (even with its pointer chain leading to the FX3's object): its first site holds other bytes, nothing is written")
        mem = Mem(image)
        r = Run(s3lib("S16"), files, dirs, mem, {}).go()
        t = r.writes.get(RESULT, b"").decode("utf8", "replace")
        ok(not r.bad and r.n_writes == 0 and "nothing is written" in t and image_but(mem, ()), "the A7S III kit's S16 on an FX3: nothing is written")
        r = E.Run(s3lib("L19"), 19, mfiles, dirs, {E.AVCAM_PHYS: av}, own={LM_AT: lm0})
        r.go()
        t = r.writes.get(RESULT, b"").decode("utf8", "replace")
        ok(not r.bad and bytes(r.phys[E.AVCAM_PHYS]) == av and bytes(r.uc.mem_read(LM_AT, lspan)) == lm0 and not r.pwrites and not r.map_writes,
           "the A7S III kit's L19 on an FX3: nothing is written in av-cam.bin or libmpr.so")
    else:
        print("NOTE  helper_s3's libraries are not here: the safety cases were skipped")
    # ---- the playback decoder (P29 / P30 = levels 29 / 30 with avdec8k_fx3_v1: av-cam.bin code and data, with the instruction caches)
    import emu_fx3_playback
    emu_fx3_playback.cases(ok)
    print("ALL PASS" if not fail else "FAILED: %d" % len(fail))
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
