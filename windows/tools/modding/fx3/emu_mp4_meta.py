"""The MP4 writer's size code (libmpr.so 6.02) run in Unicorn: stock, and with the sites of build/mp4_meta_sites.py for 3840x2560 and 5760x3840.

For the four formats of the open-gate states (combs 0, 2 AVC; 5, 7 HEVC), 23.98p and 25p, and every bit-rate index of the request:
  0x222b18  the track config (what tkhd, stsd and PROF are written from): width +0x2a, height +0x28
  0x2240cc  the stsd entry set-up (returns 0, or 2 for a width it does not know)
  0x225db8  the PROF video entry (returns 0, or 3 when its profile id or pixel aspect lookup fails); its fields: width, height, profile id,
            pixel aspect
It shows that a 5760-wide config fails 0x2240cc and 0x225db8 with only the size changed, and that the full site list passes, giving the same
profile ids and pixel aspect as the stock 3840x2160 file. Writes evidence/pipeline/mp4_meta_emu.json.
Run with the Python that has Unicorn:  C:\\Python313\\python.exe -B build/emu_mp4_meta.py
"""
import json
import struct
import sys
from pathlib import Path

from unicorn import Uc, UcError, UC_ARCH_ARM64, UC_MODE_ARM
from unicorn import arm64_const as R

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import locate_file  # noqa: E402
import mp4_meta_sites as M  # noqa: E402

IMG_SPAN = 0x2EA000
# the writer's functions per build: the A7 IV 6.02's, and the FX3 7.02's (the same code relinked; build/mp4_meta_sites.py OTHER_BUILDS), with the
# span of each libmpr.so's first loadable segment
FUNCS = {"a7iv_602": {"config": 0x222B18, "stsd": 0x2240CC, "prof": 0x225DB8, "span": 0x2EA000},
         "fx3_702": {"config": 0x21FEC4, "stsd": 0x221464, "prof": 0x223110, "span": 0x2E2000}}
OBJ, REQ, OUT, STACK, RET = 0x10000000, 0x10001000, 0x10002000, 0x10100000, 0x10200000


class Lib:
    def __init__(self, img, build="a7iv_602"):
        self.f = FUNCS[build]
        self.uc = Uc(UC_ARCH_ARM64, UC_MODE_ARM)
        self.uc.mem_map(0, self.f["span"])
        self.uc.mem_write(0, img[:self.f["span"]])
        self.uc.mem_map(OBJ, 0x10000)
        self.uc.mem_map(STACK - 0x10000, 0x20000)
        self.uc.mem_map(RET, 0x1000)
        self.uc.reg_write(R.UC_ARM64_REG_CPACR_EL1, 3 << 20)

    def call(self, fn, *args):
        for k, v in enumerate(args):
            self.uc.reg_write(getattr(R, f"UC_ARM64_REG_X{k}"), v)
        self.uc.reg_write(R.UC_ARM64_REG_SP, STACK)
        self.uc.reg_write(R.UC_ARM64_REG_LR, RET)
        self.uc.emu_start(fn, RET, count=20000)
        return self.uc.reg_read(R.UC_ARM64_REG_X0) & 0xFFFFFFFF

    def config(self, comb, rate_code, rate_index):
        self.uc.mem_write(OBJ, bytes(0x200))
        req = bytearray(0x40)
        struct.pack_into("<6I", req, 0xC, comb, 1, rate_index, rate_code, 1, 2)
        self.uc.mem_write(REQ, bytes(req))
        ret = self.call(self.f["config"], OBJ, REQ)
        return ret, bytes(self.uc.mem_read(OBJ + 0x18, 0x70))

    def stsd(self, cfg):
        self.uc.mem_write(OBJ + 0x400, cfg)
        self.uc.mem_write(OUT, bytes(0x40))
        ret = self.call(self.f["stsd"], 0, 0, OBJ + 0x400, 0, 0, OUT)
        out = bytes(self.uc.mem_read(OUT, 0x14))
        return ret, struct.unpack_from("<HH", out, 8)          # width, height of the entry

    def prof(self, cfg):
        self.uc.mem_write(OBJ + 0x400, cfg)
        self.uc.mem_write(OUT, bytes(0x40))
        ret = self.call(self.f["prof"], 0, OBJ + 0x400, OUT)
        out = bytes(self.uc.mem_read(OUT, 0x28))
        return ret, {"width": struct.unpack_from("<H", out, 0x20)[0], "height": struct.unpack_from("<H", out, 0x22)[0],
                     "profile_id": hex(struct.unpack_from("<I", out, 8)[0]), "pixel_aspect": list(struct.unpack_from("<HH", out, 0x24))}


def patched(img, site_list):
    b = bytearray(img)
    for a, new, *_ in site_list:
        b[a:a + 4] = new
    return bytes(b)


def main():
    lm = locate_file.locate("a7iv_602", "libmpr.so").read_bytes()
    variants = {"stock": lm,
                "5760x3840 sizes only": patched(lm, [s for s in M.sites(5760, 3840) if s[0] in {v[0] for v in M.SIZE_SITES.values()}]),
                "3840x2560 (design)": patched(lm, M.sites(3840, 2560)), "5760x3840 (design)": patched(lm, M.sites(5760, 3840))}
    for n in (2560, 3840):
        M.check(lm, M.sites(*((3840, 2560) if n == 2560 else (5760, 3840))))
    libs = {k: Lib(v) for k, v in variants.items()}
    rows = []
    for comb in (0, 2, 5, 7):
        for rate_code in (0, 2):
            for rate_index in range(2, 0x36):
                row = {"comb": comb, "codec": "HEVC" if comb in (5, 7) else "AVC", "rate_code": rate_code, "rate_index": rate_index}
                for name, lib in libs.items():
                    try:
                        r, cfg = lib.config(comb, rate_code, rate_index)
                        w, h = struct.unpack_from("<HH", cfg, 0x2A)[0], struct.unpack_from("<H", cfg, 0x28)[0]
                        rs, sz = lib.stsd(cfg)
                        rp, pf = lib.prof(cfg)
                        row[name] = {"config": [w, h], "stsd": [rs, list(sz)], "prof": [rp, pf]}
                    except UcError as e:
                        row[name] = {"error": str(e)}
                rows.append(row)
    # the cases a stock camera records: the stock file at 3840x2160 passes both (bit-rate indices for which it does)
    real = [r for r in rows if r["stock"].get("stsd", [1])[0] == 0 and r["stock"].get("prof", [1])[0] == 0]
    assert real, "no request the stock code accepts"
    for r in real:
        s = r["stock"]
        assert s["config"] == [3840, 2160]
        a = r["3840x2560 (design)"]
        assert a["config"] == [3840, 2560] and a["stsd"] == [0, [3840, 2560]] and a["prof"][0] == 0 and a["prof"][1]["profile_id"] == s["prof"][1]["profile_id"]
        b = r["5760x3840 sizes only"]
        assert b["config"] == [5760, 3840] and (b["stsd"][0] != 0 or b["prof"][0] != 0)
        c = r["5760x3840 (design)"]
        assert c["config"] == [5760, 3840] and c["stsd"] == [0, [5760, 3840]] and c["prof"][0] == 0, (r["comb"], r["rate_index"], c)
        assert c["prof"][1]["profile_id"] == s["prof"][1]["profile_id"] and c["prof"][1]["pixel_aspect"] == [1, 1]
        assert [c["prof"][1]["width"], c["prof"][1]["height"]] == [5760, 3840]
    summary = {}
    for r in real:
        k = (r["comb"], r["rate_code"])
        summary.setdefault(k, []).append(r["rate_index"])
    out = {"about": "libmpr.so 0x222b18, 0x2240cc and 0x225db8 run in Unicorn, stock and with build/mp4_meta_sites.py's sites. Generated by build/emu_mp4_meta.py.",
           "requests_the_stock_code_accepts": {f"comb {c} rate code {rc}": idx for (c, rc), idx in summary.items()},
           "result": "for every one of them: 3840x2560 -> config, stsd and PROF 3840x2560, same profile id; 5760x3840 with the sizes only -> stsd or PROF "
                     "refused; 5760x3840 with the design -> config, stsd and PROF 5760x3840, the stock profile id, pixel aspect 1:1",
           "rows": real}
    (ROOT / "evidence/pipeline/mp4_meta_emu.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf8", newline="\n")
    for (c, rc), idx in sorted(summary.items()):
        ex = next(r for r in real if r["comb"] == c and r["rate_code"] == rc)
        print("comb %d rate code %d: %d bit-rate indices; stock %s / 2560 %s / 5760 sizes only stsd %s prof %s / 5760 design %s prof %s %s"
              % (c, rc, len(idx), ex["stock"]["config"], ex["3840x2560 (design)"]["stsd"], ex["5760x3840 sizes only"]["stsd"][0],
                 ex["5760x3840 sizes only"]["prof"][0], ex["5760x3840 (design)"]["stsd"], ex["5760x3840 (design)"]["prof"][1]["profile_id"],
                 ex["5760x3840 (design)"]["prof"][1]["pixel_aspect"]))


def main_fx3():
    """FX3 7.02: the same requests on its own writer, stock and with the FX3 design's two heights (ogfile2560_hs_s_fx3_v2). Every request the stock
    code accepts must give config, stsd and PROF 3840x2560 with the stock profile id and pixel aspect, and the stock FX3 must answer every request as
    the stock A7 IV does (same accepted requests, same profile ids)."""
    fx = locate_file.locate("fx3_702", "libmpr.so").read_bytes()
    a4 = locate_file.locate("a7iv_602", "libmpr.so").read_bytes()
    meta = M.sites(3840, 2560, "fx3_702")
    M.check(fx, meta)
    libs = {"a7iv stock": Lib(a4), "stock": Lib(fx, "fx3_702"), "3840x2560 (design)": Lib(patched(fx, meta), "fx3_702")}
    rows = []
    for comb in (0, 2, 5, 7):
        for rate_code in (0, 2):
            for rate_index in range(2, 0x36):
                row = {"comb": comb, "codec": "HEVC" if comb in (5, 7) else "AVC", "rate_code": rate_code, "rate_index": rate_index}
                for name, lib in libs.items():
                    try:
                        r, cfg = lib.config(comb, rate_code, rate_index)
                        w, h = struct.unpack_from("<HH", cfg, 0x2A)[0], struct.unpack_from("<H", cfg, 0x28)[0]
                        rs, sz = lib.stsd(cfg)
                        rp, pf = lib.prof(cfg)
                        row[name] = {"config": [w, h], "stsd": [rs, list(sz)], "prof": [rp, pf]}
                    except UcError as e:
                        row[name] = {"error": str(e)}
                rows.append(row)
    ok_stock = lambda s: s.get("stsd", [1])[0] == 0 and s.get("prof", [1])[0] == 0
    for r in rows:                                    # the FX3's stock writer answers as the A7 IV's
        assert ok_stock(r["stock"]) == ok_stock(r["a7iv stock"]), (r["comb"], r["rate_index"])
        if ok_stock(r["stock"]):
            assert r["stock"]["config"] == r["a7iv stock"]["config"] == [3840, 2160] and r["stock"]["prof"][1] == r["a7iv stock"]["prof"][1]
    real = [r for r in rows if ok_stock(r["stock"])]
    assert real, "no request the stock code accepts"
    for r in real:
        s, a = r["stock"], r["3840x2560 (design)"]
        assert a["config"] == [3840, 2560] and a["stsd"] == [0, [3840, 2560]] and a["prof"][0] == 0, (r["comb"], r["rate_index"], a)
        assert a["prof"][1]["profile_id"] == s["prof"][1]["profile_id"] and a["prof"][1]["pixel_aspect"] == s["prof"][1]["pixel_aspect"]
        assert [a["prof"][1]["width"], a["prof"][1]["height"]] == [3840, 2560]
    rejected = [r for r in rows if not ok_stock(r["stock"])]
    assert all(not ok_stock(r["3840x2560 (design)"]) for r in rejected), "the design accepts a request stock refuses"
    summary = {}
    for r in real:
        summary.setdefault((r["comb"], r["rate_code"]), []).append(r["rate_index"])
    out = {"about": "FX3 7.02 libmpr.so 0x21fec4 (track config), 0x221464 (stsd entry) and 0x223110 (PROF entry) run in Unicorn, stock and with the two "
                    "heights of ogfile2560_hs_s_fx3_v2 (build/mp4_meta_sites.py OTHER_BUILDS); the A7 IV 6.02's writer on the same requests. "
                    "Generated by build/emu_mp4_meta.py --build fx3_702.",
           "requests_the_stock_code_accepts": {f"comb {c} rate code {rc}": idx for (c, rc), idx in summary.items()},
           "result": "the FX3's stock writer accepts the same requests as the A7 IV's and gives the same profile ids; with the design every one of them "
                     "gives config, stsd and PROF 3840x2560 with the stock profile id and pixel aspect; nothing stock refuses is accepted",
           "rows": real}
    dst = ROOT / "evidence/fx3/mp4_meta_emu_fx3.json"
    dst.write_text(json.dumps(out, indent=1) + "\n", encoding="utf8", newline="\n")
    for (c, rc), idx in sorted(summary.items()):
        ex = next(r for r in real if r["comb"] == c and r["rate_code"] == rc)
        print("comb %d rate code %d: %d bit-rate indices; stock %s %s / design stsd %s, PROF %sx%s %s pixel aspect %s"
              % (c, rc, len(idx), ex["stock"]["config"], ex["stock"]["prof"][1]["profile_id"], ex["3840x2560 (design)"]["stsd"],
                 ex["3840x2560 (design)"]["prof"][1]["width"], ex["3840x2560 (design)"]["prof"][1]["height"],
                 ex["3840x2560 (design)"]["prof"][1]["profile_id"], ex["3840x2560 (design)"]["prof"][1]["pixel_aspect"]))
    print("wrote", dst)


if __name__ == "__main__":
    main_fx3() if "--build" in sys.argv and sys.argv[sys.argv.index("--build") + 1] == "fx3_702" else main()
