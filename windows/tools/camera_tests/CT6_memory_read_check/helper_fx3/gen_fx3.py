"""Write fx3_expected.h for fx3read.c from the FX3 7.02 files and the four port designs.

  work/venv/Scripts/python.exe -I -B gen_fx3.py

The FX3 7.02 counterpart of helper_s3/gen_s3.py (the A7S III helper, which ran on an A7S III). Everything the helper compares against
is taken here from the extracted 7.02 update and from modding/designs/{ogsq_fx3_v1, outsz2560_fx3_v1, ogfile2560_hs_s_fx3_v1,
lcd32dsq_fx3_v1}.json; the helper holds no other constant about the camera except the addresses listed at the top of this file.
Differences from the A7S III helper: the FX3's addresses (modding/FX3_PORT.md; the dump's RAM pages ported by code reference with
build/port_addr.py), and the screen design's 30 words are read as soft sites (reported, not counted), so a check also says whether the
screen step is applied. Read-only on the inputs.
"""
import hashlib
import json
import struct
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
EX = ROOT / "work/extracted/fx3_702/0700_part_image/dev"
DES = ROOT / "modding/designs"
BASE = 0x108000
LABEL = "fx3read_v1"
CP_LO, CP_HI = 0xC0000, 0x2100000                     # coprocessor addresses a read may have: its logs (tomco.txt, the A7S III's), image and RAM tables
AVCAM_PHYS, AVCAM_RESERVE = 0x401000000, "@0x401000000"   # kemco.txt: memrsv=0x01000000@0x401000000:ex, as on the A7S III; checked on the camera before any read
ID_FILES = {"/libmpr.so": "nflasha15/lib/libmpr.so", "/libsencore.so": "nflasha15/lib/libsencore.so", "/libJiritsu.so": "nflasha15/lib/libJiritsu.so"}
# code pages (0x857000 holds the drive-parameter table map, the A7S III's 0x86d000) and a constant-data page (the FX3's constant data starts
# near 0xaea720, where the A7S III's 0xb11000 page is); none holds a design site, and each differs from the A7S III's and the ZV-E1's page
ID_PAGES = (0x128000, 0x4A8000, 0x857000, 0xAEB000)
DUMP_RANGES = (("shadow", 0xFF4000, 2), ("matrix", 0xF09000, 3), ("sizetable", 0x13C3000, 1), ("records", 0x1FDD000, 4),
               ("kprint", 0xE0000, 32), ("bootlog", 0xC0000, 8),
               # the second scaler's state, as the A7S III dump v3 (its 0x11a3000 / 0x11b5000 / 0x13ff000 / 0x119a000), at the FX3's addresses
               # (build/port_addr.py a7s3_501 fx3_702): saved records 0x117bdf8 / 0x117be30 and the context after them, resize work 0x118e828,
               # division block 0x13d776c, settings 0x13d8edc and the core log record 0x13d7f48 (all three -0x2911c), write-buffer ring 0x1172e70
               ("context", 0x117B000, 5), ("resizework", 0x118E000, 1), ("resizestate", 0x13D5000, 5), ("wbuf", 0x1172000, 3),
               # the display: fit-mode tables 0x1df4a8, de-squeeze ratios 0x1df6a8.., picture-ratio constants 0x1df7b8 (one page), the 2.0x crop
               # compares 0x5faf34 / 0x5faf68, the frame widgets' tables 0xd2e510.., the panel records (rear type byte 0x14909e4, second output
               # 0x1490b14), and the page where the menu's de-squeeze scale is stored by SET_ANAMO_DESQUEEZE_SCALE (0x10a8eb4)
               ("display", 0x1DF000, 1), ("crop", 0x5FA000, 1), ("frametab", 0xD2E000, 1), ("paneltype", 0x1490000, 1), ("desqueeze", 0x10A8000, 1))
# av-cam.bin guards: pieces of its tables that no site touches (the A7S III's, +0x77a0; the clip table +0x7780)
UNIT, CLIP, DESC = 0x395068, 0x39335C, 0x395108
DESIGNS = ("ogsq_fx3_v1", "outsz2560_fx3_v1", "ogfile2560_hs_s_fx3_v1", "lcd32dsq_fx3_v1")


def c_bytes(b):
    return "{" + ",".join(str(x) for x in b) + "}"


def main():
    cp = (EX / "nflasha8/cpapp-b.bin").read_bytes()
    av = (EX / "nflasha3/av-cam.bin").read_bytes()
    lm = (EX / "nflasha15/lib/libmpr.so").read_bytes()
    og, oz, fl, sc = (json.loads((DES / f"{n}.json").read_text(encoding="utf8")) for n in DESIGNS)
    assert og["artifact_sha256"] == sc["artifact_sha256"] == oz["emulated_image_sha256"] == hashlib.sha256(cp).hexdigest()
    assert fl["artifact_sha256"] == {"libmpr.so": hashlib.sha256(lm).hexdigest(), "av-cam.bin": hashlib.sha256(av).hexdigest()}
    out, blobs = [], []

    def blob(b):
        blobs.append(f"static const unsigned char B{len(blobs)}[] = {c_bytes(b)};")
        return f"B{len(blobs) - 1}"

    out.append(f'#define FX3_LABEL "{LABEL}"\n#define CP_LO {CP_LO:#x}U\n#define CP_HI {CP_HI:#x}U\n#define AVCAM_PHYS {AVCAM_PHYS:#x}UL\n'
               f'#define AVCAM_RESERVE "{AVCAM_RESERVE}"')
    out.append("struct id_file { const char *name; unsigned char sha256[32]; };\nstruct id_page { unsigned int address; unsigned char sha256[32]; };\n"
               "struct cp_site { const char *name; unsigned int address, length; const unsigned char *stock, *target; int soft; };\n"
               "struct mp_site { unsigned long offset; unsigned int length; const unsigned char *stock, *target; };\n"
               "struct av_guard { const char *name; unsigned long offset; unsigned int length; unsigned char sha256[32]; };\n"
               "struct dump_range { const char *name; unsigned int address, pages; };")
    rows = [f'    {{"{n}", {c_bytes(hashlib.sha256((EX / p).read_bytes()).digest())}}},' for n, p in ID_FILES.items()]
    out.append("static const struct id_file id_files[] = {\n" + "\n".join(rows) + "\n};")
    rows = [f"    {{{a:#x}, {c_bytes(hashlib.sha256(cp[a - BASE:a - BASE + 4096]).digest())}}}," for a in ID_PAGES]
    out.append("static const struct id_page id_pages[] = {\n" + "\n".join(rows) + "\n};")
    # ---- coprocessor sites
    sites = []
    for p in og["patches"]:
        a, old, new = int(p["addr"], 16), bytes.fromhex(p["old"]), bytes.fromhex(p["new"])
        assert cp[a - BASE:a - BASE + len(old)] == old and len(old) == len(new)
        name = p["note"].split(" ")[0] if p["kind"] == "S" else ("record_left" if "left" in p["note"] else "record_right")
        sites.append((name, a, old, new, 0))
    sr = og["stored_record"]
    # soft: the camera fills parts of this record at run time, so it need not equal the emulated one; reported, not counted
    sites.append(("stored_record", int(sr["address"], 16), bytes.fromhex(sr["stock"]), bytes.fromhex(sr["design"]), 1))
    for s in oz["sites"]:                                 # soft: the size table is zero until a movie mode has run
        sites.append(("outsize", int(s["ram_address"], 16), bytes.fromhex(s["old"]), bytes.fromhex(s["new"]), 1))
    for k, g in enumerate(oz["guards"]):
        sites.append((f"outsize_guard{k}", int(g["ram_address"], 16), bytes.fromhex(g["bytes"]), None, 1))
    for k, s in enumerate(sc["sites"]):                   # soft: the screen step is optional (apply --no-screen); reported, not counted
        a = int(s["ram_address"], 16)
        assert cp[a - BASE:a - BASE + 4] == bytes.fromhex(s["old"])
        sites.append((f"screen{k}", a, bytes.fromhex(s["old"]), bytes.fromhex(s["new"]), 1))
    rows = []
    for name, a, old, new, soft in sites:
        assert CP_LO <= a and a + len(old) <= CP_HI and len(old) <= 3072
        rows.append(f'    {{"{name}", {a:#x}, {len(old)}, {blob(old)}, {blob(new) if new is not None else "0"}, {soft}}},')
    out.append("static const struct cp_site cp_sites[] = {\n" + "\n".join(rows) + "\n};")
    # ---- main-processor sites
    lmr, avr, av_hi = [], [], 0
    for p in fl["patches"]:
        o, old, new = int(p["file_off"], 16), bytes.fromhex(p["old"]), bytes.fromhex(p["new"])
        src = lm if p["binary"] == "libmpr.so" else av
        assert src[o:o + len(old)] == old
        (lmr if p["binary"] == "libmpr.so" else avr).append(f"    {{{o:#x}UL, {len(old)}, {blob(old)}, {blob(new)}}},")
        if p["binary"] == "av-cam.bin":
            av_hi = max(av_hi, o + len(old))
    out.append("static const struct mp_site lm_sites[] = {\n" + "\n".join(lmr) + "\n};")
    out.append("static const struct mp_site av_sites[] = {\n" + "\n".join(avr) + "\n};")
    guards = (("unit_rows_0_2", UNIT, 0x30), ("clip_rows_2_7", CLIP + 0x20, 0x60), ("descriptors_0_3", DESC, 4 * 0x90))
    spans = [(int(p["file_off"], 16), len(p["old"]) // 2) for p in fl["patches"] if p["binary"] == "av-cam.bin"]
    rows = []
    for name, o, n in guards:
        assert all(o + n <= so or so + sn <= o for so, sn in spans), name
        rows.append(f'    {{"{name}", {o:#x}UL, {n}, {c_bytes(hashlib.sha256(av[o:o + n]).digest())}}},')
        av_hi = max(av_hi, o + n)
    out.append("static const struct av_guard av_guards[] = {\n" + "\n".join(rows) + "\n};")
    av_lo = min([so for so, _ in spans] + [o for _, o, _ in guards]) & ~0xFFF
    out.append(f"#define AV_LO {av_lo:#x}UL\n#define AV_HI {av_hi:#x}UL")
    rows = [f'    {{"{n}", {a:#x}, {k}}},' for n, a, k in DUMP_RANGES]
    assert all(CP_LO <= a and a + 4096 * k <= CP_HI for _, a, k in DUMP_RANGES)
    out.append("#if DUMP\nstatic const struct dump_range dump_ranges[] = {\n" + "\n".join(rows) + "\n};\n#endif")
    text = ("/* Generated by gen_fx3.py from the FX3 7.02 files and the port designs. Do not edit. */\n#ifndef DUMP\n#define DUMP 0\n#endif\n"
            + "\n".join(blobs) + "\n" + "\n".join(out) + "\n")
    (HERE / "fx3_expected.h").write_text(text, encoding="utf8", newline="\n")
    facts = {"label": LABEL, "cp_lo": CP_LO, "cp_hi": CP_HI, "avcam_phys": AVCAM_PHYS, "avcam_reserve": AVCAM_RESERVE,
             "id_files": {n: hashlib.sha256((EX / p).read_bytes()).hexdigest() for n, p in ID_FILES.items()},
             "id_pages": {hex(a): hashlib.sha256(cp[a - BASE:a - BASE + 4096]).hexdigest() for a in ID_PAGES},
             "cp_sites": [{"name": n, "address": hex(a), "length": len(o), "soft": s} for n, a, o, _, s in sites],
             "lm_sites": len(lmr), "av_sites": len(avr), "av_guards": [g[0] for g in guards], "dump_ranges": [[n, hex(a), k] for n, a, k in DUMP_RANGES],
             "designs": {d["design"]: hashlib.sha256((DES / (d["design"] + ".json")).read_bytes()).hexdigest() for d in (og, oz, fl, sc)}}
    (HERE / "fx3_expected.json").write_text(json.dumps(facts, indent=1) + "\n", encoding="utf8", newline="\n")
    # ---- what the PC needs to read a dump without the firmware files: the register matrix, the column map, the mode ids, the emulated records,
    # and the screen design's words
    M, CM, IDS, RECS, REC = 0xF09F84, 0xC53538, 0xC53790, 0x1FDD574, 0x15C
    matrix, k = [], 0
    while struct.unpack_from("<I", cp, M - BASE + 16 * k)[0]:
        matrix.append([struct.unpack_from("<I", cp, M - BASE + 16 * k)[0], cp[M - BASE + 16 * k + 4:M - BASE + 16 * k + 16].hex()])
        k += 1
    emu = json.loads((ROOT / "evidence/fx3/drvparam_stock_fx3_702.json").read_text(encoding="utf8"))["modes"]
    ref = {"about": "FX3 7.02 reference data for reading an fx3read dump; from cpapp-b.bin and build/emu_drvparam.py", "matrix_address": hex(M),
           "matrix": matrix, "column_map": [list(struct.unpack_from("<2I", cp, CM - BASE + 8 * i)) for i in range(40)],
           "mode_ids": [hex(x) for x in struct.unpack_from("<40I", cp, IDS - BASE)], "records_address": hex(RECS), "record_size": REC,
           "emulated_stock_records": {m: v["record"] for m, v in emu.items()}, "size_table_address": "0x13c3190",
           "stored_record_design": {"mode": "0x8c0", "index": og["mode_index"], "stock": sr["stock"], "design": sr["design"]},
           "screen_words": [{"address": s["ram_address"], "stock": s["old"], "new": s["new"], "note": s["note"]} for s in sc["sites"]]}
    assert len(matrix) == 489 and len(ref["emulated_stock_records"]) == 40
    (HERE / "fx3_reference.json").write_text(json.dumps(ref) + "\n", encoding="utf8", newline="\n")
    print(f"fx3_expected.h: {len(sites)} coprocessor sites ({len(sc['sites'])} of the screen), {len(lmr)} libmpr sites, {len(avr)} av-cam sites, {len(text)} bytes of header")


if __name__ == "__main__":
    main()
