"""FX3 (ILME-FX3) firmware 7.02: run one of the two READ-ONLY helper libraries and save what it reports.

  python fx3_run.py check --dry-run | --selftest
  python fx3_run.py dump  --dry-run | --selftest
  python fx3_run.py check --go --firmware-shown 7.02
  python fx3_run.py dump  --go --firmware-shown 7.02 [--clear-result SHA256]

  check   identity of the camera's software and what every site of the open-gate designs holds now: READY / NOT READY
          (the screen step's 30 words are reported as well, not counted: it is optional)
  dump    the same, plus kernel and memory facts, the coprocessor's logs and some of its tables (sensor registers, stored
          records, the scaler's state, the display: panel type, 3:2 ratio, frame tables, de-squeeze ratios)

Both libraries only read. Each creates one file, its result, on the camera's RAM disk; this script fetches it. The
library is written to the camera's service partition, loaded once, and deleted again in the same session.

The FX3 counterpart of s3_run.py (the A7S III kit, whose libraries ran on an A7S III), made from it on 2026-11-24 with this
camera's libraries, pins and result reader. Nothing here can send a memory write: neither read-only library contains one.
"""
import argparse
import json
import platform
import re
import struct
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "CT1_usb_first_contact"))
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "helper"))
sys.path.insert(0, str(HERE / "helper_fx3"))
import ct1_common as c  # noqa: E402
import ct6_level1_run as R  # noqa: E402

FIRMWARE, MODEL, BUILD = "7.02", "ILME-FX3", "fx3_702"
S3 = HERE / "helper_fx3"                       # this kit's folder (the name S3 is kept from s3_run.py)
PINS = {"check": ("libJit_fx3_check.so", "6f99aef2399a739b06d282e6b67cad842c643e33d04caad5fe4721558097cff6"),      # fx3read_v2 (2026-11-25)
        "dump": ("libJit_fx3_dump.so", "fdb83bfe2393f2cb1fe383e2cf9760cbd45d849b5425ae5ae47084df123511f8")}
LEVELS = {"check": 101, "dump": 102}              # numbers outside the A7 IV runner's own levels: none of its level-specific code runs
# THE WRITE STEPS. Each is one library built from the A7 IV helper's write code with this camera's tables (helper_fx3/build_fx3_write.sh).
# They change the running camera's memory until a cold boot. They are run through fx3_apply.py, never by a launcher of the read-only kit,
# and the libraries are not in the published kit unless it was published with --include-write.
WRITE_STEPS = {
    # L5/L6 since 2026-11-26: ogsq_fx3_v2 = v1 (drive mode 0x8c0: 23.98p, and 24p in PAL; the A7S III's working ogsq_s3_v5, which works on FX3s) + the same
    # cells on drive mode 0x820 (29.97p, and 25p in PAL: a tester's 25p design, which ran) + the stored records of both modes in NTSC or PAL form, the
    # one the camera holds (readcheck.c MULTI_REC). O5 is the earlier L5 (v1) byte for byte: apply --only-24p (NTSC only). L6 puts back either.
    "L5": ("libJit_fx3_L5.so", "9911699077a8a9a3b85b288e8c23c7e7063c6a54de5e533c22144f64a8dff1f5", "apply the sensor-side design ogsq_fx3_v2 (24p and 25p/30p modes: sensor cells, two records, the stored records, NTSC or PAL)"),
    "L6": ("libJit_fx3_L6.so", "a2f67b80aedb9cea1e0b449bd5988ecfb39e5f28fc347ad6c8c7afcde9890388", "put back the sensor-side design ogsq_fx3_v2 (or the earlier v1)"),
    "O5": ("libJit_fx3_O5.so", "9fd94c179f8c7b721600313a1e7a7f2a173a1a3dae24319fe4411cba4dac5946", "apply the earlier sensor-side design ogsq_fx3_v1 (24p only, NTSC; the step that ran on FX3s)"),
    "L16": ("libJit_fx3_L16.so", "cf644fb3d893c54ed80bffdde74fc51d7a4aab90bd74486f240ae23aaf3f636f", "apply the output size outsz2560_fx3_v1 (one word)"),
    "L17": ("libJit_fx3_L17.so", "5a3c16bf88a3f7f817df12ea0e9aea8dc8e694755af69ac86f6e8339c6eba0d4", "put back the output size outsz2560_fx3_v1"),
    # L19/L20 since 2026-11-25: ogfile2560_hs_s_fx3_v2 = the first kit's encoder side (which ran on an FX3) + the two MP4 header heights, so
    # tkhd, stsd and Sony's PROF say 3840x2560 (the A7 IV's ogfile2560_hs_s_v2). L20 puts back either version. N19 = the first kit's L19,
    # byte for byte (apply --no-meta); its put back is L20 too (the first kit's L20 would leave the two heights on a v2 camera).
    # 2026-11-26: L19/L20 carry ogfile2560_hs_s_fx3_v3 = v2 + the 29.97p descriptors and profiles (48 sites). L20 puts back v3, v2 or v1.
    "L19": ("libJit_fx3_L19.so", "64793d5a77d391c618d763626e19cd0b9e39a7228a1a56093fd0a893ab73d621", "apply the encoder-side design ogfile2560_hs_s_fx3_v3 (23.98p, 25p, 29.97p: 149 + 4 sites, and the MP4 headers say 3840x2560: 2 more)"),
    "L20": ("libJit_fx3_L20.so", "ba041c6eb5525a5eb5998f64f567be8b7ae7139076f47cc7d92df2e4bb5ae609", "put back the encoder-side design ogfile2560_hs_s_fx3_v3 (or v2, or the first kit's v1)"),
    "N19": ("libJit_fx3_N19.so", "47400649ac29ac03fd77b4805e0a41c60b4a3cfa1ae5e3f384f0d33a0b503050", "apply the first kit's encoder-side design ogfile2560_hs_s_fx3_v1 (101 + 4 sites; the MP4 headers keep 3840x2160)"),
    # The rear-screen step (optional, on top of the open-gate state): the same level 16/17 code with the screen words. The digits are the level the
    # library reports in its result's first line. There is no C step: the FX3's own De-Squeeze Display is kept (its ratios are part of S16).
    "S16": ("libJit_fx3_S16.so", "bc40334bb9bd44b69f6f6eb268b90f37696e1126c773dfe483acb0f9b369beef", "apply the screen words lcd32dsq_fx3_v1 (3:2 picture on the rear screen, the focus-frame rectangles, and De-Squeeze Display ratios for a 3:2 picture: 30 words)"),
    "S17": ("libJit_fx3_S17.so", "50a962685412467e2c9fb3f60440c2a8de5cf6d26ec71f1e4d7c305c4b396f0e", "put back the screen words lcd32dsq_fx3_v1"),
    # The playback step (optional, 2026-11-25; NOT RUN ON ANY CAMERA): in-camera playback of 3840x2560 clips with the A7 IV's decode channel
    # (avdec8k_fx3_v1: four code words and one table word of av-cam.bin, readcheck.c levels 29 / 30). The code words are kernel text: the
    # library refuses unless the processors' instruction caches can be made to fetch them afresh, and orders the writes so no state between
    # them is worse than stock. Independent of the open-gate steps; fx3_apply.py playback / playback-putback.
    "P29": ("libJit_fx3_P29.so", "c0ccb8c8fd80007cbc308720a78deec19fc132067ae5d04c78a555b27f63cc74", "apply the playback decoder avdec8k_fx3_v1 (the A7 IV's 7690x4320 decode channel and its memory: 4 code words and 1 table word of av-cam.bin)"),
    "P30": ("libJit_fx3_P30.so", "671de524a2848830c89764420b69f4417a92cc249b5f5a6726f9fbaac9080079", "put back the playback decoder avdec8k_fx3_v1"),
    # XAVC S-I 4K (2026-11-25; NOT RUN ON ANY CAMERA): the same level 19/20 code with ogfilesi2560_fx3_v1, the A7 IV's ogfilesi2560_v1 at the FX3's
    # tables (build/build_ogfile_si.py --build fx3_702, emulated on the FX3's own code by build/emu_ogfilesi_fx3.py). One more step of apply and
    # putback, so one run gives XAVC HS 4K, XAVC S 4K and XAVC S-I 4K at 3840x2560; its sites are none of L19's (--no-si leaves it out).
    # 2026-11-26: ogfilesi2560_fx3_v2 = v1 + the two 29.97p descriptors and their profiles. I20 puts back v2 or v1.
    "I19": ("libJit_fx3_I19.so", "3a553194f83439eb8c3fffaa545535ee656515378b52b10d37a8737d5831fe6a", "apply XAVC S-I 4K at 3840x2560: ogfilesi2560_fx3_v2 (23.98p, 25p, 29.97p: the S-I encoder request, 6 descriptors and their profiles: 24 + 1 sites)"),
    "I20": ("libJit_fx3_I20.so", "0754c501aadb37c9db9e614dd93751bee1717dabd90c39588ea9173cd1ae66f2", "put back XAVC S-I 4K: ogfilesi2560_fx3_v2 (or v1)"),
    # THE 4224x2816 STATE (2026-11-28; NOT RUN ON A CAMERA): the central 4224 x 2816 of the sensor's 4240 x 2832, pixel for pixel; the A7S III kit's
    # state of the same day at the FX3's addresses (modding/FX3_PORT.md). The same levels with other tables: H = the sensor side with the first stage
    # passed one to one (L5's cells, 24p and 25p/30p, NTSC or PAL), D = the output planes, K = output size and encoder side, J = the encoder side
    # without the MP4 header size, R = the encoder side with the 100M settings at 300 Mbps.
    "H5": ("libJit_fx3_H5.so", "7666f206965f7adfaa7806fd8dfad7fb994ed45797254c68dd76ac5e11cc3a9a", "apply the sensor-side design ogh2816_fx3_v1 (L5's sensor cells; the two records with a first stage of 2832 rows passed one to one; stored records 27/32, NTSC or PAL)"),
    "H6": ("libJit_fx3_H6.so", "7613ccb8f9f8ad774693ae79e716498068effa220e7058b28a53a3220ff6d486", "put back the sensor-side design ogh2816_fx3_v1"),
    "D16": ("libJit_fx3_D16.so", "5fa5a95c44d070d0cf484041f5342f77df84057377fd9b1fd0b06af148e25110", "apply the output planes dmm7slot_fx3_v1 (ten words: seven 4K planes of 14,942,208 bytes, as the FX6 kit's memory step)"),
    "D17": ("libJit_fx3_D17.so", "dfad781d74c8b36e84c2d12f82244c78be5d97dedc3110716a57c4a4544a8d75", "put back the output planes dmm7slot_fx3_v1"),
    "K16": ("libJit_fx3_K16.so", "a6f89180441a3099323b3494a67fb3e93b61a009d0874e5202888db75c30cee1", "apply the output size outsz4224_fx3_v1 (one word: 4224 x 2816)"),
    "K17": ("libJit_fx3_K17.so", "952f9c973094b6625f35c9f0147fc408c95d68a2aa181cb59794c54ecc76bf5f", "put back the output size outsz4224_fx3_v1"),
    "K19": ("libJit_fx3_K19.so", "baee9959b7e7f34f6808fe3df02780d5d628b5a28f6495fad06185bb4d08b706", "apply the encoder-side design ogfile4224_fx3_v1 (23.98p, 25p, 29.97p: 303 + 13 sites: 4224 x 2816 on both encoder cores, and the MP4 header size)"),
    "K20": ("libJit_fx3_K20.so", "4e3483ad3d08a0d46d13316864f2a79f14540d9a2fc8d229b7fb51c938916d74", "put back the encoder-side design ogfile4224_fx3_v1 (also after J19)"),
    "J19": ("libJit_fx3_J19.so", "711a334e1b6b2f508c5708d2b831c9371fe14409daacaebb3fe974d234a8d426", "apply the encoder-side design ogfile4224nm_fx3_v1 (303 + 4 sites, without the MP4 header size)"),
    "R19": ("libJit_fx3_R19.so", "5c94f52983d131a6c25d9b3ea00f0aac6eb98ccbc2591e5024243957525ad68e", "apply the encoder-side design ogfile4224r300_fx3_v1 (351 + 13 sites: as K19, the 100M record settings at 300 Mbps)"),
    "R20": ("libJit_fx3_R20.so", "bbca502306775622b5e5c7e6a006ad5ffa64fdbcf97a5c342329c999e065eab4", "put back the encoder-side design ogfile4224r300_fx3_v1"),
}
PINS.update({k: v[:2] for k, v in WRITE_STEPS.items()})
LEVELS.update({k: {"L": 200, "S": 300, "N": 500, "P": 600, "I": 700, "O": 800, "H": 900, "D": 1000, "K": 1100, "J": 1200, "R": 1300}[k[0]] + int(k[1:]) for k in WRITE_STEPS})
WHICH = "check"
FIT_4224 = [4240, 2816, 8, 0, 4224, 2816, 0, 0, 0, 0]   # the second scaler's block in the 4224x2816 state (build/build_og_fx3_native.py, the firmware's own fit)
# Libraries this kit published before and no longer runs. With PINS they are the files a run may delete from the camera's service partition
# when an earlier session left one behind (R.KNOWN_LIBS; on 2026-11-26 an FX3 tester's cut-off L19 session blocked every later run).
EARLIER_LIBS = {
    "6ca3ee7df282bda70bc50bb4f9284ccc622c2c20e6ab64b964a949148a33d836": "the first kit's L20 (put back of ogfile2560_hs_s_fx3_v1)",
    "fcf97a8ea56abee543734779b8cac10267b4b33adda863a4032c11436e6d78ce": "the first kit's read-only check (fx3read_v1)",
    "ad2bae7922865dd7faf3bce59aa4114e53fe56ce4366b133c96ce91414592527": "the first kit's read-only dump (fx3read_v1)",
    # replaced on 2026-11-26 (open gate at 25p and 29.97p): the 2026-11-25 kit's L6, L19, L20, I19, I20 (its L5 is O5, still pinned). The L19 is the
    # file an FX3 tester's cut-off session left on his camera (2026-11-26).
    "6c8544fb91879ba4c1b8ce9351826253b61557d797466f836e4e8e65b0acf3b6": "the 2026-11-25 kit's L6 (put back of ogsq_fx3_v1)",
    "c028f58c3e3a941e22eaf07445df7137eb4c739d48ce0b4f3fdac4f7744828e6": "the 2026-11-25 kit's L19 (ogfile2560_hs_s_fx3_v2)",
    "b84dd6758c18bed649aba7d3f62820a9bbb462f4fcceeade27bb91cdbe960f67": "the 2026-11-25 kit's L20 (put back of ogfile2560_hs_s_fx3_v2)",
    "740ba55937c233d1b143d14b8e48e826a8988ff78e72e8cf10d26dea8f14c8cc": "the 2026-11-25 kit's I19 (ogfilesi2560_fx3_v1)",
    "5cc2d1a692dbd3136c51ec88c345ea23c4204e83d7503721d9407ac9c636f63e": "the 2026-11-25 kit's I20 (put back of ogfilesi2560_fx3_v1)",
}
EXTRA_LIBS = {}                                   # --remove-library: one more file, named by its SHA-256 on the command line


def known_libs():
    out = {sha: "this kit's %s library (%s)" % ("read-only " + k if k in ("check", "dump") else "step " + k, name) for k, (name, sha) in PINS.items()}
    out.update(EARLIER_LIBS)
    out.update(EXTRA_LIBS)
    return out


def write_result(data):
    """The facts of a write step's result (the A7 IV helper's report format)."""
    import hashlib
    text = data.decode("utf8", "replace")
    lines = text.split("\n")
    pick = lambda start: next((ln for ln in lines if ln.startswith(start)), None)
    outcome = ("UNDO INCOMPLETE" if pick("!! UNDO INCOMPLETE") or pick("UNDO INCOMPLETE") else "DONE" if pick("DONE: ") else "NOTHING TO DO" if pick("NOTHING TO DO") else
               "NOT DONE (everything put back)" if pick("NOT DONE: ") else "NOTHING WRITTEN" if any("nothing is written" in ln for ln in lines) else "UNKNOWN")
    problems = [ln for ln in lines if ln.startswith("!!")]
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "header_ok": lines[0].startswith("readcheck 1 level %s" % WHICH[1:]),
            "euid": "see the result", "sections": [ln for ln in lines if ln.startswith("== ")], "problems": len(problems),
            "complete": any(ln.startswith("== done") for ln in lines[-3:]),
            "s3": {"step": WHICH, "what": WRITE_STEPS[WHICH][2], "outcome": outcome, "ok": outcome in ("DONE", "NOTHING TO DO"),
                   "outcome_line": pick("DONE: ") or pick("NOTHING TO DO") or pick("NOT DONE: ") or pick("!! UNDO INCOMPLETE") or pick("UNDO INCOMPLETE"), "problem_lines": problems}}


def reference():
    return json.loads((S3 / "fx3_reference.json").read_text(encoding="utf8"))


def expected():
    return json.loads((S3 / "fx3_expected.json").read_text(encoding="utf8"))


# ------------------------------------------------------------ reading a result

def check_result(data):
    """The facts of a result file. Keys the A7 IV runner prints, plus this helper's own under "s3"."""
    if WHICH in WRITE_STEPS:
        return write_result(data)
    text = data.decode("utf8", "replace")
    lines = text.split("\n")
    head = lines[0] if lines else ""
    count = lambda pat: sum(1 for ln in lines if re.search(pat, ln))
    verdict = next((ln for ln in lines if ln.startswith("VERDICT ")), "no verdict line")
    pages = {}
    for ln in lines:
        if ln.startswith("cppage "):
            _, name, addr, hx = ln.split(" ", 3)
            pages[int(addr, 16)] = (name, bytes.fromhex(hx.strip()))
    sites = []
    for ln in lines:
        m = re.match(r"site (\S+) (0x[0-9a-f]+) len (\d+)(?: bytes (?:differing from stock )?(\S+))?  (STOCK|TARGET|OTHER.*|NOT READ)$", ln)
        if m:
            sites.append({"name": m.group(1), "address": m.group(2), "length": int(m.group(3)), "shown": m.group(4), "state": m.group(5)})
    s3 = {"header": head, "verdict": verdict, "ready": verdict.startswith("VERDICT READY"),
          "identity_same": count(r"SAME as the 7\.02 update$"), "identity_differs": count(r"DIFFERS from the 7\.02 update$"),
          "coprocessor_sites": sites, "libmpr_sites": [ln for ln in lines if ln.startswith("lm ")],
          "avcam_stock": count(r"^av .*  STOCK$"), "avcam_target": count(r"^av .*  TARGET$"), "avcam_other": count(r"^av .*  OTHER$"),
          "avcam_guards": [ln for ln in lines if ln.startswith("guard ")], "problem_lines": [ln for ln in lines if ln.startswith("!!")],
          "pages": len(pages)}
    cmd = re.search(r"== file /proc/cmdline\n(.*?)\n== end", text, re.S)
    ver = re.search(r"== file /proc/version\n(.*?)\n== end", text, re.S)
    s3["kernel_command_line"], s3["kernel_version"] = (cmd.group(1).strip() if cmd else None), (ver.group(1).strip() if ver else None)
    if pages:
        s3["decoded"] = decode_pages(pages)
    import hashlib
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "header_ok": head.startswith("fx3read ") and "ILME-FX3 7.02" in head, "euid": "not read",
            "sections": [ln for ln in lines if ln.startswith("== ")], "problems": len(s3["problem_lines"]), "complete": "== done" in lines[-3:],
            "s3": s3, "_pages": pages}


def decode_pages(pages):
    """What the dump's coprocessor pages say, set against the firmware file's tables."""
    ref, out = reference(), {}

    def mem(addr, n):
        b = bytearray()
        while n:
            page = pages.get(addr & ~0xFFF)
            if page is None:
                return None
            take = min(n, 4096 - (addr & 0xFFF))
            b += page[1][addr & 0xFFF:(addr & 0xFFF) + take]
            addr, n = addr + take, n - take
        return bytes(b)

    # the sensor register shadow against each column of the register matrix
    rows = [(a, bytes.fromhex(h)) for a, h in ref["matrix"]]
    shadow = [(a, mem(a, 1)) for a, _ in rows]
    if all(v is not None for _, v in shadow):
        score = [sum(1 for (a, cols), (_, v) in zip(rows, shadow) if cols[k] == v[0]) for k in range(12)]
        best = max(range(12), key=lambda k: score[k])
        users = [ref["mode_ids"][i] for i, (col, _) in enumerate(ref["column_map"]) if col == best]
        out["sensor_registers"] = {"rows": len(rows), "rows_equal_per_column": score, "closest_column": best, "modes_using_it": users,
                                   "rows_differing_from_it": [[i, hex(a), cols[best], v[0]] for i, ((a, cols), (_, v)) in enumerate(zip(rows, shadow)) if cols[best] != v[0]][:64],
                                   "window_rows_6_7_24_42": [shadow[i][1][0] for i in (6, 7, 24, 42)]}
    # the matrix itself as the camera holds it
    m0 = int(ref["matrix_address"], 16)
    got = mem(m0, 16 * len(rows)) if (m0 & ~0xFFF) in pages else None
    if got is not None:
        want = b"".join(struct.pack("<I", a) + cols for a, cols in rows)
        out["matrix_equals_file"] = got == want
    # the stored drive-parameter records against the emulated ones
    r0, size = int(ref["records_address"], 16), ref["record_size"]
    recs = {}
    for i, mid in enumerate(ref["mode_ids"]):
        b = mem(r0 + i * size, size)
        if b is None:
            continue
        emu = bytes.fromhex(ref["emulated_stock_records"][mid])
        diff = [o for o in range(size) if b[o] != emu[o]]
        recs[mid] = {"index": i, "all_zero": not any(b), "bytes_differing_from_emulation": len(diff), "offsets": [hex(o) for o in diff[:48]], "record": b.hex()}
    out["stored_records"] = recs
    t = mem(int(ref["size_table_address"], 16), 128)
    if t is not None:
        out["size_table"] = [list(struct.unpack_from("<HHI", t, 8 * k)) for k in range(16)]
    # The second scaler's state, as the A7S III dump v3 reads it, at the FX3's addresses (build/port_addr.py a7s3_501 fx3_702: division block,
    # settings and the core log record all moved by -0x2911c; resize work 0x118e828). The block and input words are the A7S III's
    # "predicted" ones (the A7 IV's distance from the division block), moved the same way: NOT confirmed.
    st = {}
    blk = mem(0x13D7320, 0x20)                    # A7S III 0x140043c: in w, in h, start x, y, w-1, h-1, start fractions, size fractions (u16)
    if blk is not None:
        w = struct.unpack_from("<10H", blk)
        st["second_scaler_block"] = {"address": "0x13d7320", "words": list(w), "start": [round(w[2] + w[6] / 4096, 3), round(w[3] + w[7] / 4096, 3)],
                                     "size": [round(w[4] + w[8] / 4096, 3), round(w[5] + w[9] / 4096, 3)]}
    inp = mem(0x13D735C, 8)                       # A7S III 0x1400478
    if inp is not None:
        st["second_scaler_input"] = list(struct.unpack_from("<4H", inp))
    ws = mem(0x118E828, 0xDC)                     # A7S III 0x11b5c40: pixel aspect +0x48, scales +0x4c / +0x50 (Q12), zoom +0x24 (Q16)
    if ws is not None:
        st["resize_work"] = {"pixel_aspect_q12": struct.unpack_from("<i", ws, 0x48)[0], "scale_h_q12": struct.unpack_from("<i", ws, 0x4C)[0],
                             "scale_v_q12": struct.unpack_from("<i", ws, 0x50)[0], "zoom_q16": struct.unpack_from("<i", ws, 0x24)[0], "head": ws[:0x60].hex()}
    se = mem(0x13D8EDC, 0x20)                     # A7S III 0x1401ff8
    if se is not None:
        st["resize_settings"] = se.hex()
    dv = mem(0x13D776C, 0x5A0)                    # A7S III 0x1400888: per unit, stride 0x150: +0xc in start, +0x10 in width, +0x20 out width
    if dv is not None:
        st["division_units"] = [{"in_start": struct.unpack_from("<I", dv, k * 0x150 + 0xC)[0], "in_width": struct.unpack_from("<I", dv, k * 0x150 + 0x10)[0],
                                 "out_width": struct.unpack_from("<I", dv, k * 0x150 + 0x20)[0]} for k in range(4)]
    seen = {}
    pairs = {(4240, 2832), (4240, 2392), (4240, 2385), (4240, 2848), (4240, 2408), (3840, 2560), (3840, 2160), (1920, 1080), (2144, 2392), (2096, 2392), (2176, 2408),
             (4224, 2816), (4240, 2816), (4264, 2832), (2144, 2816), (2096, 2816), (2176, 2832), (2128, 2832)}      # the 4224x2816 state
    for addr, (name, blob) in sorted(pages.items()):
        if name not in ("context", "resizework", "resizestate"):
            continue
        for o in range(0, 4096 - 3, 2):
            p = struct.unpack_from("<HH", blob, o)
            if p in pairs:
                seen.setdefault("%dx%d" % p, []).append(hex(addr + o))
    st["where_sizes_occur"] = {k: v[:40] for k, v in sorted(seen.items())}
    if any(n in ("context", "resizework", "resizestate") for n, _ in pages.values()):
        out["scaler_state"] = st
    # The display (modding/FX3_PORT.md): the panel's aspect code comes from a panel-type byte (0x1e0050: type 2 is a 4:3 panel, 3 a 3:2 panel,
    # 1 a 16:9 one); rear output 0x14909e4 (4 or more counts as 1), second output 0x1490b14 (2 or more counts as 2). A 16:9 picture is letterboxed
    # (fit words 3) at width x n/d (the ratio function 0x1df794, the A7 IV's instruction form). While De-Squeeze Display is on, 0x1df680 is used
    # instead, with one ratio per factor; 2.0x also crops the input to its centre 4:3 (0x5faf04) unless the screen step turned it off.
    disp = {}
    types = mem(0x14909E4, 1), mem(0x1490B14, 1)
    if None not in types:
        name = {1: "16:9", 2: "4:3", 3: "3:2"}
        rear, second = (1 if types[0][0] >= 4 else types[0][0]), min(types[1][0], 2)
        disp["panel_types"] = {"rear_0x14909e4": types[0][0], "rear_aspect": name.get(rear, "none"), "second_0x1490b14": types[1][0], "second_aspect": name.get(second, "none")}
    fit, con = mem(0x1DF4A8, 8), mem(0x1DF7B8, 8)
    if fit is not None and con is not None:
        n, d = con[2], con[4]
        known = {(9, 16): "16:9, stock", (2, 3): "3:2 (screen step applied)"}
        form = con[:2] == bytes.fromhex("4ff0") and con[3] == 0x0E and con[5] == 0x20 and con[6:] == bytes.fromhex("07e0")
        disp["fit_16x9_picture"] = {"on_4x3_panel": struct.unpack_from("<I", fit, 0)[0], "on_3x2_panel": struct.unpack_from("<I", fit, 4)[0]}
        disp["ratio_constants"] = {"address": "0x1df7b8", "words": con.hex(), "height": "width x %d/%d" % (n, d),
                                   "state": known.get((n, d), "unknown") if form else "not the expected instructions"}
    rows = {}
    for t in (0xD2E510, 0xD2E588, 0xD2E600):
        b = mem(t, 0x78)
        if b is not None:
            rows[hex(t)] = {"row%d" % r: list(struct.unpack_from("<4H", b, 8 * (5 * r + 3))) for r in range(3)}
    if rows:
        disp["frame_rectangles_16x9_picture"] = rows
    dsq = {}
    for label, a_n, a_d in (("1.3x", 0x1DF700, 0x1DF704), ("1.5x", 0x1DF708, 0x1DF70C), ("1.65x", 0x1DF710, 0x1DF714), ("2.0x", 0x1DF6A8, 0x1DF6AC)):
        wn, wd = mem(a_n, 4), mem(a_d, 2)
        if wn is not None and wd is not None:
            good = wn[:2] == bytes.fromhex("4ff0") and wn[3] == 0x0A and wd[1] == 0x25
            dsq[label] = "%d/%d" % (wn[2], wd[0]) if good else "not the expected instructions"
    if dsq:
        stock = {"1.3x": "45/104", "1.5x": "3/8", "1.65x": "15/44", "2.0x": "3/8"}
        new = {"1.3x": "20/39", "1.5x": "4/9", "1.65x": "40/99", "2.0x": "1/3"}
        disp["desqueeze_ratios_16x9_picture"] = dict(dsq, state="stock" if dsq == stock else "3:2 picture (screen step applied)" if dsq == new else "mixed or unknown")
    cr = mem(0x5FAF36, 2), mem(0x5FAF68, 2)
    if None not in cr:
        imm = {c[0] if c[1] == 0x28 else None for c in cr}
        disp["crop_2x"] = "on (stock: the centre 4:3 is shown)" if imm == {4} else "off (screen step: the whole frame)" if imm == {5} else "not the expected instructions"
    sw = ref.get("screen_words", [])
    if sw and all(mem(int(w["address"], 16), 4) is not None for w in sw):
        got = [mem(int(w["address"], 16), 4).hex() for w in sw]
        disp["screen_words"] = {"stock": sum(g == w["stock"] for g, w in zip(got, sw)), "new": sum(g == w["new"] for g, w in zip(got, sw)),
                                "other": sum(g not in (w["stock"], w["new"]) for g, w in zip(got, sw))}
    gfw = mem(0x10A8EB4, 4)
    if gfw is not None:                           # SET_ANAMO_DESQUEEZE_SCALE's store (0x2f4ac0): what the menu last sent; meaning of the values not traced
        disp["menu_desqueeze_scale_0x10a8eb4"] = struct.unpack_from("<I", gfw)[0]
    if disp:
        out["display"] = disp
    # The camera core's periodic log record (A7S III 0x1401064; FX3 0x13d7f48). It is the one place a dump shows state from BEFORE the USB
    # session: at dump time the sensor sleeps (drive mode 1) and the live state is the session's. +4 a time count, +8 the drive mode id,
    # +0xb [context+0x364], +0xc [context+0x368], +0xd a core state number, +0xe [context+0x2a4]. On the A7S III state 7 was standby, 9 recording.
    rec = mem(0x13D7F48, 0x10)
    if rec is not None:
        out["core_log_record"] = {"time": struct.unpack_from("<I", rec, 4)[0], "drive_mode": hex(struct.unpack_from("<H", rec, 8)[0]), "context_0x364": rec[0xB],
                                  "context_0x368": rec[0xC], "state": rec[0xD], "context_0x2a4": rec[0xE]}
    return out


# ------------------------------------------------------------ the A7 IV runner, pointed at this camera

def known_answer(session, camera):
    want = (S3 / "DeviceInfo.xml").read_bytes()
    there, data = R.read(camera, R.KNOWN_PATH)
    if not there or data != want:
        raise c.StopTest("DeviceInfo.xml is not the file of the 7.02 update (%s); nothing else is sent"
                         % ("the camera returned no file" if not there else "%d bytes, SHA-256 %s" % (len(data), c.sha256(data)[:16])))
    session.say("Known-answer read: DeviceInfo.xml equals the 7.02 file (the A7 IV, A7S III and ZV-E1 have the same file: the helper itself checks which camera this is)")


def run_helper(data):
    """What loading the uploaded bytes gives on a model FX3: the real AArch64 code in Unicorn if it is installed, else a canned text."""
    if WHICH in WRITE_STEPS:                        # the write libraries are emulated by helper_fx3/emu_fx3_write.py; here only the session flow is simulated
        text = "readcheck 1 level %s\neuid 0\n== level %s\nDONE: every site holds the target bytes (canned)\n== done, bytes written before this line: 0\n" % (WHICH[1:], WHICH[1:])
        return text.encode(), "canned"
    try:
        import emu_fx3
    except Exception:
        text = "fx3read fx3read_v2 %s for ILME-FX3 7.02; read-only\n== file /proc/version\nLinux (simulated)\n\n== end 18 bytes\n== summary\nVERDICT READY (canned)\n== done\n" % WHICH
        return text.encode(), "canned"
    r, text = emu_fx3.run(bytes(data))
    if r.bad:
        raise AssertionError("the emulated helper stopped: %s" % r.bad)
    return text.encode(), "emulated"


def make_sim(lib, files=None, fault=None):
    sim = _make_sim(lib, files, fault)
    if "/usr/share/pmbp/DeviceInfo.xml" not in (files or {}):
        sim.fs["/usr/share/pmbp/DeviceInfo.xml"] = (S3 / "DeviceInfo.xml").read_bytes()
    return sim


def use(which):
    """Point the runner's module state at one of this camera's two libraries."""
    global WHICH
    WHICH = which
    name, sha = PINS[which]
    if not (S3 / name).is_file():
        raise SystemExit("%s is not in this kit%s. Nothing was sent." % (name, " (the write steps are not published yet)" if which in WRITE_STEPS else ""))
    R.LEVEL, R.DESIGN, R.LIB, R.LIB_SHA256 = LEVELS[which], "og4k_data_v1", S3 / name, sha
    R.check_result, R.known_answer, R.run_helper, R.make_sim = check_result, known_answer, run_helper, make_sim
    R.KNOWN_LIBS = known_libs()
    c.EXPECTED_FIRMWARE = FIRMWARE
    return R.library()


_make_sim = R.make_sim


def selftest(lib):
    done = []

    def check(cond, what):
        if not cond:
            raise AssertionError("self-test failed: " + what)
        done.append(what)

    W, D = "SET_FILE2", "FILE_DELETE2"
    s, sim, stopped = R.simulate(lib, R.body_run)
    r = s.results.get("ct6", {})
    check(not stopped and not sim.unexpected and R.sent(s).count(W) == 1 and R.sent(s).count(D) == 1, "normal run: one write, one delete, nothing off the list")
    check(R.sent(s).index(D) < len(R.sent(s)) - 2 and R.sent(s)[-1] == "GET_FILE2", "normal run: the delete comes before the result is read")
    check(R.LIB_PATH.decode() not in sim.fs and sim.loads == 1, "normal run: the library was loaded once and is gone afterwards")
    f = r.get("result", {}).get("s3", {})
    if WHICH in WRITE_STEPS:
        check(f.get("ok") and r["result"]["header_ok"], "normal run: the step's result is read as DONE")
    else:
        check(f.get("ready") and not f.get("identity_differs"), "normal run: the %s helper reports a stock 7.02 camera as READY" % sim.how)
    if sim.how == "emulated":
        check(len(f["coprocessor_sites"]) == len(expected()["cp_sites"]) and f["avcam_stock"] == 101 and len(f["libmpr_sites"]) == expected()["lm_sites"] == 6,
              "normal run: every coprocessor site, 6 libmpr (4 rows, 2 MP4 header heights) and 101 av-cam sites are reported")
        if WHICH == "dump":
            d = f.get("decoded", {})
            check(d.get("matrix_equals_file") and len(d.get("stored_records", {})) == 40 and d.get("size_table"), "dump: the pages decode (matrix, 40 records, size table)")
            dp = d.get("display", {})
            check(dp.get("ratio_constants", {}).get("state") == "16:9, stock" and dp.get("fit_16x9_picture") == {"on_4x3_panel": 3, "on_3x2_panel": 3}
                  and all(v == {"row0": [0, 60, 640, 360], "row1": [0, 38, 640, 404], "row2": [0, 60, 640, 360]} for v in dp.get("frame_rectangles_16x9_picture", {"x": 0}).values())
                  and len(dp.get("frame_rectangles_16x9_picture", {})) == 3 and dp.get("desqueeze_ratios_16x9_picture", {}).get("state") == "stock"
                  and dp.get("crop_2x", "").startswith("on") and dp.get("screen_words") == {"stock": 30, "new": 0, "other": 0} and "panel_types" in dp,
                  "dump: the display pages decode (stock ratio 9/16, fit words, the three tables' rows, de-squeeze ratios and crop, the 30 screen words, panel types)")
    s, sim, stopped = R.simulate(lib, R.body_run, files={R.LIB_PATH.decode(): b"someone else's"})
    check(stopped and W not in R.sent(s) and D not in R.sent(s), "a foreign libJit.so on the camera: stops, nothing written, nothing deleted")
    s, sim, stopped = R.simulate(lib, R.body_run, files={"/tmp_wbshd/readcheck_result.txt": b"old"})
    check(stopped and W not in R.sent(s), "a result already on the RAM disk: stops, nothing written")
    s, sim, stopped = R.simulate(lib, R.body_run, files={"/tmp/jbusy": b""})
    check(stopped and W not in R.sent(s), "/tmp/jbusy present: stops, nothing written")
    s, sim, stopped = R.simulate(lib, R.body_run, files={"/usr/share/pmbp/DeviceInfo.xml": b"<other camera/>"})
    check(stopped and len(R.sent(s)) == 2, "another DeviceInfo.xml: stops after the known-answer read")
    s, sim, stopped = R.simulate(lib, R.body_run, fault="load")
    check(stopped and R.sent(s).count(D) == 1 and R.LIB_PATH.decode() not in sim.fs, "a camera that cannot load the library: it is still deleted")
    # a library an earlier session left on the service partition (it survives a cold boot): one of this kit's is deleted and the run goes on
    lp = R.LIB_PATH.decode()
    other = next((S3 / n).read_bytes() for k, (n, sha) in sorted(PINS.items()) if k != WHICH and (S3 / n).is_file())
    for left, what in ((other, "another step's library"), (lib, "this step's own library")):
        s, sim, stopped = R.simulate(lib, R.body_run, files={lp: left})
        names, lr = R.sent(s), s.results["ct6"].get("leftover_removed") or {}
        check(not stopped and not sim.unexpected and names.count(D) == 2 and names.count(W) == 1 and names.index(D) < names.index(W) and lp not in sim.fs
              and sim.loads == 1 and lr.get("gone") and lr.get("sha256") == c.sha256(left) and s.results["ct6"]["library_on_camera_after"] is False,
              "%s left on the camera: deleted first, then the normal run (one write, loaded once, gone afterwards)" % what)
    s, sim, stopped = R.simulate(lib, R.body_run, files={lp: other}, fault="sticky")
    check(stopped and W not in R.sent(s) and R.sent(s).count(D) == 1 and sim.fs.get(lp) == other, "a left library the camera will not delete: stops, nothing written")
    named = b"a file named with --remove-library"
    saved = dict(R.KNOWN_LIBS)
    try:
        R.KNOWN_LIBS[c.sha256(named)] = "the file named with --remove-library"
        s, sim, stopped = R.simulate(lib, R.body_run, files={lp: named})
        check(not stopped and R.sent(s).count(D) == 2 and R.sent(s).count(W) == 1 and lp not in sim.fs, "--remove-library with the file's SHA-256: deleted, then the normal run")
        s, sim, stopped = R.simulate(lib, R.body_run, files={lp: named + b"!"})
        check(stopped and W not in R.sent(s) and D not in R.sent(s) and c.sha256(named + b"!") in stopped, "--remove-library with another SHA-256: stops, nothing deleted, the file's SHA-256 is shown")
    finally:
        R.KNOWN_LIBS.clear()
        R.KNOWN_LIBS.update(saved)
    s, sim, stopped = R.simulate(lib, R.body_remove_only, files={lp: other})
    check(not stopped and R.sent(s).count(D) == 1 and W not in R.sent(s) and lp not in sim.fs and s.results["ct6"]["library_on_camera_after"] is False,
          "--remove-only: deletes another step's library of this kit too, writes nothing")
    s, sim, stopped = R.simulate(lib, R.body_remove_only, files={lp: b"someone else's"})
    check(stopped and D not in R.sent(s) and lp in sim.fs, "--remove-only: leaves a file that is none of this kit's")
    check(set(EARLIER_LIBS) <= set(R.KNOWN_LIBS) and all(sha in R.KNOWN_LIBS for _, sha in PINS.values()) and not set(EARLIER_LIBS) & {sha for _, sha in PINS.values()},
          "every library of this kit, current (%d) and earlier (%d), is one a run may delete" % (len(PINS), len(EARLIER_LIBS)))
    check(len(R.refusals(lib)) == 15, "the guard refuses the 15 listed packets (changed library, other paths, backup, flash and debug writes ...)")
    return done


def report(session, facts, which):
    f = facts["s3"]
    if which in WRITE_STEPS:
        lines = ["FX3 7.02 step %s: %s" % (which, f["what"]), "OUTCOME: %s" % f["outcome"], str(f["outcome_line"])] + ["  " + ln for ln in f["problem_lines"]]
        session.save_bytes("fx3_report.txt", ("\n".join(lines) + "\n").encode())
        for ln in lines:
            session.say(ln)
        return
    note = state_4224_note(f)
    lines = ["FX3 7.02 %s, %s" % (which, time.strftime("%Y-%m-%d %H:%M:%S")), f["header"], f["verdict"]] + ([note] if note else []) + [
             "identity: %d same, %d differ" % (f["identity_same"], f["identity_differs"]),
             "kernel: %s" % f["kernel_version"], "command line: %s" % f["kernel_command_line"]]
    for s in f["coprocessor_sites"]:
        lines.append("  coprocessor %-16s %s len %-4d %s%s" % (s["name"], s["address"], s["length"], s["state"], "" if s["shown"] is None else "  (" + s["shown"] + ")"))
    lines += ["  " + ln for ln in f["libmpr_sites"]] + ["  " + ln for ln in f["avcam_guards"]]
    lines.append("  av-cam.bin sites: %d stock, %d target, %d other" % (f["avcam_stock"], f["avcam_target"], f["avcam_other"]))
    lines += ["problem lines:"] + ["  " + ln for ln in f["problem_lines"]] if f["problem_lines"] else ["no problem lines"]
    d = f.get("decoded")
    if d:
        sr = d.get("sensor_registers")
        if sr:
            lines.append("sensor register shadow: closest matrix column %d (%d of %d rows equal; modes %s); window rows 6/7/24/42 hold %s"
                         % (sr["closest_column"], sr["rows_equal_per_column"][sr["closest_column"]], sr["rows"], ", ".join(sr["modes_using_it"]), sr["window_rows_6_7_24_42"]))
        lines.append("register matrix equals the file: %s" % d.get("matrix_equals_file"))
        zero = [m for m, v in d.get("stored_records", {}).items() if v["all_zero"]]
        same = [m for m, v in d.get("stored_records", {}).items() if not v["bytes_differing_from_emulation"]]
        lines.append("stored drive-parameter records: %d read, %d equal to the emulated ones, %d all zero" % (len(d.get("stored_records", {})), len(same), len(zero)))
        v = d.get("stored_records", {}).get("0x8c0")
        if v:
            lines.append("  mode 0x8c0: %d bytes differ from the emulation at %s" % (v["bytes_differing_from_emulation"], ", ".join(v["offsets"])))
        if d.get("size_table"):
            lines.append("movie size table: " + "; ".join("%dx%d id %#x" % tuple(r) for r in d["size_table"]))
        ss = d.get("scaler_state")
        if ss:
            lines.append("second scaler state (addresses ported from the A7S III's; the block and input words are not confirmed):")
            bl = ss.get("second_scaler_block")
            if bl:
                lines.append("  block %s: words %s -> takes %s x %s from %s" % (bl["address"], bl["words"], bl["size"][0], bl["size"][1], bl["start"]))
                if bl["words"][:2] == [4240, 2816]:      # the 4224x2816 state's front end (ogh2816_fx3_v1)
                    lines.append("    the 4224x2816 state as designed: words %s = 4224 x 2816 from (8, 0), scale 1: %s"
                                 % (FIT_4224, "EQUAL" if bl["words"] == FIT_4224 else "NOT equal"))
            if "second_scaler_input" in ss:
                lines.append("  input words: %s" % ss["second_scaler_input"])
            rw = ss.get("resize_work")
            if rw:
                lines.append("  resize work: pixel aspect %d/4096, scales %d and %d /4096, zoom %d/65536" % (rw["pixel_aspect_q12"], rw["scale_h_q12"], rw["scale_v_q12"], rw["zoom_q16"]))
            if "division_units" in ss:
                lines.append("  division units: %s" % ss["division_units"])
            for k, v in ss.get("where_sizes_occur", {}).items():
                lines.append("  %s at %s%s" % (k, ", ".join(v[:10]), " ..." if len(v) > 10 else ""))
        cl = d.get("core_log_record")
        if cl:
            lines.append("camera core's last log record before this session: time %d, drive mode %s, values %d / %d / %d (on the A7S III state 7 = standby, 9 = recording)"
                         % (cl["time"], cl["drive_mode"], cl["context_0x364"], cl["state"], cl["context_0x2a4"]))
        dp = d.get("display")
        if dp:
            lines.append("display (what the screen step changes):")
            if "panel_types" in dp:
                t = dp["panel_types"]
                lines.append("  panel types: rear %d (%s), second output %d (%s)" % (t["rear_0x14909e4"], t["rear_aspect"], t["second_0x1490b14"], t["second_aspect"]))
            if "ratio_constants" in dp:
                r, ft = dp["ratio_constants"], dp["fit_16x9_picture"]
                lines.append("  a 16:9 picture: height = %s (%s); fit word on a 4:3 panel %d, on a 3:2 panel %d" % (r["height"], r["state"], ft["on_4x3_panel"], ft["on_3x2_panel"]))
            if "desqueeze_ratios_16x9_picture" in dp:
                q = dp["desqueeze_ratios_16x9_picture"]
                lines.append("  De-Squeeze Display ratios: 1.3x %s, 1.5x %s, 1.65x %s, 2.0x %s (%s); 2.0x crop %s" % (q.get("1.3x"), q.get("1.5x"), q.get("1.65x"), q.get("2.0x"), q["state"], dp.get("crop_2x")))
            if "screen_words" in dp:
                lines.append("  screen step words: %(stock)d stock, %(new)d applied, %(other)d other" % dp["screen_words"])
            if "menu_desqueeze_scale_0x10a8eb4" in dp:
                lines.append("  menu de-squeeze scale value: %d" % dp["menu_desqueeze_scale_0x10a8eb4"])
            for t, rw in dp.get("frame_rectangles_16x9_picture", {}).items():
                lines.append("  frame table %s: row 0 %s, row 1 %s, row 2 %s" % (t, rw["row0"], rw["row1"], rw["row2"]))
    session.save_bytes("fx3_report.txt", ("\n".join(lines) + "\n").encode())
    for ln in lines[:8] + lines[-6:]:
        session.say(ln)


def state_4224_note(f):
    """One line when a check or dump was taken with the 4224x2816 state applied. This helper knows the 3840x2560 state's bytes only, so its
    verdict then reads NOT READY; the output-size word is the one place where it shows the other state's value."""
    oz = next((s for s in f.get("coprocessor_sites", []) if s["name"] == "outsize"), None)
    if not oz or oz.get("shown") != struct.pack("<HH", 4224, 2816).hex():
        return None
    return ("NOTE: the output size word holds 4224 x 2816: the 4224x2816 state is applied. This helper compares with the 3840x2560 state, so NOT READY is "
            "what it says here; each step of the apply checked its own bytes.")


def last_saved_sha():
    """The SHA-256 of the result the newest saved session of this kit fetched, or None."""
    root = c.PRIVATE_ROOT
    if not root.is_dir():
        return None
    for folder in sorted((p for p in root.iterdir() if p.is_dir() and p.name.startswith("CT6_")), reverse=True):
        try:
            return json.loads((folder / "manifest.json").read_text(encoding="utf8"))["results"]["ct6"]["result"]["sha256"]
        except (OSError, KeyError, TypeError, ValueError):
            continue
    return None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("which", choices=sorted(PINS))
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--go", action="store_true")
    ap.add_argument("--remove-only", action="store_true")
    ap.add_argument("--clear-result", metavar="SHA256", help="first delete the result file of an earlier run from the RAM disk, only if its SHA-256 is this")
    ap.add_argument("--remove-library", metavar="SHA256", help="a libJit.so left on the camera's service partition that is none of this kit's: delete it first, "
                                                               "only if its SHA-256 is this (a library of this kit is deleted without being named)")
    ap.add_argument("--firmware-shown")
    ap.add_argument("--writes-memory", action="store_true", help="needed for a write step (L5, L6, O5, L16, L17, L19, L20, N19, S16, S17, P29, P30, I19, I20, and the 4224x2816 state's H, D, K, J, R steps): it changes the running camera's memory")
    a = ap.parse_args()
    if a.which in WRITE_STEPS and a.go and not (a.dry_run or a.selftest) and not a.writes_memory:
        raise SystemExit("%s is a write step: %s. It needs --writes-memory as well. Use fx3_apply.py. Nothing was sent." % (a.which, WRITE_STEPS[a.which][2]))
    if a.remove_library:
        if not re.fullmatch(r"[0-9a-fA-F]{64}", a.remove_library):
            raise SystemExit("--remove-library takes the 64 hexadecimal digits of the file's SHA-256 (the stopped run prints them). Nothing was sent.")
        EXTRA_LIBS[a.remove_library.lower()] = "the file named with --remove-library"
    lib = use(a.which)
    if a.dry_run or a.selftest:
        if a.selftest:                              # --dry-run and --selftest win over --go (the launchers always pass --go): nothing is sent
            for line in selftest(lib):
                print("PASS  " + line)
            print("all checks passed; nothing was sent to any device")
        else:
            print("\n".join(R.dry_run_lines(lib)))
        return
    if not a.go or a.firmware_shown != FIRMWARE:
        raise SystemExit("A live run needs --go and --firmware-shown %s (the version the camera's menu shows). Nothing was sent." % FIRMWARE)
    R.refusals(lib)
    selftest(lib)                                   # the flow must pass on the simulated camera on the day, before the real one
    import ct1_stage2_service as service
    # A result left on the RAM disk by the run before stops a new run (seen on the first A7S III session, whose runner this is). Without --clear-result the newest
    # result saved on this PC is named: the runner deletes the camera's file only if its SHA-256 is that one, i.e. only a result already here.
    R.CLEAR_SHA = a.clear_result or last_saved_sha()
    body = R.body_remove_only if a.remove_only else R.body_run
    with c.Session("remove_only" if a.remove_only else "fx3_%s" % a.which, test="CT6") as session:
        session.results.update(firmware_shown_on_camera=a.firmware_shown, model=MODEL, which=a.which, library_sha256=PINS[a.which][1],
                               pc={"platform": platform.platform(), "python": sys.version.split()[0]})
        inner = service.connect(session)
        try:
            R.service_session(session, inner, lambda cam: body(session, cam, lib), lib)
            facts = session.results.get("ct6", {}).get("result")
            if facts and not a.remove_only:
                pages = facts.pop("_pages", {})
                for addr, (name, blob) in sorted(pages.items()):
                    session.save_bytes("cp_%s_%08x.bin" % (name, addr), blob)
                report(session, facts, a.which)
        finally:
            time.sleep(3)
            c.print_pnp(session, "after the stop request")
            out = session.results.get("ct6", {})
            print("Library sent: %s. On the camera now: %s." % (
                "yes" if out.get("library_sent") else "no",
                {False: "no (confirmed)", True: "YES", None: "not sent" if not out.get("library_sent") and not a.remove_only else "UNKNOWN"}[out.get("library_on_camera_after")]))
            lr = out.get("leftover_removed")
            if lr:
                print("A library an earlier session had left on the camera (%s) was %s." % (lr["name"], "deleted first" if lr["gone"] else "NOT deleted: it is still there"))
            if a.which in WRITE_STEPS:
                print("This was a WRITE step. A cold boot (battery out for 10 seconds) undoes everything written. On the A7S III, which runs the same coprocessor software, the power switch did too: keep the camera on between steps.")
            else:
                print("Nothing on the camera was changed. Unplug and replug the USB cable before another run; a cold boot (battery out) clears the result file.")


if __name__ == "__main__":
    main()
