"""A7S III 5.01: the output-plane memory design for a 4224 x 2816 picture (2026-11-28).

  C:\\Python313\\python.exe -B build\\build_dmm_s3.py                     (A7S III 5.01: dmm7slot_s3_v1)
  C:\\Python313\\python.exe -B build\\build_dmm_s3.py --build fx3_702     (FX3 7.02: dmm7slot_fx3_v1; its layouts are 0x28 HD / 0x2a 4K,
                                                                      the same shapes and sizes; the FX3 also fills a plane at 1.25
                                                                      bytes per pixel: its 3840 x 2560 state records in the stock planes)

Why. The movie output planes (memory id 0x2d9, DmmCfg key 0x3f1) are 13,271,040 bytes. The A7S III fills them at 1.25 bytes per pixel
(format code 2: 3840 x 2560 = 12,288,000 fits, which is why the 3840 x 2560 state needs no memory step, F979). A 4224 x 2816 picture is
14,868,480 bytes, 1,597,440 more than a plane holds. The main output takes its buffer id from the size table's own word (0x2d9; the
chooser by picture bytes is another path, F704 on the A7 IV, repo issues 1 and 2 on the FX6), so the planes of that id have to grow.

The A7S III's two layouts with output planes are the FX6's, moved by three group numbers (FX6 0x26 / 0x28 -> 0x29 / 0x2b): the 4K layout
0x2b = eight planes of key 0x3f1 in the 106,954,752-byte parent 0x39, and the HD layout 0x29 = 28 small planes and one 4K plane in the
same parent. So the design is the FX6's dmm7slot_fx6_v1, which RAN ON AN FX6 (github.com/ArcaneLantern/fx6-open-gate-test issue 2, user
Mininoob: the memory model, the seven-plane idea and the ten words), with another plane size:

dmm7slot_s3_v1   ten words of the camera's run-time copy of /cp/DmmCfg.bin. Seven of the 4K layout's eight planes get 14,942,208 bytes
                 (0xe40000: the picture's 14,868,480 and 73,728 to spare, a multiple of 64 KB as the FX6's 14,745,600), the eighth leaves
                 the pool (key 0x3f1 -> 0x7fd, 4096 bytes) so that the layout still fits its parent, and the HD layout's one 4K plane gets
                 14,942,208 too, which puts that layout over the parent (as on the FX6, where it ran).
Not built: the FX6's variant that retags the HD layout's plane instead (dmm7slot_fx6_v2). It was withdrawn there (it crashed XAVC-L).

Checks: the fit of both layouts, the spare key, and the A7S III's own allocator (emu_dmm_server.py, a7s3_501) on the stock and the
changed tables, in the states a camera can be in when the words land. Writes modding/designs/dmm7slot_s3_v1.json and
evidence/a7s3/dmm7slot_s3_emu.json. Design only: nothing is sent to a camera. Never run on a camera.
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

import capstone

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import emu_dmm_server as E  # noqa: E402
import parse_dmmcfg as P  # noqa: E402

BUILDS = {"a7s3_501": {"name": "dmm7slot_s3_v1", "hd": 0x29, "uhd": 0x2B, "reader": 0xAD1024, "camera": "ILCE-7SM3 (A7S III), firmware 5.01", "short": "A7S III",
                       "evidence": "evidence/a7s3/dmm7slot_s3_emu.json", "ev": "F979"},
          "fx3_702": {"name": "dmm7slot_fx3_v1", "hd": 0x28, "uhd": 0x2A, "reader": 0xAB8B70, "camera": "ILME-FX3 (FX3), firmware 7.02", "short": "FX3",
                      "evidence": "evidence/fx3/dmm7slot_fx3_emu.json", "ev": "two FX3s, 2026-11-24"}}
BUILD = sys.argv[sys.argv.index("--build") + 1] if "--build" in sys.argv else "a7s3_501"
_B = BUILDS[BUILD]
NAME = _B["name"]
KEY, HD_GROUP, UHD_GROUP, PARENT = 0x3F1, _B["hd"], _B["uhd"], 0x39
PARENT_SIZE = 106_954_752
PICTURE = (4224, 2816)
NEED = PICTURE[0] * PICTURE[1] * 5 // 4                   # 14,868,480 at 1.25 bytes per pixel
OLD, NEW = 13_271_040, 0xE40000                        # 4096 x 2160 x 1.5; 14,942,208
SPARE_KEY, SPARE_SIZE = 0x7FD, 4096
READER = _B["reader"]                                  # the record reader (A7S III 0xad1024, FX3 0xab8b70, FX6 0xac61a4, A7 IV 0xaff040)
MEM_ID = 0x2D9
w32 = lambda v: struct.pack("<I", v)


def key_limit(img):
    """The reader's fatal test on a record's key: the one `cmp rX, #imm` with 0x800 or 0x900 in the reader (FX6 0xac623e: #0x800)."""
    md = capstone.Cs(capstone.CS_ARCH_ARM, capstone.CS_MODE_THUMB)
    md.skipdata = True
    hits = [int(i.op_str.split("#")[1], 16) for i in md.disasm(img[READER - E.BASE:READER - E.BASE + 0x400], READER)
            if i.mnemonic.startswith("cmp") and i.op_str.endswith(("#0x800", "#0x900"))]
    assert len(set(hits)) == 1, hits
    return hits[0]


def ram_table(cfg):
    """The firmware's run-time copy of the unit records, rebuilt from the file: (base address, bytes, {seq: file offset}).
    The copy holds every 0x14-byte record of section B in file order, end markers included (build_dmm_fx6.ram_table)."""
    recs, at, seq = [], {}, 0
    for g in cfg.groups:
        o = g["at"] + 0x50
        for u in g["units"]:
            assert u["seq"] == seq and u["at"] == o
            recs.append(cfg.data[o:o + 0x14])
            at[seq] = o
            o, seq = o + 0x14, seq + 1
        assert cfg.data[o + 8:o + 12] == b"\xff" * 4               # the group's end marker
        recs.append(cfg.data[o:o + 0x14])
        at[seq] = o
        seq += 1
    return P.RAM[BUILD]["unit_records"], b"".join(recs), at


def design(cfg):
    R = P.RAM[BUILD]["unit_records"]
    ra = lambda u: R + u["seq"] * 0x14
    g_hd = next(g for g in cfg.groups if g["gid"] == HD_GROUP)
    g_4k = next(g for g in cfg.groups if g["gid"] == UHD_GROUP)
    assert g_hd["parent"] == g_4k["parent"] == PARENT and cfg.parent_sizes(PARENT) == {PARENT_SIZE}
    hd = [u for u in g_hd["units"] if u["key"] == KEY]
    assert len(hd) == 1 and hd[0] is g_hd["units"][-1] and len(g_hd["units"]) == 29
    assert [u["key"] for u in g_4k["units"]] == [KEY] * 8 and {u["size"] for u in g_4k["units"]} | {hd[0]["size"]} == {OLD}
    assert sorted(u["seq"] for u in cfg.units_by_key[KEY]) == sorted([hd[0]["seq"]] + [u["seq"] for u in g_4k["units"]])
    hd, last = hd[0], g_4k["units"][7]
    big = f"{OLD:,} -> {NEW:,}"
    sites = [(ra(hd) + 12, w32(OLD), w32(NEW), hd, f"HD layout {HD_GROUP:#x}, its one 4K plane: size {big} (the layout is then over its parent, as on the FX6)")]
    sites += [(ra(u) + 12, w32(OLD), w32(NEW), u, f"4K layout {UHD_GROUP:#x}, plane {k + 1} of 8: size {big}") for k, u in enumerate(g_4k["units"][:7])]
    sites += [(ra(last) + 8, w32(KEY), w32(SPARE_KEY), last, f"4K layout {UHD_GROUP:#x}, plane 8: key {KEY:#x} -> {SPARE_KEY:#x} (it leaves the pool)"),
              (ra(last) + 12, w32(OLD), w32(SPARE_SIZE), last, f"4K layout {UHD_GROUP:#x}, plane 8: size {OLD:,} -> {SPARE_SIZE:,}")]
    return sorted(sites, key=lambda s: s[0])


def guards_for(cfg, sites, table):
    """Bytes beside the sites, from the file: the rest of every touched record, the end markers before and after the 4K layout's planes,
    and the parent records. Each at most 16 bytes, inside one record, never on a site (build_dmm_fx6.guards_for)."""
    R, data, at = table
    site_at = {a for a, *_ in sites}
    out = []

    def add(addr, n, note):
        assert 0 < n <= 16 and not any(addr < s + 4 and s < addr + n for s in site_at)
        seq, off = divmod(addr - R, 0x14)
        assert off + n <= 0x14
        out.append({"ram_address": hex(addr), "bytes": data[addr - R:addr - R + n].hex(), "file_offset": hex(at[seq] + off), "note": note})

    seen = set()
    for _, _, _, u, _ in sites:
        if u["seq"] in seen:
            continue
        seen.add(u["seq"])
        rec = R + u["seq"] * 0x14
        free = [rec + 4 * k for k in range(5) if rec + 4 * k not in site_at]
        runs = [[free[0]]]
        for w in free[1:]:
            if w == runs[-1][-1] + 4:
                runs[-1].append(w)
            else:
                runs.append([w])
        for run in runs:
            add(run[0], 4 * len(run), "layout %#x, key %#x record at %#x: the words this design leaves alone, as in the file" % (u["group"]["gid"], u["key"], rec))
    g_4k = next(g for g in cfg.groups if g["gid"] == UHD_GROUP)
    first, last = g_4k["units"][0]["seq"], g_4k["units"][-1]["seq"]
    for seq, what in ((first - 1, "the end marker before the 4K layout's planes"), (last + 1, "the end marker after the 4K layout's planes")):
        assert data[seq * 0x14 + 8:seq * 0x14 + 12] == b"\xff" * 4
        add(R + seq * 0x14, 16, what)
    for u in cfg.units_by_key[PARENT]:
        add(R + u["seq"] * 0x14, 16, "parent block, key 0x39 in layout %#x: 106,954,752 bytes, as in the file" % u["group"]["gid"])
    return out


def fits(cfg, sites):
    R = P.RAM[BUILD]["unit_records"]
    size = {a: struct.unpack("<I", n)[0] for a, o, n, u, _ in sites if a == R + u["seq"] * 0x14 + 12}
    out = {}
    for gid in (HD_GROUP, UHD_GROUP):
        g = next(g for g in cfg.groups if g["gid"] == gid)
        total = sum(size.get(R + u["seq"] * 0x14 + 12, u["size"]) for u in g["units"])
        out[hex(gid)] = {"total": total, "parent": PARENT_SIZE, "spare": PARENT_SIZE - total}
    return out


def emulate(cfg, words):
    """The A7S III's own allocator: what requests for an output plane (id 0x2d9) get, in the states a camera can be in when the words land
    (build_dmm_fx6.emulate)."""
    def fresh():
        s = E.Server(cfg.data, cfg)
        assert s.init() == 0
        return s

    def write(s):
        for a, _, n, *_ in words:
            s.uc.mem_write(a, n)

    def opens(s, n):
        out = []
        for _ in range(n):
            e = s.open(MEM_ID)
            out.append(e["extents"][0]["size"] if e["ok"] else e["result"].split(" (")[0])
        return out

    def brief(lst):
        runs = []
        for x in lst:
            if runs and runs[-1][0] == x:
                runs[-1][1] += 1
            else:
                runs.append([x, 1])
        return [("%d x %s" % (n, f"{x:,}" if isinstance(x, int) else x)) for x, n in runs]

    res = {}
    s = fresh()
    write(s)
    res["nothing open when written"] = brief(opens(s, 20))
    for n in (9, 17):
        s = fresh()
        opens(s, n)
        write(s)
        base = len(s.opens) - n
        assert all(s.free(base + k)["ok"] for k in range(n))
        res["%d planes open when written, all released, then asked again" % n] = brief(opens(s, 20))
    s = fresh()
    opens(s, 9)
    write(s)
    base = len(s.opens) - 9
    assert all(s.free(base + k)["ok"] for k in range(1, 9))
    res["9 planes open when written, all but the first (the HD layout's) released, then asked again"] = brief(opens(s, 20))
    s = fresh()
    opens(s, 9)
    write(s)
    res["9 planes open when written, more asked without a release"] = brief(opens(s, 20))
    return res


def main():
    E.use_build(BUILD)
    cfg = P.Config(P.find_file(BUILD), BUILD)
    sha = hashlib.sha256(cfg.data).hexdigest()
    img = next(p for p in (ROOT / "work/extracted" / BUILD).rglob("cpapp-b.bin") if "nflasha8" in p.as_posix()).read_bytes()
    table = ram_table(cfg)
    base, data, at = table
    sites = design(cfg)
    assert NEED <= NEW and NEW % 0x10000 == 0 and len(sites) == 10
    limit = key_limit(img)
    assert SPARE_KEY < limit and SPARE_KEY not in cfg.units_by_key and SPARE_KEY not in cfg.region_by_key
    assert not any(SPARE_KEY in r["keys"] for r in cfg.ids)
    in_image = sum(1 for o in range(0, len(img) - 3, 4) if img[o:o + 4] == w32(SPARE_KEY))
    for a, o, n, u, _ in sites:
        assert data[a - base:a - base + 4] == o and o != n and a % 4 == 0
    # the FX6's design, word for word, at this build's records: the same records (HD layout's last, the 4K layout's eight) and fields
    fx = json.loads((ROOT / "modding/designs/dmm7slot_fx6_v1.json").read_text(encoding="utf8"))
    fx_new = sorted(s["new"] for s in fx["sites"])
    assert len(fx["sites"]) == 10 and sorted(n.hex() for _, _, n, *_ in sites) == sorted(x if x != w32(14_745_600).hex() else w32(NEW).hex() for x in fx_new)
    stock = emulate(cfg, [])
    assert stock["nothing open when written"] == ["17 x 13,271,040", "3 x no group offers the key now"], stock
    emu = {"stock": stock, NAME: emulate(cfg, sites)}
    full = "9 planes open when written, all released, then asked again"
    for k, v in emu[NAME].items():
        assert not any("13,271,040" in x for x in v), (k, v)   # no small plane is ever handed out once the words are in
    assert any(("14 x %s" % f"{NEW:,}") in x for x in emu[NAME][full]), emu[NAME][full]
    fit = fits(cfg, sites)
    assert fit[hex(UHD_GROUP)]["spare"] >= 0
    d = {"design": NAME, "build": BUILD, "camera": _B["camera"], "kind": "ram_words",
         "title": f"Output planes for a {PICTURE[0]} x {PICTURE[1]} picture: seven 4K-layout planes of {NEW:,} bytes, the eighth out of the pool, and the HD layout's plane enlarged",
         "status": "built from the firmware's file and run in the %s's own allocator; NEVER RUN ON A CAMERA. The same ten words with 14,745,600 ran on an FX6 (dmm7slot_fx6_v1)" % _B["short"],
         "credit": "the memory model, the seven-plane idea and the ten words: github.com/ArcaneLantern/fx6-open-gate-test issue 2 (Mininoob)",
         "artifact": "DmmCfg.bin (the coprocessor's copy: /cp, partition nflasha8)", "dmmcfg_sha256": sha,
         "generated_by": "build/build_dmm_s3.py" + ("" if BUILD == "a7s3_501" else " --build " + BUILD),
         "table": "unit records %#x .. %#x (parse_dmmcfg.RAM %s): record = base + seq x 0x14, {0, type, key, size, attributes}" % (base, base + len(data), BUILD),
         "why": f"the {_B['short']} fills an output plane at 1.25 bytes per pixel: 13,271,040 bytes hold 3840 x 2560 (12,288,000); {PICTURE[0]} x {PICTURE[1]} needs {NEED:,}",
         "plane": {"picture": list(PICTURE), "bytes_needed": NEED, "plane_bytes": NEW, "to_spare": NEW - NEED, "would_also_hold": "4240 x 2816 (14,928,000)"},
         "sites": [{"ram_address": hex(a), "old": o.hex(), "new": n.hex(), "file_offset": hex(at[u["seq"]] + (a - base) % 0x14), "note": note} for a, o, n, u, note in sites],
         "guards": guards_for(cfg, sites, table),
         "precondition": "the camera has started (the table is copied from the file at start-up). Written during a USB session; it counts from the next time the "
                         "parent block is divided, which the picture restart at the end of the session brings about (seen on the tester's FX6)",
         "restore": "the old words (step D17), or a cold boot: the table is rebuilt from the file at every start",
         "while_applied": ["14 output planes instead of 17 (two 4K layouts of seven)", "shoot 4K only; HD and S&Q are not tested with it"],
         "spare_key": {"key": hex(SPARE_KEY), "below_the_reader_limit": hex(limit), "in_the_file": False, "aligned_words_of_cpapp_with_this_value": in_image},
         "layouts_after": fit, "allocator": emu[NAME],
         "not_shown": (["anything on an A7S III", "that 1.25 bytes per pixel holds in every record format (it held for XAVC HS 4K 4:2:2 10-bit at 3840 x 2560, F979)"]
                       if BUILD == "a7s3_501" else
                       ["anything on a camera of this model", "that 1.25 bytes per pixel holds in every record format (3840 x 2560 records in the stock planes: %s)" % _B["ev"]]) + ["what the camera's picture pipeline does with the one refused request after a full release (the FX6 ran with it)"]}
    (ROOT / f"modding/designs/{NAME}.json").write_text(json.dumps(d, indent=1) + "\n", encoding="utf8", newline="\n")
    ev = {"build": BUILD, "dmmcfg_sha256": sha, "generated_by": "build/build_dmm_s3.py", "memory_id": hex(MEM_ID), "key": hex(KEY),
          "allocator": "cpapp-b.bin's own DMM module run alone (build/emu_dmm_server.py, " + BUILD + "; --selfcheck passes): one CPU, requests made as plain calls, "
                       "no other user of the parent block",
          "layouts": fit, "requests_for_an_output_plane": emu, "spare_key_limit": hex(limit)}
    (ROOT / _B["evidence"]).write_text(json.dumps(ev, indent=1) + "\n", encoding="utf8", newline="\n")
    print(NAME, len(d["sites"]), "sites,", len(d["guards"]), "guards; plane", f"{NEW:,}", "for", f"{NEED:,}")
    for name, r in emu.items():
        print(name)
        for k, v in r.items():
            print("   %-90s %s" % (k, v))
    print("layouts:", fit, "| key limit", hex(limit))


if __name__ == "__main__":
    main()
