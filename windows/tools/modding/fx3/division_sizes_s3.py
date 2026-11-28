"""Which output sizes the second scaler's division job accepts on the A7S III (cpapp-b.bin 5.01): the firmware's own job 0x444a74
run alone in Unicorn on constructed whole-frame inputs. The A7S III counterpart of build/division_sizes.py (A7 IV job 0x464ce8).

Why (2026-11-28): the owner asked for a 4240 x 2832 file (the IMX510's whole picture, one to one). On the A7 IV the division job takes
two-unit output widths in multiples of 64 only (F405) and four-unit widths in multiples of 128 (F406). This script asks the A7S III's
own job, so the answer does not rest on the A7 IV's.

The call. build/diff_consts.py lines the two jobs up (1393 of 1479 instructions; every difference a relocated call, string or global):
  job 0x464ce8 -> 0x444a74, log print 0xa32386 -> 0x9faa12, division objects 0x11e07a0 -> 0x11b4ec8 (so 0x11df400 -> 0x11b3b28, the same
  distance), division block 0x1450d70 -> 0x1400888 (modding/A7S3_PORT.md section 13). The division objects are C++ objects: their vtable
  pointers (A7 IV 0xd34f8c..0xd3544c -> -0x29dd4; 0xd3578c -> 0xd0b9d0) and their pointers to each other are moved too (relocate()).
The input and auxiliary records are the A7 IV's stock snapshot (work/ispp/c_stock.json; they are data the caller hands over by pointer), with
the picture words overwritten as division_sizes.run_division does. Controls: the A7S III's own stock request (4240 x 2392 -> 3840 x 2160, two
units) and the proven open-gate one (4240 x 2392 -> 3840 x 2560, F979) must be accepted, and the A7 IV rule's known cases must come out the
same way on this job (two units: 4736 accepted, 4768 and 4704 refused).

  C:\\Python313\\python.exe -B build/division_sizes_s3.py          writes evidence/a7s3/division_sizes_s3.json
  C:\\Python313\\python.exe -B build/division_sizes_s3.py --build fx3_702     writes evidence/fx3/division_sizes_fx3.json
Nothing is hardware; no camera is involved.

--build fx3_702 (2026-11-28, the FX3's 4224x2816 state): the FX3 7.02 coprocessor app is the A7S III's relinked. Its job is 0x43a4f4 (match_thumb
from 0x444a74, one hit; diff_consts aligns 1393 of 1479 instructions, every difference relocated), log print 0x9e6684, division objects 0x118dab0
(A7S III 0x11b4ec8), and all nine vtables are the A7S III's moved by -0x1d028 (the table of 0xcee2e8 holds the job's six callees).
"""
import json
import struct
import sys
from pathlib import Path

import unicorn
from unicorn import arm_const as arm

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "build"))
import locate_file  # noqa: E402

BUILDS = {"a7s3_501": {"job": 0x444A74, "log": 0x9FAA12, "obj": -0x2B8D8, "vt": -0x29DD4, "vt_one": 0xD0B9D0, "out": "evidence/a7s3/division_sizes_s3.json",
                       "name": "A7S III", "works": "F979"},
          "fx3_702": {"job": 0x43A4F4, "log": 0x9E6684, "obj": -0x52CF0, "vt": -0x29DD4 - 0x1D028, "vt_one": 0xD0B9D0 - 0x1D028,
                      "out": "evidence/fx3/division_sizes_fx3.json", "name": "FX3", "works": "two FX3s, 2026-11-24"}}
BUILD = sys.argv[sys.argv.index("--build") + 1] if "--build" in sys.argv else "a7s3_501"
_B = BUILDS[BUILD]
JOB, LOG, TARGET = _B["job"], _B["log"], 0x1400888      # the result block is handed over by pointer: any free RAM (the A7S III's own block)
RELOC = {"0x11df400": 0x11DF400 + _B["obj"], "0x11e07a0": 0x11E07A0 + _B["obj"]}
OBJ = (0x11DF400, 0x11E0FA0, _B["obj"])              # the objects' pointers to each other move with them
VT = (0xD34F00, 0xD35500, _B["vt"])                  # their vtables: one block (found by the job's own callees in the table of 0xd350e4)
VT_ONE = {0xD3578C: _B["vt_one"]}                    # the last object's (found by match_thumb on its methods 0xa2885a, 0xa29d74, 0xa28d6c)


def relocate(data):
    """The A7 IV snapshot's division objects with their pointers moved to this build's addresses."""
    out = bytearray(data)
    for o in range(0, len(out) - 3, 4):
        w = struct.unpack_from("<I", out, o)[0]
        if w in VT_ONE:
            w = VT_ONE[w]
        elif VT[0] <= w < VT[1]:
            w += VT[2]
        elif OBJ[0] <= w < OBJ[1]:
            w += OBJ[2]
        else:
            continue
        struct.pack_into("<I", out, o, w)
    return bytes(out)


def run_division(image, seed, source, dest, engines):
    uc = unicorn.Uc(unicorn.UC_ARCH_ARM, unicorn.UC_MODE_ARM)
    uc.mem_map(0x108000, (len(image) + 4095) // 4096 * 4096)
    uc.mem_write(0x108000, image)
    uc.mem_map(0x1100000, 0x400000)                  # globals and division objects
    uc.mem_map(0x2C20000, 0x10000)                   # input and auxiliary records from the A7 IV's stock snapshot
    uc.mem_map(0x3000000, 0x20000)                   # stack and return sentinel
    uc.reg_write(arm.UC_ARM_REG_C1_C0_2, uc.reg_read(arm.UC_ARM_REG_C1_C0_2) | (0xF << 20))
    uc.reg_write(arm.UC_ARM_REG_FPEXC, 0x40000000)
    for address, to in RELOC.items():
        uc.mem_write(to, relocate(bytes.fromhex(seed["dumps"][address])))
    for snap in seed["snaps"]:
        if snap["pc"] == "0x464ce8":
            uc.mem_write(int(snap["addr"], 16), bytes.fromhex(snap["data"]))
    args = next(c for c in seed["call_args"] if c[1] == "0x464ce8")
    inp, aux = int(args[2], 16), int(args[4], 16)
    (iw, ih), (ow, oh) = source, dest
    words = {1: iw << 12, 2: ih << 12, 0x13: 0, 0x16: iw, 0x17: ih, 0x1A: iw << 12, 0x1B: ih << 12, 0x1C: 0, 0x1D: 0, 0x1E: iw << 12, 0x1F: ih << 12, 0x50: engines}
    for index in (*range(3, 15, 2), 0x2D, 0x31, 0x37, 0x3E, 0x45, 0x4C):
        words[index], words[index + 1] = ow, oh
    for index, value in words.items():
        uc.mem_write(inp + 4 * index, struct.pack("<I", value))
    uc.hook_add(unicorn.UC_HOOK_CODE, lambda m, a, s, d: m.reg_write(arm.UC_ARM_REG_PC, m.reg_read(arm.UC_ARM_REG_LR)), begin=LOG, end=LOG)
    stop = 0x301F000
    for reg, value in ((arm.UC_ARM_REG_R0, inp), (arm.UC_ARM_REG_R1, TARGET), (arm.UC_ARM_REG_R2, aux), (arm.UC_ARM_REG_SP, 0x301E000), (arm.UC_ARM_REG_LR, stop | 1)):
        uc.reg_write(reg, value)
    uc.emu_start(JOB | 1, stop, count=1_000_000)
    assert uc.reg_read(arm.UC_ARM_REG_PC) == stop
    block = bytes(uc.mem_read(TARGET, 0x574))
    status = struct.unpack_from("<I", block, 0x570)[0]
    units = []
    if status == 0:
        for i in range(engines):
            u = struct.unpack_from("<84i", block, i * 0x150)
            units.append({"input_x": u[3], "input_width": u[4], "scaler_out_width": u[8], "mbl_out_width": u[15], "final_x": u[48], "final_width": u[49]})
        assert sum(x["final_width"] for x in units) == ow
    return {"input": list(source), "output": list(dest), "engines": engines, "status": hex(status), "accepted": status == 0, "units": units}


def main():
    image = locate_file.locate(BUILD, "cpapp-b.bin").read_bytes()
    seed = json.loads((ROOT / "work/ispp/c_stock.json").read_text(encoding="utf8"))
    run = lambda s, d, e=2: run_division(image, seed, s, d, e)
    controls = {"stock 4K: 4240x2392 -> 3840x2160": run((4240, 2392), (3840, 2160)),
                "open gate as it records (%s): 4240x2392 -> 3840x2560" % _B["works"]: run((4240, 2392), (3840, 2560)),
                "A7 IV rule, 4736x3156 one to one (accepted there)": run((4736, 3156), (4736, 3156)),
                "A7 IV rule, 4768x2682 one to one (refused there)": run((4768, 2682), (4768, 2682)),
                "A7 IV rule, 4704x3136 one to one (refused there)": run((4704, 3136), (4704, 3136)),
                "A7 IV rule, 4608x3072 one to one (accepted there)": run((4608, 3072), (4608, 3072))}
    want = [True, True, True, False, False, True]
    assert [c["accepted"] for c in controls.values()] == want, [(k, c["status"]) for k, c in controls.items()]
    src = (4240, 2832)
    widths2 = [w for w in range(3840, 4352 + 1, 16) if run(src, (w, w * 2 // 3 // 16 * 16))["accepted"]]
    widths4 = [w for w in range(3840, 4352 + 1, 16) if run(src, (w, w * 2 // 3 // 16 * 16), 4)["accepted"]]
    cases = {"4240x2832 one to one, two units (the size asked for)": run(src, src),
             "4240x2832 one to one, four units": run(src, src, 4),
             "4240x2832 one to one, one unit": run(src, src, 1),
             "4240x2832 -> 4224x2816, two units": run(src, (4224, 2816)),
             "4240x2832 -> 4224x2832, two units": run(src, (4224, 2832)),
             "4224x2816 one to one, two units": run((4224, 2816), (4224, 2816)),
             "4240x2816 -> 4224x2816, two units (the 4224x2816 state)": run((4240, 2816), (4224, 2816)),
             "4240x2816 -> 3840x2560, two units (the real-rows test)": run((4240, 2816), (3840, 2560)),
             "4240x2832 -> 4224x2816, four units": run(src, (4224, 2816), 4),
             "4240x2832 -> 3840x2560, two units (real rows into the proven file)": run(src, (3840, 2560))}
    heights = [h for h in range(2784, 2832 + 1, 8) if run(src, (4224, h))["accepted"]]
    out = {"about": "The %s second scaler's division job (%#x) run alone on constructed inputs. Generated by build/division_sizes_s3.py%s; see its "
                    "header. Arithmetic of the firmware's own job only: no hardware." % (_B["name"], JOB, "" if BUILD == "a7s3_501" else " --build " + BUILD),
           "controls": controls,
           "from_4240x2832_two_units_output_widths_accepted_3840_to_4352_step_16": widths2,
           "from_4240x2832_four_units_output_widths_accepted_3840_to_4352_step_16": widths4,
           "from_4240x2832_two_units_width_4224_heights_accepted_2784_to_2832_step_8": heights,
           "cases": cases}
    (ROOT / _B["out"]).write_text(json.dumps(out, indent=1) + "\n", encoding="utf8", newline="\n")
    print("controls:", {k: c["status"] for k, c in controls.items()})
    print("two-unit widths accepted from 4240x2832:", widths2)
    print("four-unit widths accepted from 4240x2832:", widths4)
    print("heights accepted at 4224 wide:", heights)
    for k, v in cases.items():
        print(k, "->", v["status"], [(u["input_x"], u["input_width"], u["scaler_out_width"], u["mbl_out_width"], u["final_width"]) for u in v["units"]])


if __name__ == "__main__":
    main()
