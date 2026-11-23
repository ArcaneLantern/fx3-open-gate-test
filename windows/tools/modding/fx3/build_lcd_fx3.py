"""Design lcd32dsq_fx3_v1: the FX3 7.02 rear screen shows the open-gate live view at 3:2, and the FX3's own Anamorphic Desqueeze
display stays right for that picture.

  work\\venv\\Scripts\\python.exe -I -B build\\build_lcd_fx3.py        writes modding/designs/lcd32dsq_fx3_v1.json

The open-gate live view is a 16:9 frame (picture aspect code 2) that holds the whole 3:2 sensor area squeezed vertically, as on the
A7S III. Three groups of words, all in the FX3's coprocessor image (cpapp-b.bin, loaded at 0x108000; changed in RAM only):

(a) The picture-ratio function 0x1df794 (the A7 IV's form, not the A7S III's): with fit mode 3 (letterbox) it gives a 16:9 picture the
    height width x 9/16. 9/16 -> 2/3, the method of the A7S III's working lcdratio32_s3_v1:
      0x1df7b8  mov.w lr, #9  -> #2          0x1df7bc  movs r0, #16 -> #3
    The function's own 3:2 case (0x1df7b0) uses 2 and 3 and adds 3 to the width first. An 800 x 600 (4:3) panel gets 534 rows from
    row 33; on a 720 x 480 (3:2) panel the height 482 is more than the panel, so the function gives the whole panel. The fit words for a
    16:9 picture (0x1df4a8 / 0x1df4ac: 3 on a 4:3 and on a 3:2 panel) are left alone: they are what makes the constants count.
(b) The frame widgets' rectangle tables (cpActAfWindow 0xd2e510, cpActAfWindowRemoteSend 0xd2e588, cpActTrackingFrame 0xd2e600; the frame
    check 0x128438 compares the live-view rectangle with an entry within 5 units of a 640 x 480 grid): the 16:9 column of
      row 0 (rear output on a 4:3 panel; stock (0, 60, 640, 360) = 800 x 450 letterbox) and row 2 (the second output) -> (0, 26, 640, 428)
      row 1 (rear output on a 3:2 panel; stock (0, 38, 640, 404) = 720 x 405 letterbox)                               -> (0, 0, 640, 480)
    so the frames are drawn on either panel shape. The FX3's panel shape is read from backup memory at run time (byte 0x14909e4); the
    firmware's display table has 800 x 600 as its only 1.44M-dot geometry, so a 4:3 panel is expected (modding/FX3_PORT.md).
(c) The de-squeeze calculator 0x1df680, used instead of (a) while Anamorphic Desqueeze is on (0x60eb6e): full width, centred,
    height = (width x n + 2d) / d & ~3 with fixed per-factor ratios for a 16:9 picture. For a picture that is 3:2:
      1.3x   0x1df700 / 0x1df704  45/104 -> 20/39   (shown 1.95:1)
      1.5x   0x1df708 / 0x1df70c   3/8   ->  4/9    (2.25:1)
      1.65x  0x1df710 / 0x1df714  15/44  -> 40/99   (2.475:1)
      2.0x   0x1df6a8 / 0x1df6ac   3/8   ->  1/3    (3:1, the whole 3:2 frame: the owner's choice, 2026-11-24)
    and the 2.0x centre crop is turned off: 0x5faf04 crops the input to a centre 4:3 (width = (4h + 6) / 3) when the code is 4, on both
    of its paths; the compares at 0x5faf36 and 0x5faf68 go from `cmp r0, #4` to `cmp r0, #5` (the code is always below 5: 0x5f5442).
    The 17:9 ratios, the HDMI manual-layout copy 0x1dfb18 and the fit words stay stock.

While applied, every 16:9 picture is shown at 3:2 on the rear screen and the de-squeeze ratios are those of a 3:2 picture (other movie
formats look wrong there until the screen step is put back); HDMI's own layout is unchanged. Nothing here talks to a camera.
Checked by build/emu_lcd_fx3.py (Unicorn, the FX3's own functions) and build/lcd_fx3_qemu.py (qemu-arm, the two leaf calculators).
"""
import hashlib
import json
import struct
import sys
from pathlib import Path

from capstone import Cs, CS_ARCH_ARM, CS_MODE_THUMB

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import locate_file  # noqa: E402

NAME = "lcd32dsq_fx3_v1"
B = 0x108000
FX = locate_file.locate("fx3_702", "cpapp-b.bin").read_bytes()
S3 = locate_file.locate("a7s3_501", "cpapp-b.bin").read_bytes()
SHA = "c90d00d807874a5309dc1b65b203287e83608ceee513cc57b53409333fb6bcba"
MD = Cs(CS_ARCH_ARM, CS_MODE_THUMB)
fx = lambda a, n: FX[a - B:a - B + n]

RATIO_FN, FIT_FN, DSQ_FN, CROP_FN, FRAME_CHECK = 0x1DF794, 0x1DF458, 0x1DF680, 0x5FAF04, 0x128438
TABLES = (("cpActAfWindow (focus area frames)", 0xD2E510, 0xD4D744),
          ("cpActAfWindowRemoteSend (the same frames for a remote viewer)", 0xD2E588, 0xD4D7BC),
          ("cpActTrackingFrame (tracking and face frames)", 0xD2E600, 0xD4D834))
TABLE_LEN = 0x78
RECT_169 = {0: (0, 60, 640, 360), 1: (0, 38, 640, 404), 2: (0, 60, 640, 360)}
RECT_NEW = {0: (0, 26, 640, 428), 1: (0, 0, 640, 480), 2: (0, 26, 640, 428)}
ROWS = {0: "rear output, 4:3 panel", 1: "rear output, 3:2 panel", 2: "second output"}
# (address, stock instruction, new instruction, what)
CODE = [(0x1DF7B8, ("mov.w", "lr, #9"), ("mov.w", "lr, #2"), "picture-ratio function, 16:9 picture: numerator 9 -> 2"),
        (0x1DF7BC, ("movs", "r0, #0x10"), ("movs", "r0, #3"), "picture-ratio function, 16:9 picture: denominator 16 -> 3"),
        (0x1DF700, ("mov.w", "sl, #0x2d"), ("mov.w", "sl, #0x14"), "de-squeeze 1.3x, 16:9 picture: 45 -> 20"),
        (0x1DF704, ("movs", "r5, #0x68"), ("movs", "r5, #0x27"), "de-squeeze 1.3x: 104 -> 39 (height = width x 20/39: 1.95:1)"),
        (0x1DF708, ("mov.w", "sl, #3"), ("mov.w", "sl, #4"), "de-squeeze 1.5x, 16:9 picture: 3 -> 4"),
        (0x1DF70C, ("movs", "r5, #8"), ("movs", "r5, #9"), "de-squeeze 1.5x: 8 -> 9 (4/9: 2.25:1)"),
        (0x1DF710, ("mov.w", "sl, #0xf"), ("mov.w", "sl, #0x28"), "de-squeeze 1.65x, 16:9 picture: 15 -> 40"),
        (0x1DF714, ("movs", "r5, #0x2c"), ("movs", "r5, #0x63"), "de-squeeze 1.65x: 44 -> 99 (40/99: 2.475:1)"),
        (0x1DF6A8, ("mov.w", "sl, #3"), ("mov.w", "sl, #1"), "de-squeeze 2.0x (the default ratio, used only by code 4): 3 -> 1"),
        (0x1DF6AC, ("movs", "r5, #8"), ("movs", "r5, #3"), "de-squeeze 2.0x: 8 -> 3 (1/3: 3:1, the whole 3:2 frame)"),
        (0x5FAF36, ("cmp", "r0, #4"), ("cmp", "r0, #5"), "2.0x centre crop, first path: code 4 -> 5 (never): no crop"),
        (0x5FAF68, ("cmp", "r0, #4"), ("cmp", "r0, #5"), "2.0x centre crop, second path: code 4 -> 5 (never): no crop")]
ENC = {("mov.w", "lr, #2"): "4ff0020e", ("movs", "r0, #3"): "0320", ("mov.w", "sl, #0x14"): "4ff0140a", ("movs", "r5, #0x27"): "2725",
       ("mov.w", "sl, #4"): "4ff0040a", ("movs", "r5, #9"): "0925", ("mov.w", "sl, #0x28"): "4ff0280a", ("movs", "r5, #0x63"): "6325",
       ("mov.w", "sl, #1"): "4ff0010a", ("movs", "r5, #3"): "0325", ("cmp", "r0, #5"): "0528"}
rect = lambda r: struct.pack("<4H", *r)


def insn(data, addr):
    i = next(MD.disasm(data, addr), None)
    return (i.mnemonic, i.op_str, i.size) if i else None


def check_context():
    """Facts the design rests on, each read from the image."""
    assert hashlib.sha256(FX).hexdigest() == SHA
    # the ratio function's own 3:2 case, and the 16:9 case at the constants
    assert insn(fx(0x1DF7B0, 4), 0x1DF7B0)[:2] == ("mov.w", "lr, #2") and insn(fx(0x1DF7B4, 2), 0x1DF7B4)[:2] == ("movs", "r0, #3")
    assert FX.count(fx(RATIO_FN, 0x40)) == 1 and FX.count(bytes.fromhex("4ff0090e102007e0")) == 1
    # the A7S III's form of the constants does not exist here (lcdratio32_s3_v1's words cannot be reused)
    assert FX.count(bytes.fromhex("4ff0090e08bf1020")) == 0 and S3.count(bytes.fromhex("4ff0090e08bf1020")) == 1
    # fit words: a 16:9 picture is letterboxed on a 4:3 (code 0) and a 3:2 (code 1) panel
    assert struct.unpack("<6I", fx(0x1DF4A8, 24)) == (3, 3, 0, 0, 0, 2)
    # the frame tables are the A7S III's, byte for byte, and hold the stock 16:9 entries
    for _, t, t3 in TABLES:
        assert fx(t, TABLE_LEN) == S3[t3 - B:t3 - B + TABLE_LEN]
        for row, r in RECT_169.items():
            assert fx(t + 8 * (5 * row + 3), 8) == rect(r)
    # the frame check reads these tables (movw/movt 0xd2e510 in 0x128438) on a 640 x 480 grid with tolerance 5
    assert fx(0x12852A, 4) == bytes.fromhex("4ef21052") and fx(0x128532, 4) == bytes.fromhex("c0f2d202")
    assert struct.unpack("<d", fx(0x128600, 8))[0] == 640.0 and struct.unpack("<d", fx(0x1285F8, 8))[0] == 480.0
    assert fx(0x12854A, 4) == bytes.fromhex("b1ee041b")                    # vmov.f64 d1, #5.0
    # the de-squeeze code is checked < 5 before it is stored (VdfInputCmdSetDeSqueeze's check 0x5f5442: ldrb r1, [r0]; cmp r1, #5; it lo ...;
    # blo accept), so `cmp r0, #5` in the crop function never matches
    assert fx(0x5F5452, 6) == bytes.fromhex("0178052938bf")


def design():
    check_context()
    sites, words = [], {}
    for a, old, new, what in CODE:
        got = insn(fx(a, 4), a)
        assert got[:2] == old, (hex(a), got, old)
        enc = bytes.fromhex(ENC[new])
        assert len(enc) == got[2] and insn(enc + b"\x00\x00", a)[:2] == new, (hex(a), new)
        w = a & ~3
        cur = bytearray(words.get(w, fx(w, 4)))
        cur[a - w:a - w + len(enc)] = enc
        words[w] = bytes(cur)
        words.setdefault(("what", w), []).append(what)
    for w in sorted(k for k in words if isinstance(k, int)):
        sites.append({"ram_address": hex(w), "old": fx(w, 4).hex(), "new": words[w].hex(), "note": "; ".join(words[("what", w)])})
    for what, t, t3 in TABLES:
        for row in (0, 1, 2):
            e = t + 8 * (5 * row + 3)
            old, new = rect(RECT_169[row]), rect(RECT_NEW[row])
            for off, part in ((0, "x, y"), (4, "w, h")):
                if old[off:off + 4] != new[off:off + 4]:
                    sites.append({"ram_address": hex(e + off), "old": old[off:off + 4].hex(), "new": new[off:off + 4].hex(),
                                  "note": "%s, row %d (%s), 16:9 column, %s: %s to %s (A7S III %#x)" % (what, row, ROWS[row], part, RECT_169[row], RECT_NEW[row],
                                                                                                  t3 + 8 * (5 * row + 3) + off)})
    G = lambda a, n, note: {"ram_address": hex(a), "bytes": fx(a, n).hex(), "note": note + ", as in the file"}
    guards = [G(RATIO_FN, 16, "first 16 bytes of the picture-ratio function 0x1df794"),
              G(0x1DF7A8, 16, "the ratio function's case table and its own 3:2 case (lr 2, r0 3)"),
              G(0x1DF7C0, 16, "the ratio function after the 16:9 case (1:1 and 17:9 cases)"),
              G(FIT_FN, 16, "first 16 bytes of the fit-mode function 0x1df458"),
              G(0x1DF4A8, 8, "fit mode of a 16:9 picture on a 4:3 and on a 3:2 panel: 3, 3 (letterbox: what makes the ratio count)"),
              G(DSQ_FN, 16, "first 16 bytes of the de-squeeze calculator 0x1df680"),
              G(0x1DF690, 16, "the calculator's read of the de-squeeze code (accessor slot 0x758) and its range check"),
              G(0x1DF6B0, 16, "the code table and the 1.3x 17:9 branch (17:9 ratios left alone)"),
              G(0x1DF6F0, 16, "the whole-output path before the 16:9 ratios"),
              G(0x1DF718, 16, "the height calculation after the ratios"),
              G(CROP_FN, 16, "first 16 bytes of the input-crop function 0x5faf04 (de-squeeze active test)"),
              G(0x5FAF24, 16, "the crop function's read of the de-squeeze code"),
              G(0x5FAF38, 16, "the first crop path after the code test"),
              G(0x5FAF6C, 16, "the second crop path after the code test (width = (4h + 6) / 3)")]
    for what, t, _ in TABLES:
        for row in (0, 1, 2):
            e = t + 8 * (5 * row + 3)
            guards += [G(e - 8, 8, "%s row %d, the entry before the 16:9 entry (1:1)" % (what.split(" ")[0], row)),
                       G(e + 8, 8, "%s row %d, the entry after the 16:9 entry (17:9)" % (what.split(" ")[0], row))]
    # sites are aligned words of the file; guards and sites do not overlap
    spans = sorted([(int(s["ram_address"], 16), 4, "s") for s in sites] + [(int(g["ram_address"], 16), len(g["bytes"]) // 2, "g") for g in guards])
    assert all(a + n <= b for (a, n, _), (b, _, _) in zip(spans, spans[1:])), "a guard overlaps a site or a guard"
    assert all(int(s["ram_address"], 16) % 4 == 0 and fx(int(s["ram_address"], 16), 4) == bytes.fromhex(s["old"]) and s["old"] != s["new"] for s in sites)
    assert len(sites) == 30, len(sites)
    return {"design": NAME, "build": "fx3_702", "camera": "ILME-FX3 (FX3), firmware 7.02",
            "title": "FX3 7.02: rear screen shows the open-gate live view at 3:2 (16:9 letterbox ratio 9/16 -> 2/3, frame widgets' 16:9 entries for both panel "
                     "shapes), and the built-in Anamorphic Desqueeze display ratios set for a 3:2 picture (1.3x 1.95:1, 1.5x 2.25:1, 1.65x 2.475:1, "
                     "2.0x the whole frame at 3:1)",
            "kind": "ram_words", "artifact": "cpapp-b.bin 7.02 (ILME-FX3), its loaded image in coprocessor RAM: the words are in the file, the change is made in RAM only",
            "artifact_sha256": SHA, "generated_by": "build/build_lcd_fx3.py",
            "ported_from": "lcdratio32_s3_v1 (A7S III 5.01; works on that camera, ninth test 2026-11-22): the same 2/3 ratio and frame entries, in the A7 IV's "
                           "instruction form; the de-squeeze part is new (the A7S III kit has a C3 routine instead)",
            "summary": {"sites": len(sites), "bytes": 4 * len(sites), "guards": len(guards),
                        "picture": "16:9 live view (aspect code 2) holding the whole 3:2 sensor area",
                        "ratio_stock": "9/16", "ratio_new": "2/3", "frame_rectangles_new": {ROWS[r]: list(v) for r, v in RECT_NEW.items()},
                        "desqueeze": {"1.3x": "45/104 -> 20/39", "1.5x": "3/8 -> 4/9", "1.65x": "15/44 -> 40/99", "2.0x": "3/8 -> 1/3, centre crop off"},
                        "goes_with": ["ogsq_fx3_v1", "outsz2560_fx3_v1", "ogfile2560_hs_s_fx3_v1"]},
            "while_applied": "every 16:9 picture on the rear screen is shown at 3:2 and the de-squeeze ratios are those of a 3:2 picture (other movie formats look "
                             "wrong there). 2.0x's ratio is the calculator's default for every picture shape and its crop is off for every shape, so 2.0x shows any "
                             "picture at 3:1 (the open-gate live view is always 16:9). HDMI's own layout (0x1dfb18) and the 17:9 ratios of 1.3x / 1.5x / 1.65x are unchanged",
            "not_checked": ["on a camera: nothing of this design has run on an FX3", "the FX3's panel type byte 0x14909e4 (expected 2 = 4:3; the dump reads it)",
                            "that the FX3's menu sends codes 1 to 4 for 1.3x, 1.5x, 1.65x and 2.0x (inferred from the ratios)",
                            "whether the focus frames are drawn while de-squeeze is on (the frame check has no de-squeeze input; stock behaves the same)"],
            "sites": sites, "guards": guards}


if __name__ == "__main__":
    d = design()
    out = ROOT / "modding" / "designs" / f"{NAME}.json"
    out.write_text(json.dumps(d, indent=1) + "\n", encoding="utf8", newline="\n")
    print("%s: %d sites, %d guards" % (out.name, len(d["sites"]), len(d["guards"])))
    for s in d["sites"]:
        print("  %s %s -> %s  %s" % (s["ram_address"], s["old"], s["new"], s["note"][:90]))
